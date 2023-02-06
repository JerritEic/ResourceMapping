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
        response = False
        if 'response' in content:
            response = content['response']

        # If this message is a response being waited on, notify. If yield message is true, return to let the event
        # listener handle it.
        if response and item.CSeq in item.conn_handler.await_list:
            yield_message = item.conn_handler.await_list[item.CSeq].yield_message
            if yield_message:
                item.conn_handler.await_list[item.CSeq].set_message(item)
            item.conn_handler.await_list[item.CSeq].set()
            # Remove this CSeq from the await dict
            logging.debug(f"Removing await for CSeq {item.CSeq}")
            item.conn_handler.await_list.pop(item.CSeq)
            if yield_message:
                return

        if action == RequestType.HANDSHAKE:
            self._handle_handshake(item)
        elif action == RequestType.METRIC:
            self._handle_metric(item)
        elif action == RequestType.COMPONENT:
            self._handle_component(item)
        elif action == RequestType.EXIT:
            self._handle_exit(item)

    def _handle_handshake(self, item: Message):
        content = item.content.request
        logging.debug(
            f"Received handshake CSEQ {item.json_header['CSeq']} with response: {content['response']} and UUID: {content['uuid']}"
            f" from {item.conn_handler.addr}")
        peer_uuid = UUID(content['uuid'])
        peer_node = self.owner.net_graph.new_node(item.conn_handler.peer_name, item.conn_handler,
                                                  item.conn_handler.addr, NetworkNodeType.CLIENT,
                                                  peer_uuid, content['hw_stats'])
        item.conn_handler.peer = peer_node  # Update connection's knowledge of peer

        self.owner.net_graph.new_connection_to_self(peer_uuid)
        logging.debug(str(self.owner.net_graph))
        if not content['response']:
            # Reply with our own stats and UUID
            response_dict = dict(uuid=str(self.owner.uuid),
                                 hw_stats=self.owner.hardware_stats.copy(),
                                 response=True)
            item.content = Request(RequestType.HANDSHAKE, response_dict)
            item.conn_handler.send_message(item, is_response=True)  # don't wait for reply

    def _handle_metric(self, item: Message):
        content = item.content.request
        # logging.debug(f"Received metric request metrics: {content['metrics']} from {item.conn_handler.addr}")
        if not content['response']:
            # reply with an aggregate report of metrics
            time_start = self.owner.elapsed_time - content['period']
            cur = self.owner.db.cursor()
            table = content['metrics'][0]  # in a request, 'metrics' is a list of metrics to return
            res = cur.execute(f"SELECT AVG(cpu), AVG(memory), pid, process_name FROM {table} INNER JOIN components ON"
                              f" components.pid = {table}.component WHERE timestamp > ? GROUP BY pid", (time_start,))
            # logging.debug(f"metric report: {res.fetchall()}")
            response_dict = dict(period=content['period'],
                                 metrics=res.fetchall(),
                                 response=True)
            item.content = Request(RequestType.METRIC, response_dict)
            item.conn_handler.send_message(item, is_response=True)
        else:
            item.conn_handler.peer.add_received_metric(content['metrics'])

    def _handle_component(self, item: Message):
        content = item.content.request
        logging.debug(f"Received component request: {content['components']} from {item.conn_handler.addr}")
        if not content['response']:
            if content['component_actions'][0] == "start":
                # start the requested components, reply with status
                pid = self.owner.component_handler.start_component(content['components'][0])
                if pid == -1:
                    # Could not start the process, reply with an error
                    err_dict = dict(error=f"Could not start process {content['components'][0]}")
                    item.content = Request(RequestType.ERROR, err_dict)
                    item.conn_handler.send_message(item, is_response=True)
                else:
                    content['response'] = True
                    content['results'] = [pid]
                    item.content = Request(RequestType.COMPONENT, content)
                    item.conn_handler.send_message(item, is_response=True)
        else:
            # handle a received component response
            # currently handled by where a component request was sent.
            pass

    def _handle_exit(self, item: Message):
        logging.debug(f"Received exit request from {item.conn_handler.addr}")
        self.termination_event.set()
