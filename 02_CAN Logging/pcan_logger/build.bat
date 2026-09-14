@echo off
REM build.bat -- build the PCAN loggers on Windows.
REM
REM Run from an "x64 Native Tools Command Prompt for VS" so that cl.exe is on the PATH.
REM
REM   build.bat            build pcan_logger.exe against the real PCANBasic.lib/.dll
REM                        (copy PCANBasic.lib and PCANBasic.dll from the PCAN-Basic package,
REM                         folder x64, into this directory first)
REM   build.bat sim        build the simulator PCANBasic.dll in pcan_sim\ and link the logger to it
REM   build.bat rust       build the Rust logger with cargo (needs rustup + the MSVC toolchain)
REM
REM With MinGW (gcc) instead of MSVC, use:
REM   gcc -O2 -o pcan_logger.exe pcan_logger.c -L. -lPCANBasic
REM   gcc -O2 -shared -o pcan_sim\PCANBasic.dll pcan_sim\pcan_sim.c

if "%1"=="sim" goto sim
if "%1"=="rust" goto rust

echo Building pcan_logger.exe against PCANBasic.lib ...
cl /nologo /O2 /W3 pcan_logger.c PCANBasic.lib
goto end

:sim
echo Building the simulator PCANBasic.dll ...
cl /nologo /O2 /W3 /LD pcan_sim\pcan_sim.c /Fe:pcan_sim\PCANBasic.dll /Fo:pcan_sim\pcan_sim.obj
echo Building pcan_logger_sim.exe linked to the simulator ...
cl /nologo /O2 /W3 pcan_logger.c pcan_sim\PCANBasic.lib /Fe:pcan_logger_sim.exe
echo.
echo NOTE: Windows loads PCANBasic.dll from the .exe's folder first, then the PATH.
echo       To run against the simulator:   set PATH=%CD%\pcan_sim;%PATH%
echo       To run against real hardware:   make sure the PEAK driver's DLL wins instead.
goto end

:rust
echo Building the Rust logger ...
cd rust
if "%PCAN_LIB_DIR%"=="" echo (PCAN_LIB_DIR not set: linking against PCANBasic.lib on the default library path)
cargo build --release
cd ..

:end
