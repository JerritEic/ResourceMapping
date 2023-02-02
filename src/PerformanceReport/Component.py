from enum import IntEnum

from src.NetworkGraph.NetworkGraph import NetworkNode


class ComponentType(IntEnum):
    UNKNOWN = 0  # Not yet discovered
    RESOURCE_SERVER = 1
    RESOURCE_CLIENT = 2
    FRONTEND = 3
    SIMULATOR = 4
    RENDERER = 5


class Component:
    def __init__(self, pid, associated_client: NetworkNode,
                 name="Unknown",
                 component_type: ComponentType = ComponentType.UNKNOWN):
        self.name = name
        self.type = component_type
        self.pid = pid
        self.associated_client = associated_client
        self.is_active = True
        self.gpu_active = False
