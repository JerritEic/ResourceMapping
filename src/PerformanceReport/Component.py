from enum import Enum

from src.NetworkGraph.NetworkGraph import NetworkNode


class ComponentType(Enum):
    UNKNOWN = 0  # Not yet discovered
    FRONTEND = 1
    SIMULATOR = 2
    RENDERER = 3


class Component:
    def __init__(self, pid, associated_client: NetworkNode,
                 name="Unknown",
                 component_type: ComponentType = ComponentType.UNKNOWN):
        self.name = name
        self.type = component_type
        self.pid = pid
        self.associated_client = associated_client
