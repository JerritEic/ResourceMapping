# import src.PerformanceReport.PerformanceReport
import os
import selectors
import threading
import time
from queue import Queue

from src.Experiment.Experiment import get_experiment_by_name
from src.NetProtocol.ConnectionHandler import ConnectionHandler, ConnectionMonitor
from src.NetProtocol.Message import Message
from src.NetProtocol.MessageHandler import MessageHandler
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNodeType
from src.app.Component import Component, ComponentType, ComponentHandler
from src.PerformanceReport.HardwareMetrics import HardwareMetrics
from src.PerformanceReport.Metrics import MetricCollector, MetricCollectionMode
from src.Utility.MetricUtilities import get_static_hardware_stats, dict_factory
from src.Utility.NetworkUtilities import *
import sqlite3
import logging
from datetime import datetime
from os.path import exists
import shutil


# Entry point for resource monitoring
class Application:
    db = None
    _database_template = "./resources/db_template.db"
    _component_handler = None
    _component_metric_handlers: [MetricCollector] = []
    # By default, database
    _default_metric_collection_mode = MetricCollectionMode.TO_DB
    _db_file = None

    def __init__(self, config, is_server):
        self.is_server = is_server
        self.p_name = "ResourceServer" if self.is_server else "ResourceClient"
        # experiment
        self.experiment = get_experiment_by_name(config['DEFAULT']['experiment'])
        if self.experiment is None:
            logging.error(f"Experiment {config['DEFAULT']['experiment']} not found!")
            self.halt()

        self.termination_event = threading.Event()
        self._persist_db = config[self.p_name].getboolean('persist_db')
        # database
        self.db_write_cur = None
        date = datetime.now()
        self._db_file = f"./{date.year}{date.month}{date.day}_" \
                        f"{date.hour}{date.minute}{date.second}_{self.p_name}_metrics.db"
        if not self._initialize_sqlite_db():
            self.halt()
            return

        self.hardware_stats = get_static_hardware_stats()
        self.server_ip = config["ResourceClient"]['server_ip']
        self.port = int(config['DEFAULT']['port'])
        self.sampling_frequency = int(config[self.p_name]['sampling_frequency'])
        self.experiment.sampling_frequency = self.sampling_frequency

        # uuid
        self.uuid = cached_or_new_uuid(config[self.p_name].getboolean('use_cached_uuid'),
                                       config[self.p_name]['uuid_cache'])
        # networking
        ip = get_my_ip()
        self.ip = ip
        self.sel = selectors.DefaultSelector()
        self.receive_queue: "Queue[Message]" = Queue()
        # Setup network representation class
        self.net_graph = NetworkGraph(self.p_name, (self.ip, self.port),
                                      NetworkNodeType.CLIENT, self.uuid, self.hardware_stats)

        # Start message monitoring/handling threads
        self.connection_monitor = ConnectionMonitor(self.termination_event, self.sel, self.receive_queue)
        self.message_handler = MessageHandler(self.receive_queue, self.termination_event, owner=self)

        # Fill in initial component (which is this application)
        c = Component(os.getpid(), self.net_graph.get_own_node(), name=self.p_name)
        self._component_handler = ComponentHandler(self, config['DEFAULT']['components_file'])
        self._component_handler.add_component(c)
        self.elapsed_time = 0

    def _initialize_sqlite_db(self):
        if not exists(self._database_template):
            logging.error("Database template not found! Is the resources folder where it should be?")
            return False

        # Copy the template to working directory
        shutil.copyfile(self._database_template, self._db_file)

        try:
            self.db = sqlite3.connect(self._db_file)
            self.db.row_factory = dict_factory
            self.db_write_cur = self.db.cursor()
        except sqlite3.Error:
            logging.error("Database connection failed.")
            return False

        return True

    def start(self):
        if self.is_server:
            self._start_server()
        else:
            self._start_client()

    def _start_server(self):
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

        self._exec_loop()
        self.halt()

    def _start_client(self):
        logging.info(f"Connecting to {self.server_ip}:{self.port}")
        # wait to establish a server connection
        server_connection = wait_for_connection(self.server_ip, self.port, num_retries=3, timeout=5.0)
        if server_connection is None:
            logging.error("Could not establish connection to server. Exiting.")
            return
        logging.info(f"Connected")

        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        conn_handler = ConnectionHandler(self.sel, server_connection,
                                         (self.server_ip, self.port), 0, self.receive_queue)
        self.sel.register(server_connection, events, data=conn_handler)

        # Start the connection monitor to setup/select messages from sockets
        self.connection_monitor.start()

        handshake_dict = dict(uuid=str(self.uuid),
                              hw_stats=self.hardware_stats.copy(),
                              response=False)

        logging.info(f"Performing handshake with own uuid: {str(self.uuid)}")
        message = Message(content=Request(RequestType.HANDSHAKE, handshake_dict))
        future = conn_handler.send_message_and_wait_response(message)
        start_t = time.time()
        while True:
            self.message_handler.read_messages()
            if future.is_set():
                break
            if time.time() - start_t > 10:
                logging.error(f"Timeout on handshake, aborting.")
                self.halt()
        # After handshake established, make sure new node is marked as server
        self.net_graph.set_server(conn_handler.peer_uuid)

        # run metric collection
        self._initialize_metric_handlers()
        self._exec_loop()

        # Send exit once finished
        message = Message(content=Request(RequestType.EXIT))
        conn_handler.send_message(message)  # don't wait for a response
        self.halt()

    def _initialize_metric_handlers(self):
        self._component_metric_handlers.append(
            MetricCollector(HardwareMetrics, self._component_handler.components, self._default_metric_collection_mode, self.db_write_cur))

    # Clock that runs the local metric sampling of all components
    def _exec_loop(self):
        sample_period = 1 / self.sampling_frequency
        start_t = time.time()
        last_t = start_t
        try:
            while not self.termination_event.is_set():
                # check messages
                self.message_handler.read_messages()
                # check elapsed time
                t = time.time()
                if (t - last_t) > sample_period:
                    last_t = t
                    self.elapsed_time = (t - start_t)

                    if self.is_server:
                        self.experiment.experiment_step()
                    else:
                        self._iter_client()
        except KeyboardInterrupt:
            logging.debug("Caught keyboard interrupt, exiting")

    def _iter_client(self):
        # Start all collectors
        for metric_handler in self._component_metric_handlers:
            metric_handler.collect(elapsed_time=self.elapsed_time)
        # Process collected metrics
        for metric_handler in self._component_metric_handlers:
            metric_handler.process_results()
        # Commit any metrics logged to DB
        self.db.commit()

    def halt(self):
        if self.termination_event:
            self.termination_event.set()
        if self.connection_monitor:
            self.connection_monitor.join()
        if self.db:
            self.db.close()
        if not self._persist_db:
            os.remove(self._db_file)
