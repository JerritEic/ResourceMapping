import configparser
import argparse
import os

from src.app.Application import Application
import logging

# Python entry point
if __name__ == '__main__':
    # Read configuration
    parser = argparse.ArgumentParser(description='Reads and controls game network resources.')
    parser.add_argument('-s', '--server', default=False, action='store_true')
    args = parser.parse_args()
    CONFIG = configparser.ConfigParser()
    CONFIG.read('config.ini')

    # Setup logging
    level = logging.INFO
    if CONFIG['DEFAULT'].getboolean('verbose'):
        level = logging.DEBUG
    out_fmt = '%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
    out_fmt_time = "%H:%M:%S"
    if CONFIG['DEFAULT'].getboolean('log_to_file'):
        logging.basicConfig(level=level, filename=CONFIG['DEFAULT']['logfile'],
                            filemode='w', format=out_fmt, datefmt=out_fmt_time)
    else:
        logging.basicConfig(level=level, format=out_fmt, datefmt=out_fmt_time)

    if not os.path.isdir('./logs'):
        os.makedirs('./logs')

    # Begin resource monitoring
    app = Application(CONFIG, args.server)
    app.start()

