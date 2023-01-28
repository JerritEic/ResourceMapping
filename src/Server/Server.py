#import src.PerformanceReport.PerformanceReport
from src.Utility.NetworkUtilities import *
from src.NetworkGraph.NetworkGraph import NetworkGraph
import selectors
import socket
import logging
import types

class Server:
    def __init__(self, server_config):
        ip = get_my_ip()
        self.ip = ip
        self.port = int(server_config['DEFAULT']['port'])
        self.net_graph = NetworkGraph(ip)
        self.sel = selectors.DefaultSelector()

    def start(self):
        # https://realpython.com/python-sockets/#multi-connection-server
        addr = ('', self.port)  # all interfaces with specified port
        logging.info(f"Binding to {addr[0]}:{addr[1]}")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(addr)
        s.listen()
        s.setblocking(False)
        self.sel.register(s, selectors.EVENT_READ, data=None)

        try:
            while True:
                events = self.sel.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        # A new connection
                        self._accept_wrapper(key.fileobj)
                    else:
                        # Service existing connection
                        self._service_connection(key, mask)
        except KeyboardInterrupt:
            logging.info("Caught keyboard interrupt, exiting.")
        finally:
            self.sel.close()

    # Handle a new connection
    def _accept_wrapper(self, sock):
        conn, addr = sock.accept()
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, data=data)
        # TODO add this connection to a network graph node

    def _service_connection(self, key, mask):
        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
            recv_data = sock.recv(1024)  # Should be ready to read
            if recv_data:
                data.outb += recv_data
            else:
                print(f"Closing connection to {data.addr}")
                self.sel.unregister(sock)
                sock.close()
        if mask & selectors.EVENT_WRITE:
            if data.outb:
                print(f"Echoing {data.outb!r} to {data.addr}")
                sent = sock.send(data.outb)  # Should be ready to write
                data.outb = data.outb[sent:]
