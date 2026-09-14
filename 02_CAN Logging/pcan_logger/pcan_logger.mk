# pcan_logger.mk -- build recipe for the PCAN logger comparison (Linux / macOS / MinGW)
#
#   make -f pcan_logger.mk          build the C logger against the real PCAN-Basic library (-lpcanbasic)
#   make -f pcan_logger.mk sim      build the hardware-free simulator library and link the C logger to it
#   make -f pcan_logger.mk rust     build the Rust logger (cargo) -- uses PCAN_LIB_DIR if set
#   make -f pcan_logger.mk clean
#
# (The file is not called Makefile so it can be written through the Cowork file bridge; copy or
#  symlink it to Makefile if you prefer plain `make`.)
#
# On Windows use build.bat (MSVC) instead.

CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra
SIMDIR   = pcan_sim

.PHONY: all sim rust clean

all: pcan_logger

pcan_logger: pcan_logger.c pcan_basic_min.h
	$(CC) $(CFLAGS) -o $@ pcan_logger.c -lpcanbasic

# --- hardware-free build: replays a candump file through the PCAN-Basic API ----
$(SIMDIR)/libpcanbasic.so: $(SIMDIR)/pcan_sim.c pcan_basic_min.h
	$(CC) $(CFLAGS) -shared -fPIC -Wl,-soname,libpcanbasic.so -o $@ $(SIMDIR)/pcan_sim.c -lpthread

pcan_logger_sim: pcan_logger.c pcan_basic_min.h $(SIMDIR)/libpcanbasic.so
	$(CC) $(CFLAGS) -o $@ pcan_logger.c -L$(SIMDIR) -lpcanbasic -Wl,-rpath,'$$ORIGIN/$(SIMDIR)'

sim: pcan_logger_sim

rust:
	cd rust && cargo build --release

clean:
	rm -f pcan_logger pcan_logger_sim $(SIMDIR)/libpcanbasic.so
	cd rust && cargo clean
