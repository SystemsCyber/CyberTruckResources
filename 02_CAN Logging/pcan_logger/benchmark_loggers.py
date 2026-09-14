#!/usr/bin/env python3
"""
benchmark_loggers.py -- build the C / Rust / Python PCAN loggers and time them.

By default every logger is run against the *simulator* library (pcan_sim), which
replays a candump file through the PCAN-Basic API.  This answers the question
"how much CPU does each implementation spend per frame?" on any computer.  With
--hardware the same loggers are run against a real adapter, one after the other,
for --seconds each (so drive the truck, or replay a log with canplayer/PCAN-View,
while it runs).

    python benchmark_loggers.py                          # simulator, burst + realtime
    python benchmark_loggers.py --file ../candump_kw_drive.txt --loops 10
    python benchmark_loggers.py --hardware -c PCAN_USBBUS1 -b 250000 --seconds 30

Import from a notebook:
    from benchmark_loggers import build_all, run_benchmark
    build_all(); results = run_benchmark()

ENGR 580A2 -- Secure Vehicle and Industrial Networking, Colorado State University
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIMDIR = os.path.join(HERE, "pcan_sim")
WIN = sys.platform.startswith("win")
EXE = ".exe" if WIN else ""


def _run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=True, cwd=kw.pop("cwd", HERE), **kw)


def build_all(verbose=True):
    """Build the simulator, the C logger (linked to the simulator) and the Rust logger.
    Returns a dict of what was built.  Missing compilers are reported, not fatal."""
    built = {"sim": False, "c": False, "rust": False}
    gcc = shutil.which("gcc") or shutil.which("cc")
    cl = shutil.which("cl") if WIN else None
    cargo = shutil.which("cargo")

    # --- simulator library ------------------------------------------------------
    try:
        if WIN and cl:
            _run(["cl", "/nologo", "/O2", "/LD", os.path.join("pcan_sim", "pcan_sim.c"),
                  "/Fe:" + os.path.join("pcan_sim", "PCANBasic.dll"), "/Fo:" + os.path.join("pcan_sim", "pcan_sim.obj")])
            built["sim"] = True
        elif WIN and gcc:
            _run([gcc, "-O2", "-shared", "-o", os.path.join("pcan_sim", "PCANBasic.dll"), os.path.join("pcan_sim", "pcan_sim.c")])
            built["sim"] = True
        elif gcc:
            _run([gcc, "-O2", "-shared", "-fPIC", "-Wl,-soname,libpcanbasic.so",
                  "-o", os.path.join("pcan_sim", "libpcanbasic.so"), os.path.join("pcan_sim", "pcan_sim.c"), "-lpthread"])
            built["sim"] = True
        else:
            print("  no C compiler found (gcc/cl): cannot build the simulator")
    except subprocess.CalledProcessError as e:
        print("  simulator build failed:", e)

    # --- C logger ---------------------------------------------------------------
    if built["sim"]:
        try:
            if WIN and cl:
                _run(["cl", "/nologo", "/O2", "pcan_logger.c", os.path.join("pcan_sim", "PCANBasic.lib"),
                      "/Fe:pcan_logger_sim.exe"])
            elif WIN and gcc:
                _run([gcc, "-O2", "-o", "pcan_logger_sim.exe", "pcan_logger.c", "-Lpcan_sim", "-lPCANBasic"])
            else:
                _run([gcc, "-O2", "-o", "pcan_logger_sim", "pcan_logger.c", "-Lpcan_sim", "-lpcanbasic",
                      "-Wl,-rpath,$ORIGIN/pcan_sim"])
            built["c"] = True
        except subprocess.CalledProcessError as e:
            print("  C logger build failed:", e)

    # --- Rust logger --------------------------------------------------------------
    if cargo and built["sim"]:
        env = dict(os.environ, PCAN_LIB_DIR=SIMDIR)
        try:
            _run(["cargo", "build", "--release", "--quiet"], cwd=os.path.join(HERE, "rust"), env=env)
            built["rust"] = True
        except subprocess.CalledProcessError as e:
            print("  Rust build failed:", e)
    elif not cargo:
        print("  cargo not found: skipping the Rust logger (install from https://rustup.rs)")
    return built


def logger_commands(hardware=False):
    """Return {name: argv} for every logger that exists."""
    cmds = {}
    c_exe = os.path.join(HERE, "pcan_logger" + EXE if hardware else "pcan_logger_sim" + EXE)
    if os.path.exists(c_exe):
        cmds["C"] = [c_exe]
    rs = os.path.join(HERE, "rust", "target", "release", "pcan_logger_rs" + EXE)
    if os.path.exists(rs):
        cmds["Rust"] = [rs]
    py = os.path.join(HERE, "pcan_logger.py")
    cmds["Python (ctypes)"] = [sys.executable, py, "--backend", "ctypes"]
    try:
        import can  # noqa: F401
        cmds["Python (python-can)"] = [sys.executable, py, "--backend", "python-can"]
    except ImportError:
        print("  python-can not installed: pip install python-can")
    return cmds


def run_one(argv, env, seconds=0, quiet=False, label="can1", out=os.devnull):
    cmd = argv + ["-n", label, "-o", out]
    if seconds:
        cmd += ["-t", str(seconds)]
    if quiet:
        cmd += ["-q"]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=HERE)
    for line in reversed(p.stderr.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"{cmd}: no summary line\n{p.stderr}")


def run_benchmark(candump_file=None, loops=5, realtime_speed=10, realtime_seconds=5,
                  hardware=False, channel="PCAN_USBBUS1", bitrate=250000, seconds=30, out=None):
    """Run every available logger and return a list of result dicts.
    Output goes to a real temporary file (not /dev/null) so the cost of writing the
    log to disk is part of the measurement; it is deleted afterwards."""
    import tempfile
    candump_file = candump_file or os.path.join(HERE, "candump_kw_drive.txt")
    tmp = None
    if out is None:
        tmp = tempfile.NamedTemporaryFile(prefix="pcan_bench_", suffix=".log", delete=False)
        tmp.close()
        out = tmp.name
    env = dict(os.environ)
    if not hardware:
        env["PCAN_LIB_DIR"] = SIMDIR
        env["PCAN_SIM_FILE"] = os.path.abspath(candump_file)
        if WIN:
            env["PATH"] = SIMDIR + os.pathsep + env.get("PATH", "")
        else:
            env["LD_LIBRARY_PATH"] = SIMDIR + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    results = []
    for name, argv in logger_commands(hardware).items():
        argv = argv + ["-c", channel, "-b", str(bitrate)]
        if hardware:
            print(f"  {name}: logging {seconds}s from {channel} ...")
            r = run_one(argv, env, seconds=seconds, out=out)
            r.update(logger=name, mode="hardware")
            results.append(r)
            continue
        # burst: how fast can the loop go?  (frames per CPU second)
        e = dict(env, PCAN_SIM_MODE="burst", PCAN_SIM_LOOPS=str(loops))
        r = run_one(argv, e, out=out); r.update(logger=name, mode="burst")
        results.append(r)
        # burst, quiet: receive only, no formatting or file output
        r = run_one(argv, e, quiet=True); r.update(logger=name, mode="burst-quiet")
        results.append(r)
        # realtime at N x speed: does it keep up, and how much CPU does it need?
        e = dict(env, PCAN_SIM_MODE="realtime", PCAN_SIM_SPEED=str(realtime_speed), PCAN_SIM_LOOPS="1000",
                 PCAN_SIM_EOF_SIGINT="0")
        r = run_one(argv, e, seconds=realtime_seconds, out=out); r.update(logger=name, mode=f"realtime x{realtime_speed}")
        results.append(r)
    if tmp:
        try: os.remove(tmp.name)
        except OSError: pass
    return results


def print_table(results):
    print(f"\n{'logger':22s} {'mode':14s} {'frames':>9s} {'elapsed s':>9s} {'CPU s':>7s} {'frames/s':>11s} {'CPU us/frame':>12s} {'overruns':>8s}")
    for r in results:
        print(f"{r['logger']:22s} {r['mode']:14s} {r['frames']:9d} {r['elapsed_s']:9.3f} {r['cpu_s']:7.3f} "
              f"{r['frames_per_s']:11.1f} {r['cpu_us_per_frame']:12.2f} {r['rx_queue_overruns']:8d}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=None, help="candump file to replay through the simulator")
    ap.add_argument("--loops", type=int, default=5)
    ap.add_argument("--speed", type=float, default=10, help="realtime replay speed factor")
    ap.add_argument("--realtime-seconds", type=float, default=5)
    ap.add_argument("--hardware", action="store_true", help="use a real adapter instead of the simulator")
    ap.add_argument("-c", dest="channel", default="PCAN_USBBUS1")
    ap.add_argument("-b", dest="bitrate", type=int, default=250000)
    ap.add_argument("--seconds", type=float, default=30, help="seconds per logger with --hardware")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--json", default=None, help="write results to this JSON file")
    a = ap.parse_args()
    if not a.no_build:
        print("Building ...")
        print(" ", build_all())
    res = run_benchmark(a.file, a.loops, a.speed, a.realtime_seconds, a.hardware, a.channel, a.bitrate, a.seconds)
    print_table(res)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
