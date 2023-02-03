
# Defines behaviour of Resource Mapping server
from src.Experiment.LocalToCloudExperiment import LocalToCloudExperiment
from src.Experiment.Policy.Policy import Policy


class Experiment:
    policy: Policy = None
    experiment_name = "Unknown"
    net_graph = None
    sampling_frequency = -1

    # Perform local and remote component setup steps
    def setup(self, net_graph):
        self.net_graph = net_graph

    def _retrieve_metrics(self):
        pass

    # One iteration of experiment loop
    def experiment_step(self):
        pass


def get_experiment_by_name(name):
    if name == LocalToCloudExperiment.experiment_name:
        return LocalToCloudExperiment()
    else:
        return None
