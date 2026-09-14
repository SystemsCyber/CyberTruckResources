#!/usr/bin/env python3
"""
pcan_logger.py -- log a PEAK PCAN adapter to candump format, in Python.

Two back ends are provided so the notebook can separate two costs:

  --backend ctypes      calls the *same* PCAN-Basic functions the C and Rust loggers
                        use, through ctypes.  Any difference from C/Rust is the cost
                        of the Python interpreter itself.
  --backend python-can  uses the python-can library (pip install python-can), the way
                        most people would actually write this.  The extra cost over
                        the ctypes version is the library's convenience layer
                        (Message objects, timestamp handling, filters, ...).

Usage (same flags as the C and Rust programs):
    python pcan_logger.py [-c PCAN_USBBUS1] [-b 250000] [-t seconds] [-n label] [-o out.log] [-q]
                          [--backend ctypes|python-can]

On exit a one-line JSON summary is printed to stderr, matching the compiled loggers.

ENGR 580A2 -- Secure Vehicle and Industrial Networking, Colorado State University
"""
import argparse
import ctypes
import json
import os
import signal
import sys
import time

# ----------------------------------------------------------------------------
# PCAN-Basic constants (see pcan_basic_min.h)
# ----------------------------------------------------------------------------
CHANNELS = {"PCAN_USBBUS1": 0x51, "PCAN_USBBUS2": 0x52, "PCAN_USBBUS3": 0x53, "PCAN_USBBUS4": 0x54,
            "PCAN_PCIBUS1": 0x41, "PCAN_PCIBUS2": 0x42}
BAUD = {1000000: 0x0014, 500000: 0x001C, 250000: 0x011C, 125000: 0x031C}
PCAN_ERROR_OK, PCAN_ERROR_OVERRUN, PCAN_ERROR_QRCVEMPTY, PCAN_ERROR_QOVERRUN = 0x00, 0x02, 0x20, 0x40
PCAN_ERROR_ANYBUSERR = 0x1C
PCAN_MESSAGE_RTR, PCAN_MESSAGE_EXTENDED, PCAN_MESSAGE_ERRFRAME, PCAN_MESSAGE_STATUS = 0x01, 0x02, 0x40, 0x80


class TPCANMsg(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("ID", ctypes.c_uint32), ("MSGTYPE", ctypes.c_uint8),
                ("LEN", ctypes.c_uint8), ("DATA", ctypes.c_uint8 * 8)]


class TPCANTimestamp(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("millis", ctypes.c_uint32), ("millis_overflow", ctypes.c_uint16),
                ("micros", ctypes.c_uint16)]


def load_pcan_library():
    """Find PCANBasic.dll (Windows) or libpcanbasic.so (Linux); honour PCAN_LIB_DIR."""
    libdir = os.environ.get("PCAN_LIB_DIR")
    if sys.platform.startswith("win"):
        names = ["PCANBasic.dll"]
        loader = ctypes.WinDLL if ctypes.sizeof(ctypes.c_void_p) == 4 else ctypes.CDLL  # stdcall only matters on 32-bit
    else:
        names = ["libpcanbasic.so", "libpcanbasic.so.4"]
        loader = ctypes.CDLL
    last = None
    for n in names:
        try:
            return loader(os.path.join(libdir, n) if libdir else n)
        except OSError as e:
            last = e
    raise SystemExit(f"could not load the PCAN-Basic library ({last}); set PCAN_LIB_DIR")


def cpu_seconds():
    t = os.times()
    return t.user + t.system


def format_candump(t, label, can_id, msgtype, data):
    """Return one candump line as a str."""
    if msgtype & PCAN_MESSAGE_EXTENDED:
        id_str = f"{can_id:08X}"
    else:
        id_str = f"{can_id:03X}"
    payload = "R" if msgtype & PCAN_MESSAGE_RTR else data.hex().upper()
    return f"({t:.6f}) {label} {id_str}#{payload}\n"


# ----------------------------------------------------------------------------
def run_ctypes(args, stop):
    lib = load_pcan_library()
    lib.CAN_Initialize.argtypes = [ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint16]
    lib.CAN_Read.argtypes = [ctypes.c_uint16, ctypes.POINTER(TPCANMsg), ctypes.POINTER(TPCANTimestamp)]
    lib.CAN_Uninitialize.argtypes = [ctypes.c_uint16]
    for f in (lib.CAN_Initialize, lib.CAN_Read, lib.CAN_Uninitialize):
        f.restype = ctypes.c_uint32

    ch = CHANNELS.get(args.channel, int(args.channel, 0) if args.channel[:2] == "0x" else 0x51)
    st = lib.CAN_Initialize(ch, BAUD.get(args.bitrate, 0x011C), 0, 0, 0)
    if st != PCAN_ERROR_OK:
        raise SystemExit(f"CAN_Initialize failed: 0x{st:X}")

    out = open(args.output, "w", buffering=1 << 20) if args.output != "-" else sys.stdout
    msg, ts = TPCANMsg(), TPCANTimestamp()
    frames = bytes_written = q_over = c_over = 0
    anchored = False
    host_anchor = dev_anchor = 0
    t_start, cpu_start = time.time(), cpu_seconds()
    read, label, quiet = lib.CAN_Read, args.label, args.quiet   # local names are faster in CPython

    while not stop["flag"]:
        if args.seconds and time.time() - t_start >= args.seconds:
            break
        st = read(ch, msg, ts)
        if st == PCAN_ERROR_QRCVEMPTY:
            time.sleep(0.0002)          # no event wait in the ctypes version: keep it simple
            continue
        if st & PCAN_ERROR_QOVERRUN: q_over += 1
        if st & PCAN_ERROR_OVERRUN:  c_over += 1
        if st & ~(PCAN_ERROR_QOVERRUN | PCAN_ERROR_OVERRUN | PCAN_ERROR_ANYBUSERR):
            raise SystemExit(f"CAN_Read failed: 0x{st:X}")
        if msg.MSGTYPE & (PCAN_MESSAGE_STATUS | PCAN_MESSAGE_ERRFRAME):
            continue
        dev_us = (ts.millis + (ts.millis_overflow << 32)) * 1000 + ts.micros
        if not anchored:
            host_anchor, dev_anchor, anchored = time.time(), dev_us, True
        t = host_anchor + (dev_us - dev_anchor) / 1e6
        frames += 1
        if not quiet:
            line = format_candump(t, label, msg.ID, msg.MSGTYPE, bytes(msg.DATA[:msg.LEN]))
            out.write(line)
            bytes_written += len(line)

    elapsed, cpu = time.time() - t_start, cpu_seconds() - cpu_start
    if out is not sys.stdout:
        out.close()
    lib.CAN_Uninitialize(ch)
    return summary("Python-ctypes", frames, elapsed, cpu, q_over, c_over, bytes_written)


def run_python_can(args, stop):
    import can  # pip install python-can
    bus = can.Bus(interface="pcan", channel=args.channel, bitrate=args.bitrate)
    out = open(args.output, "w", buffering=1 << 20) if args.output != "-" else sys.stdout
    frames = bytes_written = 0
    t_start, cpu_start = time.time(), cpu_seconds()
    label, quiet = args.label, args.quiet
    try:
        while not stop["flag"]:
            if args.seconds and time.time() - t_start >= args.seconds:
                break
            m = bus.recv(timeout=0.05)
            if m is None or m.is_error_frame:
                continue
            frames += 1
            if not quiet:
                msgtype = (PCAN_MESSAGE_EXTENDED if m.is_extended_id else 0) | (PCAN_MESSAGE_RTR if m.is_remote_frame else 0)
                line = format_candump(m.timestamp, label, m.arbitration_id, msgtype, bytes(m.data))
                out.write(line)
                bytes_written += len(line)
    except KeyboardInterrupt:
        pass
    elapsed, cpu = time.time() - t_start, cpu_seconds() - cpu_start
    if out is not sys.stdout:
        out.close()
    bus.shutdown()
    return summary("Python-python-can", frames, elapsed, cpu, 0, 0, bytes_written)


def summary(language, frames, elapsed, cpu, q_over, c_over, bytes_written):
    return {"language": language, "frames": frames, "elapsed_s": round(elapsed, 3), "cpu_s": round(cpu, 3),
            "frames_per_s": round(frames / elapsed if elapsed else 0, 1),
            "cpu_us_per_frame": round(cpu * 1e6 / frames if frames else 0, 2),
            "rx_queue_overruns": q_over, "ctrl_overruns": c_over, "bytes_written": bytes_written}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", dest="channel", default="PCAN_USBBUS1")
    p.add_argument("-b", dest="bitrate", type=int, default=250000)
    p.add_argument("-t", dest="seconds", type=float, default=0.0)
    p.add_argument("-n", dest="label", default="can0")
    p.add_argument("-o", dest="output", default="-")
    p.add_argument("-q", dest="quiet", action="store_true")
    p.add_argument("--backend", choices=["ctypes", "python-can"], default="ctypes")
    args = p.parse_args()

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))

    result = run_ctypes(args, stop) if args.backend == "ctypes" else run_python_can(args, stop)
    print(json.dumps(result), file=sys.stderr)


if __name__ == "__main__":
    main()
