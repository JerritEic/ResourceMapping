from src.PerformanceReport.Metrics import Metric
import psutil
import pandas as pd
from src.PerformanceReport.Component import Component


# Collects hardware metrics system wide and for specified components
class HardwareMetrics(Metric):
    def __init__(self, components: [Component] = None):
        super().__init__()
        self.components = components

    # Gets report of hardware stats that do change, eg cpu percentage
    def run(self):
        # collect global cpu percentage, first call will return a zero!
        cpu_global = psutil.cpu_percent(interval=None, percpu=False)
        #return as dataframe
        return
