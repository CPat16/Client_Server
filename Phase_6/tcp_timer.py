from threading import Thread
from time import time, sleep
import sys

class Timer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.__time_limit = 0
        self.__stop = False
        self.__kill = False
        self.__exc = False

    def set_time(self, time_limit):
        self.__time_limit = time_limit

    def stop(self):
        self.__stop = True
    
    def restart(self, time_limit=None):
        self.__stop = False
        if time_limit != None:
            self.__time_limit = time_limit
        self.__exc = False
        self.start_time = time()

    def get_exception(self):
        return self.__exc
    
    def kill(self):
        self.__kill = True

    def run(self):
        self.start_time = time()
        while not self.__kill:
            if not self.__stop:
                elapsed = time() - self.start_time
                if elapsed >= self.__time_limit:
                    self.__stop = True
                    self.__exc = True
            else:
                pass    # timer stopped, do nothing

            sleep(0.0001)   # needed to allow other threads to run

        print("Timer killed")
