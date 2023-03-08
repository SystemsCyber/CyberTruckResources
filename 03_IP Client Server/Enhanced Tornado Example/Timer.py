from datetime import datetime
import logging
import sys

class Timer(object):

    def __init__(self, counterName, logger=None, loglevel=logging.INFO, blockSize=sys.maxsize):
        self.counterName = counterName
        self.logger = logger if logger else logging.getLogger(__name__)
        self.loglevel = loglevel
        self.t0 = datetime.now()
        self.t1 = datetime.now()
        self.deltat = self.t1 - self.t0
        self.counter = 1
        self.blockSize = blockSize

    #
    # Context Manager implementation
    #

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()
        self.report()

    def start(self):
        self.t0 = datetime.now()
        self.counter = 1

    def stop(self):
        self.t1 = datetime.now()

    def incr(self):
        self.counter += 1
        if (self.counter % self.blockSize) == 0:
            self.t1 = datetime.now()
            self.report()

    def setCount(self, count):
        self.counter = count

    def report(self):
        self.deltat = self.t1 - self.t0
        secs = self.deltat.total_seconds()

        secs = secs if secs != 0 else 1
        self.logger.log(self.loglevel, "{0}: {1}, secs: {2}, {0} per second: {3}"
                        .format(self.counterName, self.counter, secs, self.counter / secs))

