import configparser
import argparse
from src.Server.Server import Server
from src.Client.Client import Client
import logging


def start_server(server_config):
    # initialize server
    server = Server(server_config)
    # start accepting client connections and building node graph
    server.start()


def start_client(client_config):
    # initialize client
    client = Client(client_config)
    client.start()


# Entry point
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reads and controls game network resources.')
    parser.add_argument('-s', '--server', default=False, action='store_true')
    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Setup logging
    level = logging.INFO
    if config['DEFAULT'].getboolean('verbose'):
        level = logging.DEBUG
    if config['DEFAULT'].getboolean('log_to_file'):
        logging.basicConfig(level=level, filename=config['DEFAULT']['logfile'],
                            filemode='w', format='%(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=level, format='%(name)s - %(levelname)s - %(message)s')

    # Begin process
    if args.server:
        start_server(config)
    else:
        start_client(config)
