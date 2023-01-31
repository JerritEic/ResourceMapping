import struct
import sys
# controllers.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.NetProtocol.ConnectionHandler import ConnectionHandler
from src.NetProtocol.Request import Request
from src.Utility.NetworkUtilities import json_encode


class Message:
    def __init__(self, is_received: bool = True, handler: "ConnectionHandler" = None, content: Request = None):
        self.is_received = is_received
        self.conn_handler = handler
        self.json_header_len = None
        self.json_header = None
        self.CSeq = -1
        self.content = content
        self._serialized = None

    def get_serialized(self, force_reserialize=False):
        if force_reserialize or self._serialized is None:
            self._serialize()
        return self._serialized

    def _serialize(self):
        content_bytes = json_encode(self.content.request, self.content.encoding)
        self._construct_header(len(content_bytes))
        json_header_bytes = json_encode(self.json_header, "utf-8")
        message_hdr_bytes = struct.pack(">H", len(json_header_bytes))
        message = message_hdr_bytes + json_header_bytes + content_bytes
        self._serialized = message

    def _construct_header(self, content_bytes_len):
        self.json_header = dict(
            byteorder=sys.byteorder,
            content_length=content_bytes_len,
            content_type=self.content.m_type,
            content_encoding=self.content.encoding,
            CSeq=self.CSeq
        )
