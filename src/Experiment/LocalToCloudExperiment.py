import logging
import time

from src.Experiment.Experiment import Experiment
from src.Experiment.Policy.DebugPolicy import DebugPolicy
from src.Experiment.Policy.Policy import DebugPolicyAction, StartComponentAction, StopComponentAction
from src.NetProtocol.Message import Message
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph
from src.Utility.NetworkUtilities import get_my_ip
from src.app.Component import Component


class LocalToCloudExperiment(Experiment):
    experiment_name = "LocalToCloud"
    sampling_frequency = 1
    duration = 200
    local_node = None
    remote_node = None
    is_server = False
    _mc_server_port = 25576
    server_ip = None

    # Perform local and remote component setup steps
    def setup(self, net_graph: NetworkGraph, message_handler, termination_event):
        self.is_server = True
        self.net_graph = net_graph
        self.message_handler = message_handler
        # Check there are enough clients for experiment
        start_t = time.time()
        try:
            while True:
                if termination_event.is_set():
                    return False
                connected_nodes = self.net_graph.get_all_connected_nodes_self(active_only=True)
                if len(connected_nodes) >= 2:
                    break
                if time.time() - start_t > 20:
                    logging.error(f"Not enough clients connected for experiment, quiting.")
                    return False
                self.message_handler.read_messages()
        except KeyboardInterrupt:
            logging.info(f"Caught keyboard interrupt, exiting.")
            return False

        # Choose node with to be the starting local client
        if connected_nodes[0].hardware['num_cpu'] <= connected_nodes[1].hardware['num_cpu']:
            self.local_node = connected_nodes[1]
            self.remote_node = connected_nodes[0]
        else:
            self.local_node = connected_nodes[0]
            self.remote_node = connected_nodes[1]

        self.server_ip = self.remote_node.conn_handler.addr[0]
        self.server_ip = self.server_ip if self.server_ip != "127.0.0.1" else get_my_ip()

        # TODO Pairing still buggy, but only needs to be done once between any two nodes...
        #if not self._pair_streaming():
        #    return False
        # start game server on local
        if not self._start_game_server():
            return False
        if not self._start_game_clients():
            return False


        # Setup the policy, in this case hardcoded
        comp_dict1 = dict(components=["stream-server"], component_actions=['start'])
        message1 = Message(content=Request(RequestType.COMPONENT, comp_dict1))

        comp_dict2 = dict(components=["stream-client"], component_actions=['start'],
                         args=[dict(remote_ip=self.remote_node.conn_handler.addr[0])])
        message2 = Message(content=Request(RequestType.COMPONENT, comp_dict2))

        comp_dict3 = dict(components=["game-client"], component_actions=['stop'])
        message3 = Message(content=Request(RequestType.COMPONENT, comp_dict3))

        actions = [dict(action=StartComponentAction(message1, self.remote_node, self.message_handler), time=20),
                   dict(action=StartComponentAction(message2, self.local_node, self.message_handler), time=25),
                   dict(action=StopComponentAction(message3, self.local_node), time=40)]
        self.policy = DebugPolicy(actions)

        return True

    def _pair_streaming(self):
        pin = "2048"
        comp_dict = dict(components=["stream-server"], component_actions=['pair'],
                         args=[dict(pin=pin)])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future2 = self.remote_node.conn_handler.send_message_and_wait_response(message, yield_message=True)
        time.sleep(1)
        comp_dict = dict(components=["stream-client"], component_actions=['pair'],
                         args=[dict(remote_ip=self.server_ip, pin=pin)])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)

        if not self.message_handler.wait_for_responses([future1, future2], 60):
            logging.error(f"Timeout on pairing the game stream server and client!")
            return False

        resp_1 = future1.get_message().content.request['results']
        resp_2 = future2.get_message().content.request['results']
        if resp_1[0] != "PAIRED" or resp_2[0] != "PAIRED":
            logging.error(f"Failed to pair the game stream server and client!")
            return False
        return True

    def _start_game_server(self):
        comp_dict = dict(components=["game-server"], component_actions=[['start', 'status']],
                         args=[[dict(server_port=self._mc_server_port), dict(server_port=self._mc_server_port)]])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)

        if not self.message_handler.wait_for_responses([future1], 30):
            logging.error(f"Timeout on launching game server!")
            return False

        resp_1 = future1.get_message().content.request['results']
        if resp_1[0] == -1 or resp_1[1] != "READY":
            logging.error(f"Failed to start game server component.")
            return False
        self.local_node.add_known_component(
            Component(pid=resp_1[0], name="game-server"))
        return True

    def _start_game_clients(self):
        server_ip = self.local_node.conn_handler.addr[0]
        server_ip = server_ip if server_ip != "127.0.0.1" else get_my_ip()
        comp_dict = dict(components=["game-client"], component_actions=['start'],
                         args=[dict(server_ip=server_ip,
                                    server_port=self._mc_server_port)])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future1 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)
        future2 = self.remote_node.conn_handler.send_message_and_wait_response(message, yield_message=True)

        if not self.message_handler.wait_for_responses([future1, future2], 35):
            logging.error(f"Timeout on launching game clients!")
            return False

        resp_1 = future1.get_message().content.request['results']
        resp_2 = future2.get_message().content.request['results']
        if resp_1[0] == -1 or resp_2[0] == -1:
            logging.error(f"Failed to start game client components.")
            return False
        self.local_node.add_known_component(
            Component(pid=resp_1[0], name="game-client"))
        self.remote_node.add_known_component(
            Component(pid=resp_2[0], name="game-client"))

        # Wait for the clients to connect to the server
        comp_dict = dict(components=["game-server"], component_actions=['status'],
                         args=[dict(server_port=self._mc_server_port, players_connected=2)])
        message = Message(content=Request(RequestType.COMPONENT, comp_dict))
        future3 = self.local_node.conn_handler.send_message_and_wait_response(message, yield_message=True)

        # Player launching and connecting can be extremely slow.
        if not self.message_handler.wait_for_responses([future3], 180):
            logging.error(f"Timeout on clients connecting to server!")
            return False
        logging.info(f"Players have connected to the server.")
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
            if not action.perform_action():
                logging.error(f"{action.name} failed!")

        # query clients for metrics
        # self._retrieve_metrics()

        # check stop conditions
        if not self.local_node.is_active or not self.remote_node.is_active:
            logging.info(f"Experiment peer is now inactive, stopping experiment.")
            return False
        return True

    def end(self):
        if not self.is_server:
            return
        message = Message(content=Request(RequestType.EXIT))
        if self.remote_node is not None:
            self.remote_node.conn_handler.send_message(message)  # don't wait for a response
        if self.local_node is not None:
            self.local_node.conn_handler.send_message(message)
