import logging
import threading
from uuid import UUID

from src.NetProtocol.Message import Message
from queue import Queue

# thread that processes the incoming message queue
from src.NetProtocol.Request import RequestType, Request
from src.NetworkGraph.NetworkGraph import NetworkNodeType
from src.Node import Node


class MessageHandler(threading.Thread):
    def __init__(self, message_queue: "Queue[Message]", termination_event: threading.Event, owner: Node):
        super().__init__(name="MessageHandler")
        self.message_queue = message_queue
        self.termination_event = termination_event
        self.owner = owner

    def run(self):
        self.read_messages()

    def read_messages(self):
        while not self.termination_event.is_set():
            if self.message_queue.empty():
                continue
            item = self.message_queue.get()
            # hdr = item.json_header
            # m_type = hdr["content_type"]
            # encoding = hdr["content_encoding"]
            content = item.content.request
            action = content['action']

            if action == RequestType.HANDSHAKE:
                self._handle_handshake(item)
            elif action == RequestType.EXIT:
                self._handle_exit(item)
            # If this message is a response being waited on, notify
            if item.CSeq in item.conn_handler.await_list:
                item.conn_handler.await_list[item.CSeq].set()

    def _handle_handshake(self, item: Message):
        content = item.content.request
        logging.debug(
            f"Received handshake CSEQ {item.json_header['CSeq']} with response: {content['response']} and UUID: {content['uuid']}"
            f" from {item.conn_handler.addr}")
        item.conn_handler.uuid = UUID(content['uuid'])  # Update our knowledge of the peer UUID
        self.owner.net_graph.new_node(item.conn_handler.peer_name, item.conn_handler.addr,
                                      NetworkNodeType.CLIENT, item.conn_handler.uuid, content['hw_stats'])
        self.owner.net_graph.new_connection_to_self(item.conn_handler.uuid)
        if content['response'] == "false":
            # Reply with our own stats and UUID
            response_dict = dict(uuid=self.owner.uuid,
                                 hw_stats=self.owner.hardware_stats.copy(),
                                 response="true")
            item.content = Request(RequestType.HANDSHAKE, response_dict)
            item.conn_handler.send_message(item, is_response=True)

    def _handle_exit(self, item: Message):
        logging.debug(f"Received exit request from {item.conn_handler.addr}")
        self.termination_event.set()
