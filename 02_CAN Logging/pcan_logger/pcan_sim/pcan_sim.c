/*
 * pcan_sim.c -- a drop-in *simulator* of the PCAN-Basic shared library.
 *
 * It exports the same functions as PCANBasic.dll / libpcanbasic.so, but instead
 * of talking to hardware it replays a candump text file.  This lets you compile,
 * run and benchmark the C, Rust and Python loggers on any computer, and it makes
 * the comparison fair: every logger sees exactly the same frames.
 *
 * Build:
 *     Linux:   gcc -O2 -shared -fPIC -o libpcanbasic.so pcan_sim.c
 *     Windows: cl /O2 /LD pcan_sim.c /Fe:PCANBasic.dll     (MSVC)
 *              gcc -O2 -shared -o PCANBasic.dll pcan_sim.c   (MinGW)
 *
 * Control with environment variables:
 *     PCAN_SIM_FILE   candump file to replay              (default candump_kw_drive.txt)
 *     PCAN_SIM_MODE   burst | realtime                    (default burst)
 *                     burst    = hand out frames as fast as the caller reads them
 *                     realtime = honour the timestamps in the file
 *     PCAN_SIM_SPEED  realtime speed factor (2 = twice as fast)   (default 1)
 *     PCAN_SIM_LOOPS  how many times to replay the file           (default 1)
 *     PCAN_SIM_EOF_SIGINT  1 = send SIGINT to the process when frames run out (default 1)
 *
 * Only the behaviour the loggers rely on is simulated.  Do not ship this next to
 * a real installation -- a program that finds this library first will never see
 * the real adapter.
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
#  define EXPORT __declspec(dllexport)
#else
#  include <unistd.h>
#  include <fcntl.h>
#  include <pthread.h>
#  define EXPORT __attribute__((visibility("default")))
#endif

#define HAVE_PCANBASIC_H_NEVER
#include "../pcan_basic_min.h"

typedef struct { double t; uint32_t id; uint8_t ext; uint8_t len; uint8_t data[8]; } Frame;

static Frame   *g_frames = NULL;
static size_t   g_count = 0, g_next = 0;
static int      g_loops = 1, g_loop = 0, g_realtime = 0, g_eof_sigint = 1, g_open = 0, g_eof_sent = 0;
static double   g_speed = 1.0, g_t0_wall = 0.0, g_t0_file = 0.0;
static volatile int g_ticker_run = 0;   /* realtime mode: helper thread signals "frame due" */
#ifdef _WIN32
static HANDLE   g_event = NULL;
static HANDLE   g_ticker = NULL;
#else
static int      g_pipe[2] = {-1, -1};
static pthread_t g_ticker;
#endif

static double now_s(void)
{
#ifdef _WIN32
    LARGE_INTEGER f, c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return (double)c.QuadPart / (double)f.QuadPart;
#else
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
#endif
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int load_file(const char *name)
{
    FILE *f = fopen(name, "r");
    if (!f) { fprintf(stderr, "pcan_sim: cannot open %s\n", name); return 0; }
    size_t cap = 1 << 16;
    g_frames = malloc(cap * sizeof(Frame));
    char line[512];
    while (fgets(line, sizeof line, f)) {
        /* (1604007042.461135) can1 18FEBF0B#80067D7D79777B79 */
        char *p = strchr(line, '(');  if (!p) continue;
        double t = strtod(p + 1, &p);
        if (*p != ')') continue;
        p++;
        while (*p == ' ') p++;
        while (*p && *p != ' ') p++;              /* skip channel */
        while (*p == ' ') p++;
        char *hash = strchr(p, '#'); if (!hash) continue;
        size_t idlen = (size_t)(hash - p);
        uint32_t id = 0;
        for (size_t i = 0; i < idlen; i++) { int v = hexval(p[i]); if (v < 0) { id = 0xFFFFFFFF; break; } id = (id << 4) | (uint32_t)v; }
        if (id == 0xFFFFFFFF) continue;
        Frame fr; fr.t = t; fr.id = id; fr.ext = idlen > 3; fr.len = 0;
        char *d = hash + 1;
        while (fr.len < 8 && hexval(d[0]) >= 0 && hexval(d[1]) >= 0) {
            fr.data[fr.len++] = (uint8_t)((hexval(d[0]) << 4) | hexval(d[1]));
            d += 2;
        }
        if (g_count == cap) { cap *= 2; g_frames = realloc(g_frames, cap * sizeof(Frame)); }
        g_frames[g_count++] = fr;
    }
    fclose(f);
    return g_count > 0;
}

/* Wake up a waiting logger: Windows event or a byte in the Linux pipe. */
static void signal_rx(void)
{
#ifdef _WIN32
    if (g_event) SetEvent(g_event);
#else
    if (g_pipe[1] >= 0) { if (write(g_pipe[1], "x", 1) < 0) { /* pipe full: fine */ } }
#endif
}

static void drain_rx(void)
{
#ifndef _WIN32
    char buf[256];
    if (g_pipe[0] >= 0) while (read(g_pipe[0], buf, sizeof buf) > 0) { }
#endif
}

static void sleep_s(double s)
{
    if (s <= 0) return;
#ifdef _WIN32
    Sleep((DWORD)(s * 1000));
#else
    struct timespec sl = { (time_t)s, (long)((s - (time_t)s) * 1e9) }; nanosleep(&sl, NULL);
#endif
}

/* Realtime mode only: behave like a driver interrupt -- signal each time a frame becomes due.
 * NOTE: this thread runs inside the logger's own process, so in realtime mode the CPU time a
 * logger reports includes the simulator's timing work.  Compare loggers with each other, not
 * with the absolute CPU numbers from real hardware. */
#ifdef _WIN32
static DWORD WINAPI ticker_main(LPVOID arg)
#else
static void *ticker_main(void *arg)
#endif
{
    (void)arg;
    while (g_ticker_run) {
        size_t n = g_next; int loop = g_loop;
        if (n >= g_count) { sleep_s(0.001); continue; }
        double due = g_t0_wall + (g_frames[n].t - g_t0_file) / g_speed;
        double wait = due - now_s();
        if (wait > 0) { sleep_s(wait > 0.002 ? 0.002 : wait); continue; }
        signal_rx();
        /* sleep until the following frame is due (at least 50 us) -- one wakeup per frame,
           roughly what a driver interrupt costs.  Signalling twice is harmless. */
        (void)loop;
        double next_due = (n + 1 < g_count) ? g_t0_wall + (g_frames[n + 1].t - g_t0_file) / g_speed : now_s() + 0.001;
        double w2 = next_due - now_s();
        sleep_s(w2 < 0.00005 ? 0.00005 : w2);
    }
#ifdef _WIN32
    return 0;
#else
    return NULL;
#endif
}

EXPORT TPCANStatus PCAN_API CAN_Initialize(TPCANHandle Channel, TPCANBaudrate Btr0Btr1,
                                           TPCANType HwType, uint32_t IOPort, uint16_t Interrupt)
{
    (void)Channel; (void)Btr0Btr1; (void)HwType; (void)IOPort; (void)Interrupt;
    const char *file = getenv("PCAN_SIM_FILE"); if (!file) file = "candump_kw_drive.txt";
    const char *mode = getenv("PCAN_SIM_MODE"); g_realtime = mode && !strcmp(mode, "realtime");
    const char *sp = getenv("PCAN_SIM_SPEED"); if (sp) g_speed = atof(sp); if (g_speed <= 0) g_speed = 1;
    const char *lp = getenv("PCAN_SIM_LOOPS"); if (lp) g_loops = atoi(lp); if (g_loops < 1) g_loops = 1;
    const char *es = getenv("PCAN_SIM_EOF_SIGINT"); if (es) g_eof_sigint = atoi(es);
    if (!g_frames && !load_file(file)) return PCAN_ERROR_ILLHW;
    g_next = 0; g_loop = 0; g_eof_sent = 0;
    g_t0_wall = now_s(); g_t0_file = g_frames[0].t;
#ifndef _WIN32
    if (g_pipe[0] < 0 && pipe(g_pipe) == 0) {
        fcntl(g_pipe[0], F_SETFL, O_NONBLOCK);
        fcntl(g_pipe[1], F_SETFL, O_NONBLOCK);
    }
    drain_rx();
#endif
    g_open = 1;
    if (g_realtime) {
        g_ticker_run = 1;
#ifdef _WIN32
        g_ticker = CreateThread(NULL, 0, ticker_main, NULL, 0, NULL);
#else
        pthread_create(&g_ticker, NULL, ticker_main, NULL);
#endif
    } else {
        signal_rx();   /* burst mode: always readable, select()/WaitForSingleObject return at once */
    }
    return PCAN_ERROR_OK;
}

EXPORT TPCANStatus PCAN_API CAN_Uninitialize(TPCANHandle Channel)
{
    (void)Channel;
    g_open = 0;
    if (g_ticker_run) {
        g_ticker_run = 0;
#ifdef _WIN32
        WaitForSingleObject(g_ticker, 1000); CloseHandle(g_ticker); g_ticker = NULL;
#else
        pthread_join(g_ticker, NULL);
#endif
    }
    return PCAN_ERROR_OK;
}
EXPORT TPCANStatus PCAN_API CAN_Reset(TPCANHandle Channel) { (void)Channel; return PCAN_ERROR_OK; }
EXPORT TPCANStatus PCAN_API CAN_GetStatus(TPCANHandle Channel) { (void)Channel; return PCAN_ERROR_OK; }
EXPORT TPCANStatus PCAN_API CAN_Write(TPCANHandle Channel, TPCANMsg *m) { (void)Channel; (void)m; return PCAN_ERROR_OK; }

EXPORT TPCANStatus PCAN_API CAN_Read(TPCANHandle Channel, TPCANMsg *msg, TPCANTimestamp *ts)
{
    (void)Channel;
    if (!g_open) return PCAN_ERROR_INITIALIZE;
    if (g_next >= g_count) {
        if (++g_loop < g_loops) { g_next = 0; g_t0_wall += (g_frames[g_count-1].t - g_t0_file) / g_speed; }
        else {
            if (g_eof_sigint && !g_eof_sent) { g_eof_sent = 1; raise(SIGINT); }
            return PCAN_ERROR_QRCVEMPTY;
        }
    }
    Frame *f = &g_frames[g_next];
    double rel = (f->t - g_t0_file) / g_speed;              /* seconds since replay start */
    if (g_realtime && now_s() - g_t0_wall < rel) {
        /* queue empty: the caller should wait on the receive event / fd, which the
           ticker thread signals when this frame becomes due. */
        drain_rx();
        return PCAN_ERROR_QRCVEMPTY;
    }
    g_next++;
    msg->ID = f->id;
    msg->MSGTYPE = f->ext ? PCAN_MESSAGE_EXTENDED : PCAN_MESSAGE_STANDARD;
    msg->LEN = f->len;
    memcpy(msg->DATA, f->data, 8);
    if (ts) {
        /* device timestamp = file time, loops appended back to back */
        double dev = (f->t - g_t0_file) + g_loop * (g_frames[g_count-1].t - g_t0_file + 0.001);
        uint64_t us = (uint64_t)(dev * 1e6 + 0.5);
        uint64_t ms = us / 1000;
        ts->micros = (uint16_t)(us % 1000);
        ts->millis = (uint32_t)(ms & 0xFFFFFFFFu);
        ts->millis_overflow = (uint16_t)(ms >> 32);
    }
    return PCAN_ERROR_OK;
}

EXPORT TPCANStatus PCAN_API CAN_GetValue(TPCANHandle Channel, TPCANParameter Parameter, void *Buffer, uint32_t Len)
{
    (void)Channel;
    switch (Parameter) {
    case PCAN_RECEIVE_EVENT:
#ifndef _WIN32
        /* burst mode: the pipe always holds a byte, so select()/poll() return at once.
           realtime mode: the ticker thread writes a byte whenever a frame becomes due. */
        if (Len >= sizeof(int)) { *(int *)Buffer = g_pipe[0]; return PCAN_ERROR_OK; }
#endif
        return PCAN_ERROR_ILLPARAMTYPE;
    case PCAN_API_VERSION:
    case PCAN_CHANNEL_VERSION:
        if (Len) { strncpy((char *)Buffer, "4.9.0.942", Len); ((char *)Buffer)[Len - 1] = 0; }
        return PCAN_ERROR_OK;
    case PCAN_CHANNEL_CONDITION:
        if (Len >= 4) *(uint32_t *)Buffer = 0x01;      /* PCAN_CHANNEL_AVAILABLE */
        return PCAN_ERROR_OK;
    default:
        if (Len >= 4) *(uint32_t *)Buffer = 0;         /* generic "off/zero" answer */
        return PCAN_ERROR_OK;
    }
}

EXPORT TPCANStatus PCAN_API CAN_SetValue(TPCANHandle Channel, TPCANParameter Parameter, void *Buffer, uint32_t Len)
{
    (void)Channel; (void)Buffer; (void)Len;
#ifdef _WIN32
    if (Parameter == PCAN_RECEIVE_EVENT && Len >= sizeof(HANDLE)) { g_event = *(HANDLE *)Buffer; if (g_event && !g_realtime) SetEvent(g_event); }
#else
    (void)Parameter;
#endif
    return PCAN_ERROR_OK;
}

EXPORT TPCANStatus PCAN_API CAN_GetErrorText(TPCANStatus Error, uint16_t Language, char *Buffer)
{
    (void)Language;
    const char *s = "pcan_sim: unknown error";
    switch (Error) {
        case PCAN_ERROR_OK: s = "OK"; break;
        case PCAN_ERROR_QRCVEMPTY: s = "receive queue empty"; break;
        case PCAN_ERROR_ILLHW: s = "pcan_sim: could not load PCAN_SIM_FILE"; break;
        case PCAN_ERROR_INITIALIZE: s = "channel not initialized"; break;
    }
    strcpy(Buffer, s);
    return PCAN_ERROR_OK;
}
