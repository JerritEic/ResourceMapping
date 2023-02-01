import uuid
from enum import Enum
import logging


class NetworkNodeType(Enum):
    UNKNOWN = 0  # Not yet discovered
    CLIENT = 1  # Client facing, e.g. a player endpoint
    CLOUD = 2  # Hardware that isn't client facing


# Constructs a graph of the network resources that this node knows about
class NetworkGraph:
    _server = None
    _nodes = dict()          # UUID -> Node Objects
    _connections = dict()    # UUID -> Connection Objects
    _edges = dict()          # UUID _nodes -> UUID _connections

    def __init__(self, name, own_addr, own_type, own_uuid, hardware):
        self._own_addr = own_addr
        self._own_uuid = own_uuid
        self.new_node(name, own_addr, own_type, own_uuid, hardware)

    def set_server(self, server_uuid):
        if server_uuid not in self._nodes:
            logging.error(f"No node with uuid: {server_uuid}")
            return
        self._server = server_uuid

    def get_server(self):
        return self.get_node(self._server)

    # Create new node and add it to the dict
    def new_node(self, name, addr, node_type, node_uuid, hardware=None):
        node = NetworkNode(name, addr, node_uuid, node_type, hardware)
        self._nodes[node.uuid] = node
        self._edges[node.uuid] = []
        return node.uuid

    # Create a new connection from this node to another
    def new_connection_to_self(self, other_uuid):
        self.new_connection(self._own_uuid, other_uuid)

    # Create a new connection object and add it to both dict entries
    def new_connection(self, v1_uuid: uuid.UUID, v2_uuid: uuid.UUID):
        # Check these nodes exist
        if v1_uuid not in self._nodes:
            logging.error(f"No node with uuid: {v1_uuid}")
            return
        if v2_uuid not in self._nodes:
            logging.error(f"No node with uuid: {v2_uuid}")
            return

        # Check connection not already made, using uuid combination as a per-connection uuid
        conn_uuid = v1_uuid.bytes + v2_uuid.bytes
        if conn_uuid in self._connections:
            logging.warning(f"Connection already exists between {self._nodes[v1_uuid].name} and {self._nodes[v1_uuid].name}")

        # Make and store the edge
        connection = NetworkEdge(v1_uuid, v2_uuid)
        self._connections[connection.conn_uuid] = connection
        self._edges[v1_uuid] = self._edges[v1_uuid].append(connection.conn_uuid)
        self._edges[v2_uuid] = self._edges[v2_uuid].append(connection.conn_uuid)

    def get_node(self, node_uuid):
        if node_uuid in self._nodes:
            return self._nodes[node_uuid]
        else:
            logging.error(f"No node with uuid: {node_uuid}")
            return None

    def get_all_connections_to_node(self, node_uuid):
        if node_uuid not in self._nodes:
            logging.error(f"No node with uuid: {node_uuid}")
            return
        if node_uuid not in self._edges:
            return []
        return self._edges[node_uuid]

    def get_connection_by_conn_uuid(self, conn_uuid):
        if conn_uuid in self._connections:
            return self._connections[conn_uuid]
        else:
            logging.error(f"No connection with uuid: {conn_uuid}")
            return None

    def get_connection_by_nodes(self, v1_uuid, v2_uuid):
        # Check these _nodes exist
        if v1_uuid not in self._nodes:
            logging.error(f"No node with uuid: {v1_uuid}")
            return
        if v2_uuid not in self._nodes:
            logging.error(f"No node with uuid: {v2_uuid}")
            return

        # Check connection not already made, using uuid combination as a per-connection uuid
        return self.get_connection_by_conn_uuid(v1_uuid + v2_uuid)


# Represents connection between host
class NetworkEdge:
    conn_uuid = None
    v1_uuid = None
    v2_uuid = None

    def __init__(self, v1_uuid: uuid.UUID, v2_uuid: uuid.UUID):
        self.v1_uuid = v1_uuid
        self.v2_uuid = v2_uuid
        self.conn_uuid = v1_uuid.bytes + v2_uuid.bytes


# Represents a host on the network
class NetworkNode:
    uuid = ""
    name = "unknown"
    addr = ("0.0.0.0", 42)  # IP starts unknown
    type = NetworkNodeType.UNKNOWN
    components = set()  # Known resources

    def __init__(self, name, addr, node_uuid, node_type, hardware=None):
        self.name = name
        self.addr = addr
        self.uuid = node_uuid
        self.type = node_type
        self.hardware = None
