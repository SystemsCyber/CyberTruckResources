# PCAN logger comparison: C, Rust and Python

A stand-alone side project for the CAN Logging module: is a logger written in a
compiled language faster than one written in Python?

All four programs do the same job -- read frames from a PEAK PCAN adapter
through the PCAN-Basic API and write them in `candump` format -- and all
print the same one-line JSON summary on exit so they can be compared.

| File | What it is |
|------|-----------|
| `pcan_logger.c` | C logger. Event-driven receive, 1 MiB output buffer, hand-rolled hex formatting. |
| `pcan_basic_min.h` | Our own declarations of the handful of PCAN-Basic functions used. `-DHAVE_PCANBASIC_H` uses PEAK's official `PCANBasic.h` instead. |
| `rust/` | Rust logger (`cargo build --release`). Same functions, declared in an `extern "system"` block -- no crates. |
| `pcan_logger.py` | Python logger with two back ends: `--backend ctypes` (same raw API) and `--backend python-can`. |
| `pcan_sim/pcan_sim.c` | A **simulator** of `PCANBasic.dll` / `libpcanbasic.so` that replays a candump file. Lets every logger run and be timed on a machine with no adapter. |
| `benchmark_loggers.py` | Builds everything and runs the loggers against the simulator (or `--hardware`) and prints a comparison table. |
| `pcan_logger.mk`, `build.bat` | Build recipes for Linux/MinGW (`make -f pcan_logger.mk sim`) and MSVC. |

## Quick start (no hardware)

```
python benchmark_loggers.py                 # builds sim + C + Rust, runs all four loggers
```

## Against a real adapter

Install the PCAN-Basic package from PEAK (Windows: `PCANBasic.dll`, `PCANBasic.lib`,
`PCANBasic.h`; Linux: `libpcanbasic.so` from "PCAN-Basic for Linux" plus the `pcan`
kernel driver or the mainline `peak_usb` driver with the PCAN-Basic netdev build).

```
make -f pcan_logger.mk                      # Linux: C logger against -lpcanbasic
build.bat                                   # Windows (MSVC), with PCANBasic.lib in this folder
cd rust && cargo build --release            # Rust, library on the default search path
python benchmark_loggers.py --hardware -c PCAN_USBBUS1 -b 250000 --seconds 30
```

Every logger accepts the same flags:

```
-c PCAN_USBBUS1   channel      -b 250000   bit rate     -t 30   seconds to run (0 = Ctrl-C)
-n can1           channel label in the log   -o file.log  output ('-' = stdout)   -q  count only
```

## Simulator environment variables

```
PCAN_SIM_FILE=candump_kw_drive.txt   file to replay
PCAN_SIM_MODE=burst|realtime         burst = as fast as the caller reads; realtime = follow the timestamps
PCAN_SIM_SPEED=10                    realtime speed factor
PCAN_SIM_LOOPS=5                     replay the file this many times
PCAN_SIM_EOF_SIGINT=1                send Ctrl-C to the logger when the file runs out
```

Never leave the simulator's `PCANBasic.dll` / `libpcanbasic.so` where a real
installation would be found first.
