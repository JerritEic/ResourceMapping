import logging
from enum import IntEnum


class RequestType(IntEnum):
    PING = 0,
    ACK = 1,
    HANDSHAKE = 2,
    METRIC = 3,
    EXIT = 4


class Request:
    request = None
    encoding = "utf-8"
    m_type = "text/json"

    def __init__(self, action: RequestType = None, args: dict = None, content: dict = None):
        # Allow building a request with an existing content dictionary
        if content is not None:
            self.request = content
            return
        # Else build one
        if action == RequestType.PING:
            self._construct_ping_request(args)
        elif action == RequestType.HANDSHAKE:
            self._construct_handshake_request(args)
        elif action == RequestType.METRIC:
            self._construct_metric_request(args)
        elif action == RequestType.EXIT:
            self._construct_exit_request()
        elif action is not None:
            logging.debug(f"Unsupported request action type.")

    def _construct_handshake_request(self, args):
        req_fields = ['action', 'response', 'hw_stats', 'uuid']
        args['action'] = RequestType.HANDSHAKE
        if 'response' not in args:
            args['response'] = False
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Handshake missing {req_field}")
                return
        self.request = args

    def _construct_metric_request(self, args):
        # metrics in a request is a list of metrics to return, in a response it is a list of json dicts for each metric
        req_fields = ['action', 'response', 'metrics', 'period']
        args['action'] = RequestType.METRIC
        if 'response' not in args:
            args['response'] = False
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Metric request missing {req_field}")
                return
        self.request = args

    def _construct_exit_request(self):
        content = dict(action=RequestType.EXIT)
        self.request = content

    def _construct_ping_request(self, args):
        pass
