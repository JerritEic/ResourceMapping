#import src.PerformanceReport.PerformanceReport
from src.Utility.NetworkUtilities import *
import logging


class Client:
    def __init__(self, client_config):
        self.server_ip = client_config['client']['server_ip']
        self.server_port = int(client_config['DEFAULT']['port'])

    def start(self):
        logging.info(f"Connecting to {self.server_ip}:{self.server_port}")
        # wait to establish a server connection
        server_connection = wait_for_connection(self.server_ip, self.server_port, num_retries=3, timeout=5.0)
        if server_connection is None:
            logging.error("Could not establish connection to server. Exiting.")
            return
        logging.info(f"Connected")
        server_connection.send(b"Client message 1")
        msg = server_connection.recv(1024)
        logging.info(f"received: {msg}")
