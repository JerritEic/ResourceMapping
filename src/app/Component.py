import atexit
import configparser
import logging
import subprocess
import time
from os.path import exists

import psutil
from mcstatus import JavaServer
import minecraft_launcher_lib
from typing import TYPE_CHECKING
from src.Utility.ComponentUtilities import check_if_jar_running

if TYPE_CHECKING:
    from src.app.Application import Application

COMPONENT_CONFIG = dict()


class Component:
    def __init__(self, pid, name="Unknown", process=None):
        self.name = name
        self.pid = pid
        self.is_active = True
        self.gpu_active = False
        self.process = process


# Installs MC if not installed, returns command to run it
def special_start_mc_client_cmd(cwd, args) -> (list[str], str, int):
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

    # Auto connect to server
    if "server_ip" in args and "server_port" in args:
        options["port"] = str(args["server_port"])
        options["server"] = str(args["server_ip"])
    return minecraft_launcher_lib.command.get_minecraft_command("1.12.2", minecraft_directory, options), "./", subprocess.DEVNULL


def special_start_mc_server_cmd(cwd, args) -> (list[str], str, int):
    # Kill any PID running opencraft.jar
    cmd = [f"{cwd}jre-legacy/bin/java.exe", "-jar", f"{cwd}opencraft.jar"]
    check_if_jar_running("opencraft", kill=True)
    if "server_port" in args:
        cmd.append("--port")
        cmd.append(str(args["server_port"]))
    return cmd, "./", subprocess.DEVNULL


def special_ready_mc_server(args):
    port = int(COMPONENT_CONFIG['game-server']['port']) if "server_port" not in args else int(args["server_port"])
    server = JavaServer("localhost", port)
    try:
        status = server.status()
        logging.debug(f"Received from server: {status.latency} ms with {status.players.max}")
    except ConnectionRefusedError:
        logging.error(f"Server refused connection.")
        return "UNREADY"
    return "READY"


# Special component commands
special_commands = dict(
    SPECIAL_START_MC_CLIENT=special_start_mc_client_cmd,
    SPECIAL_START_MC_SERVER=special_start_mc_server_cmd,
    SPECIAL_READY_MC_SERVER=special_ready_mc_server
)


class ComponentHandler:
    def __init__(self, owner: "Application", component_config_file):
        if not exists(component_config_file):
            logging.error(f"Configuration file not found!")
        global COMPONENT_CONFIG
        COMPONENT_CONFIG = configparser.ConfigParser()
        COMPONENT_CONFIG.read(component_config_file)
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
        if component_name not in COMPONENT_CONFIG:
            logging.error(f"Unrecognized component: {component_name}")
            return "UNSUPPORTED"
        if 'ready' not in COMPONENT_CONFIG[component_name]:
            logging.error(f"Unsupported command: 'ready' for component {component_name}")
            return "UNSUPPORTED"
        cmd = COMPONENT_CONFIG[component_name]['ready']
        if cmd in special_commands:
            return special_commands[cmd](args)
        else:
            # TODO By default check if the process is running
            return "READY"

    #  Start a process by name and return its PID
    def start_component(self, component_name, args: dict) -> int:
        # check if this is a known component
        if component_name not in COMPONENT_CONFIG:
            logging.error(f"Unrecognized component: {component_name}")
            return -1
        logging.info(f"Starting {component_name}")
        # start the component
        cwd = COMPONENT_CONFIG[component_name]['path']
        cmd = COMPONENT_CONFIG[component_name]['start']
        proc = self._start_component_command(cmd=cmd, args=args, cwd=cwd, name=component_name)
        if proc is not None:
            self.add_component(Component(proc.pid, component_name, process=proc))
            return proc.pid
        else:
            return -1

    def _start_component_command(self, cmd, args, cwd, name):
        # Check if there is a special command for starting this component
        stdout = None
        if cmd in special_commands:
            cmd, cwd, stdout = special_commands[cmd](cwd, args)
        try:
            logging.debug(f"Executing {cmd} in dir {cwd}")
            if stdout is None:
                stdout = open(f"./logs/{self.owner.p_name}_{str(self.owner.uuid)[-5:]}_{name}_out.txt", 'w')
            proc = psutil.Popen(cmd, cwd=cwd, stdout=stdout, stderr=subprocess.STDOUT)
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
