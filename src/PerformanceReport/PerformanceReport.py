from NetworkMetrics import *
from HardwareMetrics import *
from ApplicationMetrics import *


# Aggregate report of network, hardware, and application metrics
class PerformanceReport:
    def __init__(self, nodeName="error"):
        self.nodeName = nodeName
