import logging
import threading
import time
from uuid import UUID

from src.NetProtocol.AwaitResponse import MessageEvent
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
        logging.debug(f"Await list on {item.conn_handler.addr} is {item.conn_handler.await_list}")
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

    # Given list of MessageEvents, wait for all of their associated responses to arrive.
    def wait_for_responses(self, message_events: list[MessageEvent], timeout: int) -> bool:
        start_t = time.time()
        not_ready = True
        while not_ready:
            self.read_messages()
            if time.time() - start_t > timeout or self.termination_event.is_set():
                return False
            not_ready = False
            for m in message_events:
                if not m.is_set():
                    not_ready = True
                    break
        return True

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
        comp_name = content['components'][0]
        logging.debug(f"Received component request with CSeq {item.CSeq} for {comp_name} from {item.conn_handler.addr}")
        if not content['response']:
            component_actions = content['component_actions'][0]
            # ensure it is a list
            component_actions = [component_actions] if not isinstance(component_actions, list) else component_actions
            component_action_responses = []
            for i, component_action in enumerate(component_actions):
                try:
                    args = content['args'][i] if 'args' in content else dict()
                except IndexError:
                    args = dict()
                if component_action == "start":
                    # start the requested components, reply with pid
                    pid = self.owner.component_handler.start_component(comp_name, args)
                    component_action_responses.append(pid)
                elif component_action == "ready":
                    res = self.owner.component_handler.ready_component(comp_name, args)
                    component_action_responses.append(res)
                else:
                    component_action_responses.append("UNSUPPORTED")
            content['response'] = True
            content['results'] = component_action_responses
            item.content = Request(RequestType.COMPONENT, content)
            item.conn_handler.send_message(item, is_response=True)
        else:
            # handle a received component response
            # currently handled by where a component request was sent.
            logging.error(f"Message handler received an un-awaited component response, dropping it...")

    def _handle_exit(self, item: Message):
        logging.debug(f"Received exit request from {item.conn_handler.addr}")
        item.conn_handler.close()
