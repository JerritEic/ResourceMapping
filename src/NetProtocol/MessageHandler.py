import logging
import threading
from uuid import UUID

from src.NetProtocol.Message import Message
from queue import Queue

# thread that processes the incoming message queue
from src.NetProtocol.Request import RequestType, Request
from src.NetworkGraph.NetworkGraph import NetworkNodeType
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.app.Application import Application


class MessageHandler:
    def __init__(self, message_queue: "Queue[Message]", termination_event: threading.Event, owner: "Application"):
        self.message_queue = message_queue
        self.termination_event = termination_event
        self.owner = owner

    def read_messages(self):
        if self.message_queue.empty():
            return
        item = self.message_queue.get()
        # hdr = item.json_header
        # m_type = hdr["content_type"]
        # encoding = hdr["content_encoding"]
        content = item.content.request
        action = content['action']

        if action == RequestType.HANDSHAKE:
            self._handle_handshake(item)
        elif action == RequestType.METRIC:
            self._handle_metric(item)
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
        item.conn_handler.peer_uuid = UUID(content['uuid'])  # Update our knowledge of the peer UUID
        self.owner.net_graph.new_node(item.conn_handler.peer_name, item.conn_handler,
                                      NetworkNodeType.CLIENT, item.conn_handler.peer_uuid, content['hw_stats'])
        self.owner.net_graph.new_connection_to_self(item.conn_handler.peer_uuid)
        if not content['response']:
            # Reply with our own stats and UUID
            response_dict = dict(uuid=str(self.owner.uuid),
                                 hw_stats=self.owner.hardware_stats.copy(),
                                 response=True)
            item.content = Request(RequestType.HANDSHAKE, response_dict)
            item.conn_handler.send_message(item, is_response=True)

    def _handle_metric(self, item: Message):
        content = item.content.request
        logging.debug(
            f"Received metric request metrics: {content['metrics']} from {item.conn_handler.addr}")
        if not content['response']:
            # reply with an aggregate report of metrics
            time_start = self.owner.elapsed_time - content['period']
            cur = self.owner.db.cursor()
            table = content['metrics'][0]
            res = cur.execute(f"SELECT AVG(cpu), AVG(memory), pid, process_name FROM {table} INNER JOIN components ON"
                              f" components.pid = {table}.component WHERE timestamp > ? GROUP BY pid", (time_start,))
            logging.debug(f"metric report: {res.fetchall()}")
        else:
            # handle a received aggregate report of metrics
            pass

    def _handle_exit(self, item: Message):
        logging.debug(f"Received exit request from {item.conn_handler.addr}")
        self.termination_event.set()
