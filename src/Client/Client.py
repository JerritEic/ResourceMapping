# import src.PerformanceReport.PerformanceReport
import selectors
import threading
import traceback
from queue import Queue

from src.NetProtocol.ConnectionHandler import ConnectionHandler, ConnectionMonitor
from src.NetProtocol.Message import Message
from src.NetProtocol.MessageHandler import MessageHandler
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNodeType
from src.Utility.NetworkUtilities import *
from src.Node import Node
from src.third_party.timed_count.timed_count.timed_count import timed_count
import sqlite3
import logging
import datetime
from os.path import exists
import shutil
import uuid


class Client(Node):
    db = None
    _database_template = "./resources/db_template.db"
    _hw_metric_thread = None
    _net_metric_thread = None
    _component_metric_threads = []

    def __init__(self, client_config):
        super().__init__()
        self.server_ip = client_config['client']['server_ip']
        self.server_port = int(client_config['DEFAULT']['port'])
        self.sampling_frequency = int(client_config['client']['sampling_frequency'])

        # uuid
        self.uuid = cached_or_new_uuid(client_config['DEFAULT'].getboolean('use_cached_uuid'))
        # networking
        self.connection_monitor = ConnectionMonitor(self.termination_event, self.sel, self.receive_queue)
        self.message_handler = MessageHandler(self.receive_queue, self.termination_event, owner=self)

        self.net_graph = NetworkGraph("client", (self.ip, self.server_port), NetworkNodeType.CLIENT, self.uuid)
        # database
        if not self._initialize_sqlite_db():
            return

    def _initialize_sqlite_db(self):
        if not exists(self._database_template):
            logging.error("Database template not found! Is the resources folder where it should be?")
            return False
        date = datetime.datetime
        db_name = f"./{date.year}_{date.month}_{date.day}_{date.hour}_{date.minute}_{date.second}_metrics.db"

        # Copy the template to working directory
        shutil.copyfile(self._database_template, db_name)

        try:
            self.db = sqlite3.connect(db_name)
        except sqlite3.Error:
            logging.error("Database connection failed.")
            return False

        return True

    def start(self):
        logging.info(f"Connecting to {self.server_ip}:{self.server_port}")
        # wait to establish a server connection
        server_connection = wait_for_connection(self.server_ip, self.server_port, num_retries=3, timeout=5.0)
        if server_connection is None:
            logging.error("Could not establish connection to server. Exiting.")
            return
        logging.info(f"Connected")

        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        conn_handler = ConnectionHandler(self.sel, server_connection,
                                         (self.server_ip, self.server_port), 0, self.receive_queue)
        self.sel.register(server_connection, events, data=conn_handler)

        # Start the connection monitor to setup/select messages from sockets
        self.connection_monitor.start()
        # Start message handler to handle messages from all monitored connections
        self.message_handler.start()

        logging.info(f"Performing handshake with own uuid: {str(self.uuid)}")
        message = Message(content=Request(RequestType.HANDSHAKE, dict(uuid=str(self.uuid))))
        future = conn_handler.send_message_and_wait_response(message)
        if not future.wait(timeout=10):
            logging.error(f"Timeout on handshake, aborting.")
            self.halt()
            return
        # After handshake established, make sure new node is marked as server
        self.net_graph.set_server(conn_handler.addr, conn_handler.peer_uuid)
        # DO THINGS

        # Send exit once finished
        message = Message(content=Request(RequestType.EXIT))
        conn_handler.send_message(message)  # don't wait for a response
        self.halt()

    def metric_monitoring(self):
        sample_period = 1.0/self.sampling_frequency

        while True:
            pass


    def halt(self):
        self.termination_event.set()
        self.connection_monitor.join()
        self.message_handler.join()
