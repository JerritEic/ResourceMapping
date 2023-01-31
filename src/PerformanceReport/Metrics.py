import datetime
import threading


class MetricCollector(threading.Thread):
    components = None

    def __init__(self):
        super().__init__()

    def run(self):
        pass
