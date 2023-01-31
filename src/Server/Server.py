# import src.PerformanceReport.PerformanceReport
from queue import Queue
import traceback
from src.Utility.NetworkUtilities import *
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNodeType
from src.NetProtocol.ConnectionHandler import ConnectionHandler, ConnectionMonitor
from src.NetProtocol.MessageHandler import MessageHandler
from src.NetProtocol.Message import Message
from src.Node import Node
import selectors
import socket
import logging
import threading


class Server(Node):
    def __init__(self, server_config):
        super().__init__()
        self.port = int(server_config['DEFAULT']['port'])
        self.uuid = cached_or_new_uuid(use_cached=True, cache_file="./server_cached_uuid.txt")
        self.net_graph = NetworkGraph("server", (self.ip, self.port), NetworkNodeType.CLOUD, self.uuid)
        self.net_graph.set_server((self.ip, self.port), self.uuid)
        self.connection_monitor = ConnectionMonitor(self.termination_event, self.sel, self.receive_queue)
        self.message_handler = MessageHandler(self.receive_queue, self.termination_event, owner=self)

    def start(self):
        # https://realpython.com/python-sockets/#multi-connection-server
        addr = ('', self.port)  # all interfaces with specified port
        logging.info(f"Binding to {addr[0]}:{addr[1]}")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Avoid bind() exception: OSError: [Errno 48] Address already in use
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen()
        s.setblocking(False)
        self.sel.register(s, selectors.EVENT_READ | selectors.EVENT_WRITE, data=None)
        # Main connection thread, reads recv of each connection into a message queue
        self.connection_monitor.start()
        self.message_handler.start()

        # New connections are being found and their messages handled, do something...
        try:
            while not self.termination_event.is_set():
                pass
        except KeyboardInterrupt:
            logging.debug("Caught keyboard interrupt, exiting")
        finally:
            self.termination_event.set()
        self.connection_monitor.join()
        self.message_handler.join()

