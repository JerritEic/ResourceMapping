from src.Experiment.Experiment import Experiment
from src.Experiment.Policy.CPUPolicy import CPUPolicy
from src.NetProtocol.Message import Message
from src.NetProtocol.Request import Request, RequestType


class LocalToCloudExperiment(Experiment):
    experiment_name = "LocalToCloud"
    sampling_frequency = 1

    def __init__(self):
        self.policy = CPUPolicy()

    # Perform local and remote component setup steps
    def setup(self, net_graph):
        self.net_graph = net_graph

    def _retrieve_metrics(self):
        for n_uuid in self.net_graph.get_all_connected_node_uuids_self():
            metric_dict = dict(metrics=["hardware_metrics"], period=self.sampling_frequency)
            message = Message(content=Request(RequestType.METRIC, metric_dict))
            self.net_graph.get_node(n_uuid).conn_handler.send_message(message)

    # One iteration of experiment loop
    def experiment_step(self):
        # check policy conditions

        # perform policy actions

        # query clients for metrics
        self._retrieve_metrics()
