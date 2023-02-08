# import src.PerformanceReport.PerformanceReport
import os
import selectors
import threading
import time
from queue import Queue

from src.Experiment.ExperimentList import get_experiment_by_name
from src.NetProtocol.ConnectionHandler import ConnectionHandler, ConnectionMonitor
from src.NetProtocol.Message import Message
from src.NetProtocol.MessageHandler import MessageHandler
from src.NetProtocol.Request import Request, RequestType
from src.NetworkGraph.NetworkGraph import NetworkGraph, NetworkNodeType
from src.app.Component import Component, ComponentHandler
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
    _database_template = None
    component_handler = None
    connection_monitor = None
    component_metric_handlers: [MetricCollector] = []
    # By default, database
    _default_metric_collection_mode = MetricCollectionMode.TO_DB
    _db_file = None

    def __init__(self, config, is_server):
        self.config = config
        self.is_server = is_server
        self.p_name = "ResourceServer" if self.is_server else "ResourceClient"
        # experiment
        self.experiment = get_experiment_by_name(config['DEFAULT']['experiment'])
        if self.experiment is None:
            logging.error(f"Experiment {config['DEFAULT']['experiment']} not found!")
            self.halt()

        self.termination_event = threading.Event()
        self._database_template = config[self.p_name]['database_template']
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
        #logging.debug(f"getting ip...")
        # networking
        #ip = get_my_ip()
        self.ip = "127.0.0.1"
        self.sel = selectors.DefaultSelector()
        self.receive_queue: "Queue[Message]" = Queue()
        # Setup network representation class
        self.net_graph = NetworkGraph(self.p_name, (self.ip, self.port),
                                      NetworkNodeType.CLIENT, self.uuid, self.hardware_stats)

        # Start message monitoring/handling threads
        self.connection_monitor = ConnectionMonitor(self.termination_event, self.sel, self.receive_queue)
        self.message_handler = MessageHandler(self.receive_queue, self.termination_event, owner=self)

        # Fill in initial components (which is this application)
        self.component_handler = ComponentHandler(self, config['DEFAULT']['components_file'])
        c = Component(os.getpid(), name=self.p_name)
        self.component_handler.add_component(c)
        self.elapsed_time = 0
        logging.debug(f"Setup complete")

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
        if not self.experiment.setup(self.net_graph, self.message_handler, self.termination_event):
            logging.error(f"Experiment setup failed, aborting.")
            self.halt()
            return
        self._exec_loop()
        self.experiment.end()
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
                return
        # After handshake established, make sure new node is marked as server
        self.net_graph.set_server(conn_handler.peer.uuid)

        # run metric collection
        self._initialize_metric_handlers()
        self._exec_loop()

        # Send exit once finished
        message = Message(content=Request(RequestType.EXIT))
        conn_handler.send_message(message)  # don't wait for a response
        self.halt()

    def _initialize_metric_handlers(self):
        self.component_metric_handlers.append(
            MetricCollector(HardwareMetrics, self.component_handler.components, self._default_metric_collection_mode, self.db_write_cur))

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
                        if (t - start_t) > self.experiment.duration:
                            break
                        if not self.experiment.experiment_step():
                            break
                    else:
                        self._iter_client()
        except KeyboardInterrupt:
            logging.debug("Caught keyboard interrupt, exiting")

    def _iter_client(self):
        # Start all collectors
        for metric_handler in self.component_metric_handlers:
            metric_handler.collect(elapsed_time=self.elapsed_time)
        # Process collected metrics
        for metric_handler in self.component_metric_handlers:
            metric_handler.process_results()
        # Commit any metrics logged to DB
        self.db.commit()

    def halt(self):
        if self.experiment is not None:
            self.experiment.end()
        if self.termination_event is not None:
            self.termination_event.set()
        if self.component_handler is not None:
            self.component_handler.stop_components()
        if self.connection_monitor is not None:
            self.connection_monitor.join(timeout=1)
        if self.db is not None:
            self.db.close()
        if not self._persist_db:
            os.remove(self._db_file)
