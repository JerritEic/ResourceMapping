import logging
from pynvml import *

from psutil import NoSuchProcess, AccessDenied

from src.PerformanceReport.Metrics import Metric
import psutil
from src.PerformanceReport.Component import Component


# Collects hardware metrics system wide and for specified components
class HardwareMetrics(Metric):
    _db_sub_query = "SELECT pid FROM components WHERE pid = :pid"
    db_query_template = f"INSERT INTO hardware_metrics VALUES (:timestamp, ({_db_sub_query}), :cpu, :memory)"

    def __init__(self, components: [Component], elapsed_time):
        super().__init__(components, elapsed_time)
        self.name = "HardwareMetrics"

    # Gets report of hardware stats that do change, eg cpu percentage
    def run(self):
        # collect global cpu percentage, first call will return a zero!

        cpu_global = psutil.cpu_percent(interval=None, percpu=False)
        mem_global = psutil.virtual_memory().used
        results_dicts = [dict(timestamp=self.elapsed_time, pid=-1,
                              cpu=cpu_global, memory=mem_global)]
        for comp in self.components:
            try:
                if psutil.pid_exists(comp.pid):
                    p = psutil.Process(comp.pid)
                    # can be > 100.0 in case of a process running multiple threads on different CPU cores.
                    cpu = p.cpu_percent(interval=None)
                    # RSS is platform portable, but not the best measure of memory usage
                    mem = p.memory_info().rss
                    results_dicts.append(dict(timestamp=self.elapsed_time, pid=comp.pid,
                                              cpu=cpu, memory=mem))
            except NoSuchProcess:
                logging.error(f"PID {comp.pid} is not an active process...")
            except AccessDenied:
                logging.error(f"PID {comp.pid} access denied")
        # result to dict, could also be dataframe
        self.result = results_dicts
