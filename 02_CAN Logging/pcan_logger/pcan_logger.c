/*
 * pcan_logger.c -- log CAN traffic from a PEAK PCAN adapter to candump format
 *
 *   (1604007042.461135) can1 18FEBF0B#80067D7D79777B79
 *
 * Purpose: give a compiled-language baseline to compare against python-can
 * when deciding whether a logger keeps up with a busy J1939 network
 * (250 kbit/s ~ 2,000 frames/s, 500 kbit/s ~ 4,000 frames/s).
 *
 * Build (Linux, PCAN-Basic for Linux installed):
 *     gcc -O2 -o pcan_logger pcan_logger.c -lpcanbasic
 * Build (Windows, MSVC "x64 Native Tools" prompt, PCANBasic.lib/.dll from PEAK):
 *     cl /O2 pcan_logger.c PCANBasic.lib
 * Build (Windows, MinGW gcc):
 *     gcc -O2 -o pcan_logger.exe pcan_logger.c -L. -lPCANBasic
 * Build against the hardware-free simulator in ../pcan_sim (see README):
 *     gcc -O2 -o pcan_logger pcan_logger.c -L../pcan_sim -lpcanbasic -Wl,-rpath,../pcan_sim
 *
 * Usage:
 *     pcan_logger [-c PCAN_USBBUS1] [-b 250000] [-t seconds] [-n label] [-o out.log] [-q]
 *        -c  channel name (PCAN_USBBUS1..4, PCAN_PCIBUS1..2)         default PCAN_USBBUS1
 *        -b  bit rate in bit/s: 125000 250000 500000 1000000        default 250000
 *        -t  stop after this many seconds (0 = run until Ctrl-C)     default 0
 *        -n  channel label written in the candump line                default can0
 *        -o  output file ('-' = stdout)                               default '-'
 *        -q  quiet: do not write frames, only count them (measures the pure receive cost)
 *
 * On exit the program prints a one-line JSON summary to stderr, for example
 *   {"frames": 120345, "elapsed_s": 60.002, "cpu_s": 0.81, "frames_per_s": 2005.7,
 *    "rx_queue_overruns": 0, "ctrl_overruns": 0, "bytes_written": 5776560}
 * The notebook parses that line.
 *
 * ENGR 580A2 -- Secure Vehicle and Industrial Networking, Colorado State University
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <signal.h>
#include <time.h>

#ifdef _WIN32
#  include <windows.h>
#else
#  include <sys/select.h>
#  include <sys/time.h>
#  include <sys/resource.h>
#  include <unistd.h>
#endif

#include "pcan_basic_min.h"

/* ------------------------------------------------------------------------ */
/* Portable clocks                                                          */
/* ------------------------------------------------------------------------ */
static double wall_seconds(void)          /* seconds since the Unix epoch */
{
#ifdef _WIN32
    FILETIME ft; ULARGE_INTEGER u;
    GetSystemTimePreciseAsFileTime(&ft);
    u.LowPart = ft.dwLowDateTime; u.HighPart = ft.dwHighDateTime;
    return (double)(u.QuadPart - 116444736000000000ULL) / 1e7;
#else
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
#endif
}

static double cpu_seconds(void)           /* user+system CPU time of this process */
{
#ifdef _WIN32
    FILETIME c, e, k, u; ULARGE_INTEGER ku, uu;
    GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &u);
    ku.LowPart = k.dwLowDateTime; ku.HighPart = k.dwHighDateTime;
    uu.LowPart = u.dwLowDateTime; uu.HighPart = u.dwHighDateTime;
    return (double)(ku.QuadPart + uu.QuadPart) / 1e7;
#else
    struct rusage r;
    getrusage(RUSAGE_SELF, &r);
    return r.ru_utime.tv_sec + r.ru_utime.tv_usec / 1e6
         + r.ru_stime.tv_sec + r.ru_stime.tv_usec / 1e6;
#endif
}

/* ------------------------------------------------------------------------ */
/* Argument helpers                                                         */
/* ------------------------------------------------------------------------ */
static TPCANHandle channel_from_name(const char *s)
{
    struct { const char *n; TPCANHandle h; } tbl[] = {
        {"PCAN_USBBUS1", PCAN_USBBUS1}, {"PCAN_USBBUS2", PCAN_USBBUS2},
        {"PCAN_USBBUS3", PCAN_USBBUS3}, {"PCAN_USBBUS4", PCAN_USBBUS4},
        {"PCAN_PCIBUS1", PCAN_PCIBUS1}, {"PCAN_PCIBUS2", PCAN_PCIBUS2},
    };
    for (size_t i = 0; i < sizeof tbl / sizeof tbl[0]; i++)
        if (strcmp(tbl[i].n, s) == 0) return tbl[i].h;
    return (TPCANHandle)strtoul(s, NULL, 0);      /* allow raw 0x51 etc. */
}

static TPCANBaudrate baud_from_bps(long bps)
{
    switch (bps) {
        case 1000000: return PCAN_BAUD_1M;
        case 500000:  return PCAN_BAUD_500K;
        case 250000:  return PCAN_BAUD_250K;
        case 125000:  return PCAN_BAUD_125K;
        default:
            fprintf(stderr, "unsupported bit rate %ld, using 250000\n", bps);
            return PCAN_BAUD_250K;
    }
}

static void die(const char *what, TPCANStatus st)
{
    char text[256] = "";
    CAN_GetErrorText(st, 0x09, text);
    fprintf(stderr, "%s failed: 0x%X %s\n", what, (unsigned)st, text);
    exit(1);
}

/* ------------------------------------------------------------------------ */
/* Ctrl-C handling                                                          */
/* ------------------------------------------------------------------------ */
static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig) { (void)sig; g_stop = 1; }

/* ------------------------------------------------------------------------ */
/* Fast candump line formatter                                              */
/*   sprintf is slow; hand-rolled hex is ~5-10x faster and shows what the   */
/*   text format actually costs.                                            */
/* ------------------------------------------------------------------------ */
static const char HEX[] = "0123456789ABCDEF";

static size_t format_candump(char *out, double t, const char *label, size_t label_len,
                             const TPCANMsg *m)
{
    char *p = out;
    /* (seconds.micros) */
    long long secs = (long long)t;
    long usec = (long)((t - (double)secs) * 1e6 + 0.5);
    if (usec >= 1000000) { usec -= 1000000; secs++; }
    p += sprintf(p, "(%lld.%06ld) ", secs, usec);   /* one sprintf for the time only */
    memcpy(p, label, label_len); p += label_len;
    *p++ = ' ';
    if (m->MSGTYPE & PCAN_MESSAGE_EXTENDED) {
        for (int shift = 28; shift >= 0; shift -= 4) *p++ = HEX[(m->ID >> shift) & 0xF];
    } else {
        for (int shift = 8; shift >= 0; shift -= 4) *p++ = HEX[(m->ID >> shift) & 0xF];
    }
    *p++ = '#';
    if (m->MSGTYPE & PCAN_MESSAGE_RTR) {
        *p++ = 'R';
    } else {
        for (int i = 0; i < m->LEN && i < 8; i++) {
            *p++ = HEX[m->DATA[i] >> 4];
            *p++ = HEX[m->DATA[i] & 0xF];
        }
    }
    *p++ = '\n';
    return (size_t)(p - out);
}

/* ------------------------------------------------------------------------ */
int main(int argc, char **argv)
{
    const char *chan_name = "PCAN_USBBUS1";
    const char *label     = "can0";
    const char *outname   = "-";
    long   bps      = 250000;
    double run_secs = 0.0;
    int    quiet    = 0;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "-c") && i + 1 < argc) chan_name = argv[++i];
        else if (!strcmp(argv[i], "-b") && i + 1 < argc) bps       = atol(argv[++i]);
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) run_secs  = atof(argv[++i]);
        else if (!strcmp(argv[i], "-n") && i + 1 < argc) label     = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outname   = argv[++i];
        else if (!strcmp(argv[i], "-q")) quiet = 1;
        else { fprintf(stderr, "unknown argument %s\n", argv[i]); return 2; }
    }

    TPCANHandle ch = channel_from_name(chan_name);
    TPCANStatus st = CAN_Initialize(ch, baud_from_bps(bps), 0, 0, 0);
    if (st != PCAN_ERROR_OK) die("CAN_Initialize", st);

    /* Ask the driver to wake us up instead of polling. */
#ifdef _WIN32
    HANDLE ev = CreateEvent(NULL, FALSE, FALSE, NULL);
    st = CAN_SetValue(ch, PCAN_RECEIVE_EVENT, &ev, sizeof(ev));
    int have_event = (st == PCAN_ERROR_OK);
#else
    int fd = -1;
    st = CAN_GetValue(ch, PCAN_RECEIVE_EVENT, &fd, sizeof(fd));
    int have_event = (st == PCAN_ERROR_OK && fd >= 0);
#endif

    FILE *out = stdout;
    if (strcmp(outname, "-") != 0) {
        out = fopen(outname, "wb");
        if (!out) { perror(outname); return 1; }
    }
    static char iobuf[1 << 20];
    setvbuf(out, iobuf, _IOFBF, sizeof iobuf);      /* 1 MiB buffer: fewer syscalls */

    signal(SIGINT, on_sigint);

    TPCANMsg msg; TPCANTimestamp ts;
    char line[96];
    size_t label_len = strlen(label);

    unsigned long long frames = 0, bytes = 0, q_overruns = 0, ctrl_overruns = 0;
    double t_start = wall_seconds(), cpu_start = cpu_seconds();
    double host_anchor = 0.0; uint64_t dev_anchor = 0; int anchored = 0;

    while (!g_stop) {
        if (run_secs > 0 && wall_seconds() - t_start >= run_secs) break;

        st = CAN_Read(ch, &msg, &ts);

        if (st == PCAN_ERROR_QRCVEMPTY) {
            /* Nothing queued: sleep until the driver signals, or briefly. */
#ifdef _WIN32
            if (have_event) WaitForSingleObject(ev, 50); else Sleep(1);
#else
            if (have_event) {
                fd_set rfds; FD_ZERO(&rfds); FD_SET(fd, &rfds);
                struct timeval tv = {0, 50000};
                select(fd + 1, &rfds, NULL, NULL, &tv);
            } else {
                usleep(200);
            }
#endif
            continue;
        }
        if (st & PCAN_ERROR_QOVERRUN) q_overruns++;   /* we were too slow: frames lost */
        if (st & PCAN_ERROR_OVERRUN)  ctrl_overruns++;
        if (st & ~(PCAN_ERROR_QOVERRUN | PCAN_ERROR_OVERRUN | PCAN_ERROR_ANYBUSERR)) {
            if (st != PCAN_ERROR_OK) die("CAN_Read", st);
        }
        if (msg.MSGTYPE & (PCAN_MESSAGE_STATUS | PCAN_MESSAGE_ERRFRAME)) continue;

        /* Convert the device timestamp to Unix time: anchor the first frame to the host clock. */
        uint64_t dev_us = ((uint64_t)ts.millis + ((uint64_t)ts.millis_overflow << 32)) * 1000ULL + ts.micros;
        if (!anchored) { host_anchor = wall_seconds(); dev_anchor = dev_us; anchored = 1; }
        double t = host_anchor + (double)(int64_t)(dev_us - dev_anchor) / 1e6;

        frames++;
        if (!quiet) {
            size_t n = format_candump(line, t, label, label_len, &msg);
            fwrite(line, 1, n, out);
            bytes += n;
        }
    }

    double elapsed = wall_seconds() - t_start, cpu = cpu_seconds() - cpu_start;
    fflush(out);
    if (out != stdout) fclose(out);
    CAN_Uninitialize(ch);

    fprintf(stderr,
        "{\"language\": \"C\", \"frames\": %llu, \"elapsed_s\": %.3f, \"cpu_s\": %.3f, "
        "\"frames_per_s\": %.1f, \"cpu_us_per_frame\": %.2f, \"rx_queue_overruns\": %llu, "
        "\"ctrl_overruns\": %llu, \"bytes_written\": %llu}\n",
        frames, elapsed, cpu, frames / (elapsed > 0 ? elapsed : 1),
        frames ? cpu * 1e6 / frames : 0.0, q_overruns, ctrl_overruns, bytes);
    return 0;
}
