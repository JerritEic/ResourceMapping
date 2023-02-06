import logging
import time
from typing import TYPE_CHECKING

from src.Experiment.Experiment import Experiment
from src.Experiment.Policy.CPUPolicy import CPUPolicy
from src.Experiment.Policy.DebugPolicy import DebugPolicy
from src.Experiment.Policy.Policy import DebugPolicyAction
from src.NetProtocol.Message import Message
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNode
from src.app.Component import Component


class DebugExperiment(Experiment):
    experiment_name = "DebugExperiment"
    sampling_frequency = 1

    def __init__(self):
        # Behaviour of policy pre-defined here
        actions = [dict(action=DebugPolicyAction(), time=20)]
        self.policy = DebugPolicy(actions)
        self.node_1 = None

    # Perform local and remote component setup steps
    def setup(self, net_graph: NetworkGraph, message_handler):
        self.net_graph = net_graph
        self.message_handler = message_handler
        # Check there are enough clients for experiment
        start_t = time.time()
        while True:
            connected_nodes = self.net_graph.get_all_connected_nodes_self(active_only=True)
            if len(connected_nodes) >= 1:
                break
            if time.time() - start_t > 20:
                logging.error(f"Not enough clients connected for experiment, quiting.")
                return False
            self.message_handler.read_messages()

        self.node_1 = connected_nodes[0]
        if not self._start_game_server():
            return False

        #if not self._start_game_clients():
        #    return False
        return True

    def _start_game_server(self):
        comp_dict = dict(components=["game-server"], component_actions=['start'], pids=[-1])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.node_1.conn_handler.send_message_and_wait_response(message, yield_message=True)
        start_t = time.time()
        while True:
            self.message_handler.read_messages()
            if future1.is_set():
                break
            if time.time() - start_t > 30:
                logging.error(f"Timeout on launching game clients!")
                return False
        resp_1 = future1.get_message().content.request
        if resp_1['action'] != RequestType.COMPONENT:
            logging.error(f"Failed to start game server component.")
            return False
        self.node_1.add_known_component(
            Component(pid=resp_1['results'][0], name="game-server"))
        return True

    def _start_game_clients(self):
        comp_dict = dict(components=["game-client"], component_actions=['start'], pids=[-1])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.node_1.conn_handler.send_message_and_wait_response(message, yield_message=True)

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
        self.node_1.add_known_component(
            Component(pid=resp_1['results'][0], name="game-client"))
        return True

    def _retrieve_metrics(self):
        metric_dict = dict(metrics=["hardware_metrics"], period=self.sampling_frequency)
        message = Message(content=Request(RequestType.METRIC, metric_dict))
        self.node_1.conn_handler.send_message(message)

    # One iteration of experiment loop
    def experiment_step(self):
        # check policy conditions
        actions = self.policy.check([self.node_1])

        # perform policy actions
        for action in actions:
            action.perform_action()

        # query clients for metrics
        self._retrieve_metrics()

        # check stop conditions
        if not self.node_1.is_active:
            logging.info(f"Experiment peer is now inactive, stopping experiment.")
            return False
        return True
