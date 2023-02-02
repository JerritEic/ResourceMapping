import configparser
import argparse
from src.app.Application import Application
import logging

# Python entry point
if __name__ == '__main__':
    # Read configuration
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
                            filemode='w', format='%(threadName)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=level, format='%(threadName)s- %(levelname)s - %(message)s')

    # Begin resource monitoring
    # TODO also start a client alongside a server
    app = Application(config, args.server)
    app.start()

