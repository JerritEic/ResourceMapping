import configparser
import logging
import subprocess
from os.path import exists
from enum import IntEnum

import minecraft_launcher_lib
from typing import TYPE_CHECKING
if TYPE_CHECKING:
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


# Installs MC if not installed, returns command to run it
def special_start_mc_client_cmd(cwd) -> (str, list[str]):
    minecraft_directory = cwd
    # minecraft_launcher_lib.install.install_minecraft_version("1.12.2", minecraft_directory)
    options = minecraft_launcher_lib.utils.generate_test_options()
    # Set JVM arguments
    options["jvmArguments"] = ["-Xmx2G", "-Xms2G"]
    # Enable custom resolution
    options["customResolution"] = True
    # Set custom resolution
    options["resolutionWidth"] = "960"
    options["resolutionHeight"] = "540"
    return minecraft_launcher_lib.command.get_minecraft_command("1.12.2", minecraft_directory, options), "./"


# Special component commands
special_commands = dict(
    SPECIAL_START_MC_CLIENT=special_start_mc_client_cmd
)


class ComponentHandler:
    def __init__(self, owner: "Application", component_config_file):
        if not exists(component_config_file):
            logging.error(f"Configuration file not found!")
        self.component_config = configparser.ConfigParser()
        self.component_config.read(component_config_file)
        self.components: [Component] = []
        self.owner = owner

    def add_component(self, component: Component):
        # Write this component into the database
        self.owner.db_write_cur.execute("INSERT INTO components VALUES (?, ?)",
                                        (component.name, component.pid))
        self.owner.db.commit()
        self.components.append(component)

    #  Start a process by name and return its PID
    def start_component(self, component_name) -> int:
        # check if this is a known component
        if component_name not in self.component_config:
            logging.error(f"Unrecognized component: {component_name}")
            return -1
        logging.info(f"Starting {component_name}")
        # start the component
        cwd = self.component_config[component_name]['path']
        cmd = self.component_config[component_name]['start']
        proc = self._start_component_command(cmd=cmd, cwd=cwd)
        if proc is not None:
            self.add_component(Component(proc.pid, self.owner.uuid, component_name, process=proc))
            return proc.pid
        else:
            return -1

    def _start_component_command(self, cmd, cwd):
        # Check if there is a special command for starting this component
        if cmd in special_commands:
            cmd, cwd = special_commands[cmd](cwd)
        try:
            logging.debug(f"Executing {cmd}")
            proc = subprocess.Popen(cmd, cwd=cwd)
            if proc.poll() is not None:
                logging.error(f"subprocess {cmd} terminated early with {proc.returncode}")
                return None
            return proc
        except OSError as error:
            logging.error(f"Popen failed for cmd {cmd} with error {error}")
        return None
