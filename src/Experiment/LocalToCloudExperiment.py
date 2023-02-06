import logging
import time

from src.Experiment.Experiment import Experiment
from src.Experiment.Policy.DebugPolicy import DebugPolicy
from src.Experiment.Policy.Policy import DebugPolicyAction
from src.NetProtocol.Message import Message
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph
from src.app.Component import Component


class LocalToCloudExperiment(Experiment):
    experiment_name = "LocalToCloud"
    sampling_frequency = 1
    local_node = None
    remote_node = None

    def __init__(self):
        # After x seconds, start the remote client
        # wait for it be ready
        # start local video stream
        # stop local client component
        actions = [dict(action=DebugPolicyAction(), time=20)]
        self.policy = DebugPolicy(actions)

    # Perform local and remote component setup steps
    def setup(self, net_graph: NetworkGraph, message_handler):
        self.net_graph = net_graph
        self.message_handler = message_handler
        # Check there are enough clients for experiment
        start_t = time.time()
        while True:
            connected_nodes = self.net_graph.get_all_connected_nodes_self(active_only=True)
            if len(connected_nodes) >= 2:
                break
            if time.time() - start_t > 20:
                logging.error(f"Not enough clients connected for experiment, quiting.")
                return False
            self.message_handler.read_messages()

        # Choose node with less resources to be the starting local client
        node_1 = self.net_graph.get_node(connected_nodes[0])
        node_2 = self.net_graph.get_node(connected_nodes[1])
        if node_1.hardware['num_cpu'] >= node_2.hardware['num_cpu']:
            self.local_node = connected_nodes[1]
            self.remote_node = connected_nodes[0]
        else:
            self.local_node = connected_nodes[0]
            self.remote_node = connected_nodes[1]
        if not self._start_game_server():
            return False
        if not self._start_game_clients():
            return False

    def _start_game_server(self):
        comp_dict = dict(components=["game-server"], component_actions=['start'], pids=[-1])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)
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
        self.local_node.add_known_component(
            Component(pid=resp_1['results'][0], name="game-server"))
        return True

    def _start_game_clients(self):
        comp_dict = dict(components=["game-client"], component_actions=['start'], pids=[-1])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)
        future2 = self.remote_node.conn_handler.send_message_and_wait_response(message, yield_message=True)

        start_t = time.time()
        while True:
            self.message_handler.read_messages()
            if future1.is_set() and future2.is_set():
                break
            if time.time() - start_t > 30:
                logging.error(f"Timeout on launching game clients!")
                return False
        resp_1 = future1.get_message().content.request
        resp_2 = future2.get_message().content.request
        if resp_1['action'] != RequestType.COMPONENT or resp_2['action'] != RequestType.COMPONENT:
            logging.error(f"Failed to start game client components.")
            return False
        self.local_node.add_known_component(
            Component(pid=resp_1['results'][0], name="game-client"))
        self.remote_node.add_known_component(
            Component(pid=resp_2['results'][0], name="game-client"))
        return True

    def _retrieve_metrics(self):
        metric_dict = dict(metrics=["hardware_metrics"], period=self.sampling_frequency)
        message = Message(content=Request(RequestType.METRIC, metric_dict))
        self.local_node.conn_handler.send_message(message)
        self.remote_node.conn_handler.send_message(message)

    # One iteration of experiment loop
    def experiment_step(self):
        # check policy conditions
        actions = self.policy.check([self.local_node, self.remote_node])

        # perform policy actions
        for action in actions:
            action.perform_action()

        # query clients for metrics
        self._retrieve_metrics()

        # check stop conditions
        if not self.local_node.is_active or not self.remote_node.is_active:
            logging.info(f"Experiment peer is now inactive, stopping experiment.")
            return False
        return True
