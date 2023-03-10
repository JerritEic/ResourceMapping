import logging
import queue
import struct
import selectors
import traceback
from socket import socket
from threading import Event, Thread

from src.NetProtocol.AwaitResponse import MessageEvent
from src.NetProtocol.Request import Request
from src.Utility.NetworkUtilities import json_decode
from src.NetProtocol.Message import Message


# Required headers in the JSON header
REQUIRED_HEADERS = [
    "byteorder",
    "content_length",
    "content_type",
    "content_encoding",
    "CSeq"
]


# Handles setting up connections and monitoring all socket connections
class ConnectionMonitor(Thread):
    def __init__(self, termination_event: Event, selector, receive_queue):
        super().__init__()
        self.termination_event = termination_event
        self.selector = selector
        self.receive_queue = receive_queue
        self.connection_number = 1

    def run(self):
        try:
            while not self.termination_event.is_set():
                # logging.debug(f"Checking selector.select")
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        # A new connection
                        self._accept_wrapper(key.fileobj)
                    else:
                        conn_handler = key.data
                        try:
                            conn_handler.process_events(mask)
                        except Exception:
                            logging.error(f"Exception in message from/to {conn_handler.addr}\n:{traceback.format_exc()}")
                            conn_handler.close()
                # Check for a socket still being monitored
                if not self.selector.get_map():
                    break
        except KeyboardInterrupt:
            logging.info("Caught keyboard interrupt, exiting.")
        finally:
            logging.debug(f"Connection handler stopped.")
            self.selector.close()
            self.termination_event.set()

    # Handle a new connection
    def _accept_wrapper(self, sock: socket):
        conn, addr = sock.accept()
        logging.info(f"Accepted connection from {conn.getpeername()}")
        conn.setblocking(False)
        conn_handler = ConnectionHandler(selector=self.selector, sock=conn, addr=conn.getpeername(),
                                         num=self.connection_number, receive_queue=self.receive_queue)
        self.connection_number += 1
        self.selector.register(conn, selectors.EVENT_READ | selectors.EVENT_WRITE, data=conn_handler)


# Handles receiving and sending on a specific connection. Run on main server/client thread
# based on https://realpython.com/python-sockets/#application-client-and-server
class ConnectionHandler(Thread):
    def __init__(self, selector: selectors.BaseSelector, sock: socket, addr, num, receive_queue: queue.Queue):
        super().__init__(name="ConnectionHandler")
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.peer_name = f"peer_{num}"
        self.CSeq = -1  # Sequence number we use when sending messages, incremented each message
        self.peer = None  # Is set to a NetworkNode after a successful handshake
        self._recv_buffer = b""
        self._send_buffer = b""
        self._current_recv_message = None
        # submit messages to the global receive queue
        self._receive_queue = receive_queue
        # each message handler gets own send queue
        self._send_queue = queue.Queue()
        # CSeq -> Event dict, events are set when the CSeq we are awaiting arrives
        self.await_list = dict()

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self._read_wrapper()
        if mask & selectors.EVENT_WRITE:
            self._write_wrapper()

    def _read_wrapper(self):
        self._read()

        if self._current_recv_message is None:
            #logging.debug(f"started receiving new message")
            self._current_recv_message = Message(handler=self)

        # could take multiple _read to process single message, so keep track of headers
        if self._current_recv_message.json_header_len is None:
            self._process_protoheader()

        if self._current_recv_message.json_header_len is not None:
            if self._current_recv_message.json_header is None:
                self._process_jsonheader()

        if self._current_recv_message.json_header:
            if self._current_recv_message.content is None:
                self._process_message()

    # read from socket to a buffer
    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                # Empty message interpreted as socket closed
                logging.info(f"Peer at {self.addr} closed.")
                self.close()

    def _write_wrapper(self):
        if not self._send_buffer:
            if not self._send_queue.empty():
                self._send_buffer += self._send_queue.get()
            #else:
            #    logging.info("Nothing more to write")
            #    self._set_selector_events_mask('r')

        self._write()

    # Send data in the send buffer
    def _write(self):
        if self._send_buffer:
            # logging.debug(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)

            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                if sent and not self._send_buffer:
                    # buffer is drained. The response has been sent.
                    logging.debug(f"Message has been sent")


    # Process the fixed length header (2 byte, big endian), gives length of following JSON header
    def _process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._current_recv_message.json_header_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    # Process variable length json_header
    def _process_jsonheader(self):
        hdrlen = self._current_recv_message.json_header_len
        if len(self._recv_buffer) >= hdrlen:
            self._current_recv_message.json_header = json_decode(self._recv_buffer[:hdrlen], "utf-8")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for req_hdr in REQUIRED_HEADERS:
                if req_hdr not in self._current_recv_message.json_header:
                    raise ValueError(f"Missing required header '{req_hdr}'.")
            # Make sure CSeq is correct on the message
            self._current_recv_message.CSeq = self._current_recv_message.json_header['CSeq']

    # Process message after reading the header
    def _process_message(self):
        hdr = self._current_recv_message.json_header
        content_len = hdr["content_length"]
        # don't process now if we haven't received the whole message yet
        if not len(self._recv_buffer) >= content_len:
            return
        # get received content
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]

        if hdr["content_type"] == "text/json":
            encoding = hdr["content_encoding"]
            self._current_recv_message.content = Request(content=json_decode(data, encoding))
            logging.debug(f"Received request {self._current_recv_message.content.request['action']} from {self.addr}")
        else:
            # Binary or unknown content-type
            self._current_recv_message.content = data
            logging.debug(
                f"Received {hdr['content_type']} "
                f"request from {self.addr}"
            )
        self._receive_queue.put(self._current_recv_message)
        self._current_recv_message = None

    # enqueue a request, return CSeq
    def send_message(self, message: Message, is_response=False):
        message.conn_handler = self
        message.is_received = False
        # Don't change the CSeq if we are responding to a message
        if not is_response:
            self.CSeq += 1
            logging.debug(f"CSeq for {self.addr} is now {self.CSeq}")
            message.CSeq = self.CSeq
        logging.debug(f"Enqueued{' response' if is_response else ''}: {message.content.request['action']} to {self.addr} with CSeq {message.CSeq}")
        #self._set_selector_events_mask('rw')
        self._send_queue.put(message.get_serialized())

    # enqueue a request, returns a future to wait for a response. If yield_message is true, the message handler will
    # pass the message through this event rather than handle it itself
    def send_message_and_wait_response(self, message: Message, is_response=False, yield_message=False) -> MessageEvent:
        message.conn_handler = self
        message.is_received = False
        # Don't change the CSeq if we are responding to a message
        if not is_response:
            self.CSeq += 1
            logging.debug(f"CSeq for {self.addr} is now {self.CSeq}")
            message.CSeq = self.CSeq
        #self._set_selector_events_mask('rw')
        # Add the wait event before sending
        logging.debug(f"Enqueued{' response' if is_response else ''}: {message.content.request['action']} to {self.addr} with wait on CSeq {message.CSeq}")
        message_event = self._add_new_await(message.CSeq, yield_message)
        # Force a reserialize, fixes an edge case where we wait on a message with wrong CSeq sent
        self._send_queue.put(message.get_serialized(force_reserialize=True))
        return message_event

    # Add a new CSeq await to the list of waiting event objects
    def _add_new_await(self, CSeq, yield_message) -> MessageEvent:
        if CSeq in self.await_list:
            logging.error(f"Already waiting for a response to this message...")
        event = MessageEvent(yield_message)
        #logging.debug(f"Adding await for CSeq {CSeq}")
        self.await_list[CSeq] = event
        return event

    # Set selector to listen for events: mode is 'r', 'w', or 'rw'.
    def _set_selector_events_mask(self, mode):
        logging.debug(f"Set selector to mode {mode}")
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(self.sock, events, data=self)

    def close(self):
        logging.info(f"Closing connection to {self.addr}")
        if self.peer is not None:
            self.peer.is_active = False
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            logging.error(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )

        try:
            self.sock.close()
        except OSError as e:
            logging.error(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None
