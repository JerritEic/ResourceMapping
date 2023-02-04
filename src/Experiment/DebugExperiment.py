import logging
import time
from typing import TYPE_CHECKING

from src.Experiment.Experiment import Experiment
from src.Experiment.Policy.CPUPolicy import CPUPolicy
from src.NetProtocol.Message import Message
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNode
from src.app.Component import Component


class DebugExperiment(Experiment):
    experiment_name = "DebugExperiment"
    sampling_frequency = 1
    _local_client_uuid = None

    def __init__(self):
        self.policy = CPUPolicy()

    # Perform local and remote component setup steps
    def setup(self, net_graph: NetworkGraph, message_handler):
        self.net_graph = net_graph
        self.message_handler = message_handler
        # Check there are enough clients for experiment
        start_t = time.time()
        while True:
            connected_nodes = self.net_graph.get_all_connected_node_uuids_self()
            if len(connected_nodes) >= 1:
                break
            if time.time() - start_t > 20:
                logging.error(f"Not enough clients connected for experiment, quiting.")
                return False
            self.message_handler.read_messages()

        node_1 = self.net_graph.get_node(connected_nodes[0])

        if not self._start_game_clients(node_1):
            return False

        return True


    def _start_game_clients(self, node_1: NetworkNode):
        comp_dict = dict(components=["game-client"], component_actions=['start'], pids=[-1])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = node_1.conn_handler.send_message_and_wait_response(message, yield_message=True)

        start_t = time.time()
        while True:
            self.message_handler.read_messages()
            if future1.is_set():
                break
            if time.time() - start_t > 50:
                logging.error(f"Timeout on launching game clients!")
                return False
        resp_1 = future1.get_message().content.request
        if resp_1['action'] != RequestType.COMPONENT:
            logging.error(f"Failed to start game client components.")
            return False
        node_1.add_known_component(
            Component(pid=resp_1['results'][0], associated_client_uuid=node_1.conn_handler.peer_uuid, name="game-client"))
        return True

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
