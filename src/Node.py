import selectors
import threading
from queue import Queue
from src.NetProtocol.Message import Message
from src.NetworkGraph.NetworkGraph import NetworkGraph
from src.Utility.NetworkUtilities import get_my_ip


class Node:
    uuid = None
    node_graph = None
    net_graph: NetworkGraph = None

    def __init__(self):
        self.sel = selectors.DefaultSelector()
        self.receive_queue: "Queue[Message]" = Queue()
        self.termination_event = threading.Event()
        ip = get_my_ip()
        self.ip = ip
