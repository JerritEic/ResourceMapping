import configparser
import logging
import subprocess
from os.path import exists
from enum import IntEnum

from src.NetworkGraph.NetworkGraph import NetworkNode
from src.app.Application import Application


class Component:
    def __init__(self, pid, associated_client_uuid,
                 name="Unknown", process=None):
        self.name = name
        self.pid = pid
        self.associated_client_uuid = associated_client_uuid
        self.is_active = True
        self.gpu_active = False
        self.process = process


class ComponentHandler:
    def __init__(self, owner: Application, component_config_file):
        if not exists(component_config_file):
            logging.error(f"Configuration file not found!")
        self.component_config = configparser.ConfigParser()
        self.component_config.read(component_config_file)
        self.components: [Component] = []
        self.owner = owner

    def add_component(self, component: Component):
        self.owner.db_write_cur.execute("INSERT INTO components VALUES (?, ?)",
                                        (component.name, component.pid))
        self.owner.db.commit()
        self.components.append(component)

    #  Start a process and return a component object with its PID
    def start_component(self, component_name):
        # check if this is a known component
        if component_name not in self.component_config:
            logging.error(f"Unrecognized component: {component_name}")
            return False
        # start the component
        cwd = self.component_config[component_name]['path']
        cmd = self.component_config[component_name]['cmd']
        proc = self._run_command(cmd=cmd, cwd=cwd)
        if proc is not None:
            self.add_component(Component(proc.pid, self.owner.uuid, component_name, process=proc))
            return True
        else:
            return False

    def _run_command(self, cmd, cwd):
        try:
            proc = subprocess.Popen(cmd, cwd=cwd)
            if proc.poll() is not None:
                logging.error(f"subprocess {cmd} terminated early with {proc.returncode}")
                return None
            return proc
        except OSError as error:
            logging.error(f"Popen failed for cmd {cmd} with error {error}")
        return None
