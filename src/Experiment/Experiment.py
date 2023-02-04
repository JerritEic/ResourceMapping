
# Defines behaviour of Resource Mapping server
from src.Experiment.Policy.Policy import Policy


class Experiment:
    policy: Policy = None
    experiment_name = "Unknown"
    net_graph = None
    message_handler = None
    sampling_frequency = -1

    # Perform local and remote component setup steps
    def setup(self, net_graph, message_handler):
        self.net_graph = net_graph
        self.net_graph = message_handler

    def _retrieve_metrics(self):
        pass

    # One iteration of experiment loop
    def experiment_step(self):
        pass

