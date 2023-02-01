import datetime
import threading


# Parent class for metric collectors
class Metric(threading.Thread):
    def __init__(self):
        super().__init__()

    def run(self):
        pass

# Manages running metric collector threads
class MetricCollector:
    def __init__(self, metric_thread: Metric):
        self.metric_thread = metric_thread

    def collect(self):
        self.metric_thread.start()

    def halt(self):
        self.metric_thread.join()
