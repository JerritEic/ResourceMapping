import uuid
from enum import Enum
import logging


class NetworkNodeType(Enum):
    UNKNOWN = 0  # Not yet discovered
    CLIENT = 1  # Client facing, e.g. a player endpoint
    CLOUD = 2  # Hardware that isn't client facing


# Constructs a graph of the network resources
class NetworkGraph:
    _server = None
    _nodes = dict()          # UUID -> Node Objects
    _connections = dict()    # UUID -> Connection Objects
    _edges = dict()          # UUID _nodes -> UUID _connections

    def __init__(self, server_ip):
        self._server = self.new_node("server", server_ip, NetworkNodeType.CLOUD)

    def get_server(self):
        return self.get_node(self._server)

    # Create new node and add it to the dict
    def new_node(self, name, ip, node_type):
        node = NetworkNode(name, ip, node_type)
        self._nodes[node.uuid] = node
        self._edges[node.uuid] = []
        return node.uuid

    # Create a new connection object and add it to both dict entries
    def new_connection(self, v1_uuid, v2_uuid):
        # Check these nodes exist
        if not self._nodes[v1_uuid]:
            logging.error(f"No node with uuid: {v1_uuid}")
            return
        if not self._nodes[v2_uuid]:
            logging.error(f"No node with uuid: {v2_uuid}")
            return

        # Check connection not already made, using uuid combination as a per-connection uuid
        conn_uuid = v1_uuid + v2_uuid
        if self._connections[conn_uuid]:
            logging.warning(f"Connection already exists between {self._nodes[v1_uuid].name} and {self._nodes[v1_uuid].name}")

        # Make and store the edge
        connection = NetworkEdge(v1_uuid, v2_uuid)
        self._connections[connection.conn_uuid] = connection
        self._edges[v1_uuid] = self._edges[v1_uuid].append(connection.conn_uuid)
        self._edges[v2_uuid] = self._edges[v2_uuid].append(connection.conn_uuid)

    def get_node(self, node_uuid):
        if self._nodes[node_uuid]:
            return self._nodes[node_uuid]
        else:
            logging.error(f"No node with uuid: {node_uuid}")
            return None

    def get_connection_by_uuid(self, conn_uuid):
        if self._connections[conn_uuid]:
            return self._connections[conn_uuid]
        else:
            logging.error(f"No connection with uuid: {conn_uuid}")
            return None

    def get_connection_by_nodes(self, v1_uuid, v2_uuid):
        # Check these _nodes exist
        if not self._nodes[v1_uuid]:
            logging.error(f"No node with uuid: {v1_uuid}")
            return
        if not self._nodes[v2_uuid]:
            logging.error(f"No node with uuid: {v2_uuid}")
            return

        # Check connection not already made, using uuid combination as a per-connection uuid
        return self.get_connection_by_uuid(v1_uuid + v2_uuid)


# Represents connection between host
class NetworkEdge:
    conn_uuid = None
    v1_uuid = None
    v2_uuid = None

    def __init__(self, v1_uuid, v2_uuid):
        self.v1_uuid = v1_uuid
        self.v2_uuid = v2_uuid
        self.conn_uuid = v1_uuid + v2_uuid


# Represents a host on the network
class NetworkNode:
    uuid = ""
    name = "unknown"
    ip = "0.0.0.0"  # IP starts unknown
    type = NetworkNodeType.UNKNOWN
    components = set()

    def __init__(self, name, ip, node_type):
        self.name = name
        self.ip = ip
        self.type = node_type
        self.uuid = uuid.uuid4()
