from enum import Enum


class ComponentType(Enum):
    UNKNOWN = 0  # Not yet discovered
    FRONTEND = 1
    SIMULATOR = 2
    RENDERER = 3


class Component:
    def __init__(self, name, component_type: ComponentType, pid, associated_client):
        self.name = name
        self.type = component_type
        self.pid = pid
        self.associated_client = associated_client
