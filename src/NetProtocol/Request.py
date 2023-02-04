import logging
from enum import IntEnum


class RequestType(IntEnum):
    PING = 0,
    ACK = 1,
    HANDSHAKE = 2,
    METRIC = 3,
    COMPONENT = 4,
    EXIT = 5,
    ERROR = 6


class Request:
    request = None
    encoding = "utf-8"
    m_type = "text/json"

    def __init__(self, action: RequestType = None, args: dict = None, content: dict = None):
        # Allow building a request with an existing content dictionary
        if content is not None:
            self.request = content
            return
        args['action'] = action
        if 'response' not in args:
            args['response'] = False
        # Else build one
        if action == RequestType.PING:
            self._construct_ping_request(args)
        elif action == RequestType.HANDSHAKE:
            self._construct_handshake_request(args)
        elif action == RequestType.METRIC:
            self._construct_metric_request(args)
        elif action == RequestType.COMPONENT:
            self._construct_component_request(args)
        elif action == RequestType.EXIT:
            self._construct_exit_request(args)
        elif action == RequestType.EXIT:
            self._construct_error_request(args)
        elif action is not None:
            logging.debug(f"Unsupported request action type.")

    def _construct_handshake_request(self, args):
        req_fields = ['hw_stats', 'uuid']
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Handshake request missing {req_field}")
                return
        self.request = args

    def _construct_metric_request(self, args):
        # metrics in a request is a list of metrics to return, in a response it is a list of json dicts for each metric
        req_fields = ['metrics', 'period']
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Metric request missing {req_field}")
                return
        self.request = args

    def _construct_component_request(self, args):
        req_fields = ['components', 'component_actions', 'results']
        if 'results' not in args:
            args['results'] = [-1]
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Component request missing {req_field}")
                return
        self.request = args

    def _construct_exit_request(self, args):
        self.request = args

    def _construct_error_request(self, args):
        req_fields = ['error']
        for req_field in req_fields:
            if req_field not in args:
                logging.error(f"Error request missing {req_field}")
                return
        self.request = args

    def _construct_ping_request(self, args):
        pass
