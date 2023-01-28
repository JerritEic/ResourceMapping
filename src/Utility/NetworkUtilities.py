import socket
import logging


def get_my_ip():
    hostname = socket.getfqdn()
    ip = socket.gethostbyname_ex(hostname)
    return ip


def wait_for_connection(ip, port, num_retries, timeout):
    if num_retries == 0:
        logging.error(f"Could not connect to {ip}:{port}")
        return None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        return sock
    except TimeoutError:
        logging.debug(f"timed out connecting to {ip}:{port}, retrying...")
    except ConnectionRefusedError:
        logging.debug(f"connection refused to {ip}:{port}, retrying...")

    return wait_for_connection(ip, port, num_retries-1, timeout)
