import threading
from typing import Union

from src.NetProtocol.Message import Message


# Event object for a message arriving.
class MessageEvent(threading.Event):
    def __init__(self, yield_message):
        super().__init__()
        self.message = None
        self.yield_message = yield_message

    def set_message(self, message: Message):
        self.message = message

    def get_message(self) -> Union[None, Message]:
        if self.is_set():
            return self.message
        else:
            return None
