from Metrics import *
from Component import Component


# Collects hardware metrics
class HardwareMetrics(MetricCollector):
    def __init__(self, components: [Component]):
        self.components = components
        super().__init__()

    def run(self):
        pass

