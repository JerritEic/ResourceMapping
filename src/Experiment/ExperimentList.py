from src.Experiment.DebugExperiment import DebugExperiment
from src.Experiment.LocalToCloudExperiment import LocalToCloudExperiment


def get_experiment_by_name(name):
    if name == LocalToCloudExperiment.experiment_name:
        return LocalToCloudExperiment()
    elif name == DebugExperiment.experiment_name:
        return DebugExperiment()
    else:
        return None
