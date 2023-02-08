import io
import json
import socket
import logging
import uuid
from os.path import exists


def get_my_ip():
    hostname = socket.getfqdn()
    ip = socket.gethostbyname_ex(hostname)
    return ip[2][-1]


def wait_for_connection(ip, port, num_retries, timeout):
    if num_retries == 0:
        logging.error(f"Could not connect to {ip}:{port}")
        return None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        return sock
    except TimeoutError:
        logging.debug(f"timed out connecting to {ip}:{port}, retrying...")
    except ConnectionRefusedError:
        logging.debug(f"connection refused to {ip}:{port}, retrying...")

    return wait_for_connection(ip, port, num_retries-1, timeout)


def cached_or_new_uuid(use_cached=False, cache_file="./cached_uuid.txt"):
    ret = None
    # uuid
    if use_cached and exists(cache_file):
        with open(cache_file, 'r') as file:
            ret = uuid.UUID(file.readline())
    else:
        ret = uuid.uuid4()
        with open(cache_file, 'w') as file:
            file.write(str(ret))
    return ret


def json_encode(obj, encoding):
    return json.dumps(obj, ensure_ascii=False).encode(encoding)


def json_decode(json_bytes, encoding):
    tiow = io.TextIOWrapper(
        io.BytesIO(json_bytes), encoding=encoding, newline=""
    )
    obj = json.load(tiow)
    tiow.close()
    return obj
