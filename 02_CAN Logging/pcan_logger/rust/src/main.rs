//! pcan_logger_rs -- log CAN traffic from a PEAK PCAN adapter to candump format.
//!
//! This is the Rust twin of ../pcan_logger.c.  It calls the very same C functions
//! exported by PCANBasic.dll / libpcanbasic.so through a hand-written FFI block,
//! so any speed difference between the two programs comes from the language and
//! its standard library, not from a different driver path.
//!
//! Build:
//!     cargo build --release                       # library on the default search path
//!     PCAN_LIB_DIR=../pcan_sim cargo build --release   # link against the simulator
//! Usage: same flags as the C program
//!     pcan_logger_rs [-c PCAN_USBBUS1] [-b 250000] [-t seconds] [-n label] [-o out.log] [-q]
//!
//! ENGR 580A2 -- Secure Vehicle and Industrial Networking, Colorado State University

use std::ffi::c_void;
use std::io::{self, BufWriter, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// FFI: the slice of the PCAN-Basic API we use (see pcan_basic_min.h)
// ---------------------------------------------------------------------------
type TPCANHandle = u16;
type TPCANStatus = u32;
type TPCANParameter = u8;
type TPCANBaudrate = u16;

#[repr(C, packed)]
#[derive(Clone, Copy, Default)]
struct TPCANMsg {
    id: u32,
    msgtype: u8,
    len: u8,
    data: [u8; 8],
}

#[repr(C, packed)]
#[derive(Clone, Copy, Default)]
struct TPCANTimestamp {
    millis: u32,
    millis_overflow: u16,
    micros: u16,
}

const PCAN_USBBUS1: TPCANHandle = 0x51;
const PCAN_BAUD_1M: TPCANBaudrate = 0x0014;
const PCAN_BAUD_500K: TPCANBaudrate = 0x001C;
const PCAN_BAUD_250K: TPCANBaudrate = 0x011C;
const PCAN_BAUD_125K: TPCANBaudrate = 0x031C;

const PCAN_ERROR_OK: TPCANStatus = 0x00;
const PCAN_ERROR_OVERRUN: TPCANStatus = 0x02;
const PCAN_ERROR_ANYBUSERR: TPCANStatus = 0x1C;
const PCAN_ERROR_QRCVEMPTY: TPCANStatus = 0x20;
const PCAN_ERROR_QOVERRUN: TPCANStatus = 0x40;

const PCAN_MESSAGE_RTR: u8 = 0x01;
const PCAN_MESSAGE_EXTENDED: u8 = 0x02;
const PCAN_MESSAGE_ERRFRAME: u8 = 0x40;
const PCAN_MESSAGE_STATUS: u8 = 0x80;

const PCAN_RECEIVE_EVENT: TPCANParameter = 0x03;

// "system" = stdcall on 32-bit Windows, the plain C convention everywhere else,
// which is exactly what the PCANBasic.dll / libpcanbasic.so exports use.
#[cfg_attr(windows, link(name = "PCANBasic"))]
#[cfg_attr(not(windows), link(name = "pcanbasic"))]
extern "system" {
    fn CAN_Initialize(channel: TPCANHandle, btr0btr1: TPCANBaudrate, hwtype: u8, ioport: u32, interrupt: u16) -> TPCANStatus;
    fn CAN_Uninitialize(channel: TPCANHandle) -> TPCANStatus;
    fn CAN_Read(channel: TPCANHandle, msg: *mut TPCANMsg, ts: *mut TPCANTimestamp) -> TPCANStatus;
    fn CAN_GetValue(channel: TPCANHandle, param: TPCANParameter, buf: *mut c_void, len: u32) -> TPCANStatus;
    #[allow(dead_code)]
    fn CAN_SetValue(channel: TPCANHandle, param: TPCANParameter, buf: *mut c_void, len: u32) -> TPCANStatus;
    fn CAN_GetErrorText(error: TPCANStatus, language: u16, buf: *mut u8) -> TPCANStatus;
}

fn error_text(st: TPCANStatus) -> String {
    let mut buf = [0u8; 256];
    unsafe { CAN_GetErrorText(st, 0x09, buf.as_mut_ptr()) };
    let n = buf.iter().position(|&b| b == 0).unwrap_or(buf.len());
    String::from_utf8_lossy(&buf[..n]).into_owned()
}

// ---------------------------------------------------------------------------
// Waiting for data: Windows event handle or Linux file descriptor
// ---------------------------------------------------------------------------
#[cfg(windows)]
mod wait {
    use super::*;
    #[link(name = "kernel32")]
    extern "system" {
        fn CreateEventW(attr: *mut c_void, manual: i32, initial: i32, name: *const u16) -> *mut c_void;
        fn WaitForSingleObject(h: *mut c_void, ms: u32) -> u32;
    }
    pub struct Waiter(*mut c_void);
    impl Waiter {
        pub fn new(ch: TPCANHandle) -> Option<Waiter> {
            unsafe {
                let mut h = CreateEventW(std::ptr::null_mut(), 0, 0, std::ptr::null());
                let st = CAN_SetValue(ch, PCAN_RECEIVE_EVENT, &mut h as *mut _ as *mut c_void, std::mem::size_of::<*mut c_void>() as u32);
                if st == PCAN_ERROR_OK { Some(Waiter(h)) } else { None }
            }
        }
        pub fn wait(&self) { unsafe { WaitForSingleObject(self.0, 50); } }
    }
}

#[cfg(not(windows))]
mod wait {
    use super::*;
    extern "C" {
        fn poll(fds: *mut PollFd, nfds: u64, timeout_ms: i32) -> i32;
    }
    #[repr(C)]
    struct PollFd { fd: i32, events: i16, revents: i16 }
    pub struct Waiter(i32);
    impl Waiter {
        pub fn new(ch: TPCANHandle) -> Option<Waiter> {
            let mut fd: i32 = -1;
            let st = unsafe { CAN_GetValue(ch, PCAN_RECEIVE_EVENT, &mut fd as *mut _ as *mut c_void, 4) };
            if st == PCAN_ERROR_OK && fd >= 0 { Some(Waiter(fd)) } else { None }
        }
        pub fn wait(&self) {
            let mut p = PollFd { fd: self.0, events: 0x0001 /* POLLIN */, revents: 0 };
            unsafe { poll(&mut p, 1, 50); }
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
fn channel_from_name(s: &str) -> TPCANHandle {
    match s {
        "PCAN_USBBUS1" => 0x51, "PCAN_USBBUS2" => 0x52, "PCAN_USBBUS3" => 0x53, "PCAN_USBBUS4" => 0x54,
        "PCAN_PCIBUS1" => 0x41, "PCAN_PCIBUS2" => 0x42,
        _ => u16::from_str_radix(s.trim_start_matches("0x"), 16).unwrap_or(PCAN_USBBUS1),
    }
}

fn baud_from_bps(bps: u64) -> TPCANBaudrate {
    match bps {
        1_000_000 => PCAN_BAUD_1M, 500_000 => PCAN_BAUD_500K, 125_000 => PCAN_BAUD_125K,
        250_000 => PCAN_BAUD_250K,
        _ => { eprintln!("unsupported bit rate {bps}, using 250000"); PCAN_BAUD_250K }
    }
}

fn unix_seconds() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

/// user+system CPU time of this process, in seconds
fn cpu_seconds() -> f64 {
    #[cfg(not(windows))]
    unsafe {
        #[repr(C)] struct Timeval { sec: i64, usec: i64 }
        #[repr(C)] struct Rusage { utime: Timeval, stime: Timeval, rest: [i64; 14] }
        extern "C" { fn getrusage(who: i32, r: *mut Rusage) -> i32; }
        let mut r: Rusage = std::mem::zeroed();
        getrusage(0, &mut r);
        (r.utime.sec + r.stime.sec) as f64 + (r.utime.usec + r.stime.usec) as f64 / 1e6
    }
    #[cfg(windows)]
    unsafe {
        #[repr(C)] #[derive(Default)] struct Ft { lo: u32, hi: u32 }
        #[link(name = "kernel32")]
        extern "system" {
            fn GetCurrentProcess() -> *mut c_void;
            fn GetProcessTimes(h: *mut c_void, c: *mut Ft, e: *mut Ft, k: *mut Ft, u: *mut Ft) -> i32;
        }
        let (mut c, mut e, mut k, mut u) = (Ft::default(), Ft::default(), Ft::default(), Ft::default());
        GetProcessTimes(GetCurrentProcess(), &mut c, &mut e, &mut k, &mut u);
        let f = |t: &Ft| ((t.hi as u64) << 32 | t.lo as u64) as f64 / 1e7;
        f(&k) + f(&u)
    }
}

const HEX: &[u8; 16] = b"0123456789ABCDEF";

/// Write one candump line into `out` and return its length.
fn format_candump(out: &mut [u8], t: f64, label: &[u8], m: &TPCANMsg) -> usize {
    let mut secs = t as i64;
    let mut usec = ((t - secs as f64) * 1e6 + 0.5) as i64;
    if usec >= 1_000_000 { usec -= 1_000_000; secs += 1; }
    // (seconds.micros) -- write! into a byte slice avoids allocating a String
    let mut n = {
        let mut cur = io::Cursor::new(&mut out[..]);
        write!(cur, "({secs}.{usec:06}) ").unwrap();
        cur.position() as usize
    };
    out[n..n + label.len()].copy_from_slice(label);
    n += label.len();
    out[n] = b' '; n += 1;
    let id = m.id;                                   // copy out of the packed struct
    let nibbles: i32 = if m.msgtype & PCAN_MESSAGE_EXTENDED != 0 { 8 } else { 3 };
    for i in (0..nibbles).rev() {
        out[n] = HEX[((id >> (4 * i)) & 0xF) as usize]; n += 1;
    }
    out[n] = b'#'; n += 1;
    if m.msgtype & PCAN_MESSAGE_RTR != 0 {
        out[n] = b'R'; n += 1;
    } else {
        for &b in &m.data[..(m.len as usize).min(8)] {
            out[n] = HEX[(b >> 4) as usize]; out[n + 1] = HEX[(b & 0xF) as usize]; n += 2;
        }
    }
    out[n] = b'\n'; n += 1;
    n
}

static STOP: AtomicBool = AtomicBool::new(false);

// Minimal Ctrl-C handling without the `ctrlc` crate.
#[cfg(not(windows))]
fn install_sigint() {
    extern "C" { fn signal(sig: i32, handler: extern "C" fn(i32)) -> usize; }
    extern "C" fn on_sigint(_: i32) { STOP.store(true, Ordering::SeqCst); }
    unsafe { signal(2 /* SIGINT */, on_sigint); }
}
#[cfg(windows)]
fn install_sigint() {
    #[link(name = "kernel32")]
    extern "system" { fn SetConsoleCtrlHandler(h: extern "system" fn(u32) -> i32, add: i32) -> i32; }
    extern "system" fn on_ctrl(_: u32) -> i32 { STOP.store(true, Ordering::SeqCst); 1 }
    unsafe { SetConsoleCtrlHandler(on_ctrl, 1); }
}

// ---------------------------------------------------------------------------
fn main() {
    let mut chan_name = String::from("PCAN_USBBUS1");
    let mut label = String::from("can0");
    let mut outname = String::from("-");
    let mut bps: u64 = 250_000;
    let mut run_secs: f64 = 0.0;
    let mut quiet = false;

    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-c" if i + 1 < args.len() => { chan_name = args[i + 1].clone(); i += 1; }
            "-b" if i + 1 < args.len() => { bps = args[i + 1].parse().unwrap_or(250_000); i += 1; }
            "-t" if i + 1 < args.len() => { run_secs = args[i + 1].parse().unwrap_or(0.0); i += 1; }
            "-n" if i + 1 < args.len() => { label = args[i + 1].clone(); i += 1; }
            "-o" if i + 1 < args.len() => { outname = args[i + 1].clone(); i += 1; }
            "-q" => quiet = true,
            other => { eprintln!("unknown argument {other}"); std::process::exit(2); }
        }
        i += 1;
    }

    let ch = channel_from_name(&chan_name);
    let st = unsafe { CAN_Initialize(ch, baud_from_bps(bps), 0, 0, 0) };
    if st != PCAN_ERROR_OK {
        eprintln!("CAN_Initialize failed: 0x{st:X} {}", error_text(st));
        std::process::exit(1);
    }
    let waiter = wait::Waiter::new(ch);

    // 1 MiB buffered writer: the OS write() call is far more expensive than formatting.
    let sink: Box<dyn Write> = if outname == "-" {
        Box::new(io::stdout())
    } else {
        Box::new(std::fs::File::create(&outname).unwrap_or_else(|e| { eprintln!("{outname}: {e}"); std::process::exit(1) }))
    };
    let mut out = BufWriter::with_capacity(1 << 20, sink);

    install_sigint();

    let mut msg = TPCANMsg::default();
    let mut ts = TPCANTimestamp::default();
    let mut line = [0u8; 96];
    let label_b = label.as_bytes();

    let (mut frames, mut bytes, mut q_overruns, mut ctrl_overruns) = (0u64, 0u64, 0u64, 0u64);
    let t_start = Instant::now();
    let cpu_start = cpu_seconds();
    let (mut host_anchor, mut dev_anchor, mut anchored) = (0.0f64, 0u64, false);
    let run_limit = if run_secs > 0.0 { Some(Duration::from_secs_f64(run_secs)) } else { None };

    while !STOP.load(Ordering::Relaxed) {
        if let Some(limit) = run_limit { if t_start.elapsed() >= limit { break; } }

        let st = unsafe { CAN_Read(ch, &mut msg, &mut ts) };
        if st == PCAN_ERROR_QRCVEMPTY {
            match &waiter {
                Some(w) => w.wait(),
                None => std::thread::sleep(Duration::from_micros(200)),
            }
            continue;
        }
        if st & PCAN_ERROR_QOVERRUN != 0 { q_overruns += 1; }
        if st & PCAN_ERROR_OVERRUN != 0 { ctrl_overruns += 1; }
        if st & !(PCAN_ERROR_QOVERRUN | PCAN_ERROR_OVERRUN | PCAN_ERROR_ANYBUSERR) != 0 {
            eprintln!("CAN_Read failed: 0x{st:X} {}", error_text(st));
            break;
        }
        if msg.msgtype & (PCAN_MESSAGE_STATUS | PCAN_MESSAGE_ERRFRAME) != 0 { continue; }

        let (millis, over, micros) = (ts.millis, ts.millis_overflow, ts.micros); // copy from packed struct
        let dev_us = ((millis as u64) + ((over as u64) << 32)) * 1000 + micros as u64;
        if !anchored { host_anchor = unix_seconds(); dev_anchor = dev_us; anchored = true; }
        let t = host_anchor + (dev_us as i64 - dev_anchor as i64) as f64 / 1e6;

        frames += 1;
        if !quiet {
            let n = format_candump(&mut line, t, label_b, &msg);
            out.write_all(&line[..n]).unwrap();
            bytes += n as u64;
        }
    }

    let elapsed = t_start.elapsed().as_secs_f64();
    let cpu = cpu_seconds() - cpu_start;
    out.flush().ok();
    drop(out);
    unsafe { CAN_Uninitialize(ch) };

    eprintln!(
        "{{\"language\": \"Rust\", \"frames\": {frames}, \"elapsed_s\": {elapsed:.3}, \"cpu_s\": {cpu:.3}, \
         \"frames_per_s\": {:.1}, \"cpu_us_per_frame\": {:.2}, \"rx_queue_overruns\": {q_overruns}, \
         \"ctrl_overruns\": {ctrl_overruns}, \"bytes_written\": {bytes}}}",
        frames as f64 / if elapsed > 0.0 { elapsed } else { 1.0 },
        if frames > 0 { cpu * 1e6 / frames as f64 } else { 0.0 }
    );
}
