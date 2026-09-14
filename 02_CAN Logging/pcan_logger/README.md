# PCAN logger comparison: C, Rust and Python

Companion code for the *Is a Compiled Logger Faster?* section of
`CAN Log File Analysis Part 2.ipynb`.

The C and Rust programs here and the two Python loggers defined in the notebook
all do the same job -- read frames from a PEAK PCAN adapter through the PCAN-Basic
API and write them in `candump` format -- and report the same statistics so the
notebook can compare them. The notebook builds these files itself (`build_loggers()`).

| File | What it is |
|------|-----------|
| `pcan_logger.c` | C logger. Event-driven receive, 1 MiB output buffer, hand-rolled hex formatting. |
| `pcan_basic_min.h` | Our own declarations of the handful of PCAN-Basic functions used. `-DHAVE_PCANBASIC_H` uses PEAK's official `PCANBasic.h` instead. |
| `rust/` | Rust logger (`cargo build --release`). Same functions, declared in an `extern "system"` block -- no crates. |
| `pcan_sim/pcan_sim.c` | A **simulator** of `PCANBasic.dll` / `libpcanbasic.so` that replays a candump file. Lets every logger run and be timed on a machine with no adapter. |
| `Makefile`, `build.bat` | Build recipes for Linux/MinGW and MSVC. |

## Quick start (no hardware)

Run the *Is a Compiled Logger Faster?* section of the Part 2 notebook, or by hand:

```
make -f pcan_logger.mk sim                  # simulator library + C logger linked to it
PCAN_LIB_DIR=$PWD/pcan_sim make -f pcan_logger.mk rust
PCAN_SIM_FILE=../candump_kw_drive.txt LD_LIBRARY_PATH=pcan_sim ./pcan_logger_sim -n can1 -o test.log
```

## Against a real adapter

Install the PCAN-Basic package from PEAK (Windows: `PCANBasic.dll`, `PCANBasic.lib`,
`PCANBasic.h`; Linux: `libpcanbasic.so` from "PCAN-Basic for Linux" plus the `pcan`
kernel driver or the mainline `peak_usb` driver with the PCAN-Basic netdev build).

```
make                                        # Linux: C logger against -lpcanbasic
build.bat                                   # Windows (MSVC), with PCANBasic.lib in this folder
cd rust && cargo build --release            # Rust, library on the default search path
pcan_logger -c PCAN_USBBUS1 -b 250000 -t 30 -o c.log
rust/target/release/pcan_logger_rs -c PCAN_USBBUS1 -b 250000 -t 30 -o rust.log
```

Both compiled loggers accept the same flags:

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
