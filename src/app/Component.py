import atexit
import configparser
import logging
import subprocess
from os.path import exists
import psutil
from typing import TYPE_CHECKING

from src.app.ComponentActions import special_commands
if TYPE_CHECKING:
    from src.app.Application import Application


class Component:
    def __init__(self, pid, name="Unknown", process=None):
        self.name = name
        self.pid = pid
        self.is_active = True
        self.gpu_active = False
        self.process = process


class ComponentHandler:
    def __init__(self, owner: "Application", component_config_file):
        if not exists(component_config_file):
            logging.error(f"Configuration file not found!")

        self.COMPONENT_CONFIG = configparser.ConfigParser()
        self.COMPONENT_CONFIG.read(component_config_file)
        self.components: [Component] = []
        self.owner = owner
        atexit.register(self.stop_components)

    def add_component(self, component: Component):
        # Write this component into the database
        self.owner.db_write_cur.execute("INSERT INTO components VALUES (?, ?)",
                                        (component.name, component.pid))
        self.owner.db.commit()
        self.components.append(component)

    # Check if a component is ready for use
    def ready_component(self, component_name, args: dict):
        if component_name not in self.COMPONENT_CONFIG:
            logging.error(f"Unrecognized component: {component_name}")
            return "UNSUPPORTED"
        if 'ready' not in self.COMPONENT_CONFIG[component_name]:
            logging.error(f"Unsupported command: 'ready' for component {component_name}")
            return "UNSUPPORTED"
        cmd = self.COMPONENT_CONFIG[component_name]['ready']
        if cmd in special_commands:
            return special_commands[cmd](args)
        else:
            # TODO By default check if the process is running
            return "READY"

    #  Start a process by name and return its PID
    def start_component(self, component_name, args: dict) -> int:
        # check if this is a known component
        if component_name not in self.COMPONENT_CONFIG:
            logging.error(f"Unrecognized component: {component_name}")
            return -1
        logging.info(f"Starting {component_name}")
        # start the component
        cwd = self.COMPONENT_CONFIG[component_name]['path']
        cmd = self.COMPONENT_CONFIG[component_name]['start']
        proc = self._start_component_command(cmd=cmd, args=args, cwd=cwd, name=component_name)
        if proc is not None:
            self.add_component(Component(proc.pid, component_name, process=proc))
            return proc.pid
        else:
            return -1

    # Pair a component to another. May launch a process temporarily but closes it after
    def pair_component(self, component_name, args: dict):
        if component_name not in self.COMPONENT_CONFIG:
            logging.error(f"Unrecognized component: {component_name}")
            return "UNSUPPORTED"
        if 'pair' not in self.COMPONENT_CONFIG[component_name]:
            logging.error(f"Unsupported command: 'pair' for component {component_name}")
            return "UNSUPPORTED"
        cmd = self.COMPONENT_CONFIG[component_name]['pair']
        cwd = self.COMPONENT_CONFIG[component_name]['path']
        if cmd in special_commands:
            return special_commands[cmd](cwd, args)
        else:
            # TODO By default check if the process is running
            return "PAIRED"

    def _start_component_command(self, cmd, args, cwd, name):
        # Check if there is a special command for starting this component
        stdout = None
        if cmd in special_commands:
            cmd, cwd, stdout = special_commands[cmd](cwd, args)
        try:
            logging.debug(f"Executing {cmd} in dir {cwd}")
            if stdout is None:
                stdout = open(f"./logs/{self.owner.p_name}_{str(self.owner.uuid)[-5:]}_{name}_out.txt", 'w')
            proc = psutil.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=stdout, stderr=subprocess.STDOUT)
            if proc.poll() is not None:
                logging.error(f"subprocess {cmd} terminated early with {proc.returncode}")
                return None
            return proc
        except OSError as error:
            logging.error(f"Popen failed for cmd {cmd} with error {error}")
        return None

    # make sure that no matter what we kill all the spawned processes.
    def stop_components(self):
        for component in self.components:
            if component.process is not None:
                component.process.kill()
