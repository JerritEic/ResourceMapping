# Installs MC if not installed, returns command to run it
import glob
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import minecraft_launcher_lib
from mcstatus import JavaServer

from src.Utility.ComponentUtilities import check_if_jar_running, search_file, read_proc_stdout_until


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
    return minecraft_launcher_lib.command.get_minecraft_command("1.12.2", minecraft_directory,
                                                                options), "./", subprocess.DEVNULL


def special_start_mc_server_cmd(cwd, args) -> (list[str], str, int):
    # Kill any PID running opencraft.jar
    cmd = [f"{cwd}jre-legacy/bin/java.exe", "-jar", f"{cwd}opencraft.jar"]
    check_if_jar_running("opencraft", kill=True)
    if "server_port" in args:
        cmd.append("--port")
        cmd.append(str(args["server_port"]))
    return cmd, "./", subprocess.DEVNULL


def special_pair_moonlight_client(cwd, args):
    # First pair with where we will connect
    remote_ip = "localhost" if 'remote_ip' not in args else args['remote_ip']
    pin = "2048" if 'pin' not in args else args['pin']
    cmd = [f"{cwd}Moonlight.exe", "pair", remote_ip, "--pin", str(pin)]
    logging.debug(f"Running {cwd}{cmd}")
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(40)  # Pairing the client can be a lengthy process.
    # get most recent output log since moonlight doesnt print to stdout
    p.kill()
    list_of_files = glob.glob(f"{cwd}Moonlight-*")
    latest_file = max(list_of_files, key=os.path.getctime)
    if not search_file(latest_file, "resolved"):
        logging.error("Pairing of moonlight client failed or log file not found.")
        # We still try anyway. These log files are unreliable
        # return "UNPAIRED"
    return "PAIRED"


def special_start_moonlight_client_cmd(cwd, args) -> (list[str], str, int):
    remote_ip = "localhost" if 'remote_ip' not in args else args['remote_ip']
    cmd = [f"{cwd}Moonlight.exe", "stream", remote_ip, "desktop"]
    return cmd, "./", subprocess.DEVNULL


def special_pair_sunshine_server(cwd, args):
    pin = "2048" if 'pin' not in args else args['pin']
    # start sunshine in pin to stdin mode
    cmd = [f"{cwd}sunshine.exe", "-0"]
    logging.debug(f"Running {cwd}{cmd}")
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    found_verified = threading.Event()
    found_input_pin = threading.Event()
    t = threading.Thread(target=read_proc_stdout_until,
                         args=(p, [("verified", found_verified), ("insert pin", found_input_pin)]))
    t.start()
    start_t = time.time()
    while time.time() - start_t < 60:
        if found_input_pin.is_set():
            logging.debug(f"Pairing sunshine server requests pin")
            # process is now expecting input of a pin
            p.stdin.write((pin + "\n").encode('UTF-8'))
            p.stdin.flush()
            found_input_pin.clear()
        if found_verified.is_set():
            logging.debug("Successfully paired sunshine server!")
            p.kill()
            return "PAIRED"
    logging.debug(f"Pairing sunshine server pin request timed out.")
    p.kill()
    return "UNPAIRED"


# not currently used
def special_start_sunshine_server_cmd(cwd, args) -> (list[str], str, int):
    # start sunshine
    cmd = [f"{cwd}sunshine.exe"]
    return cmd, "./", subprocess.DEVNULL


def special_ready_mc_server(args):
    port = 25575 if "server_port" not in args else int(args["server_port"])
    server = JavaServer("localhost", port)
    try:
        status = server.status()
        logging.debug(f"Received from server: {status.latency} ms with {status.players.max}")
    except ConnectionRefusedError:
        logging.error(f"Server refused connection.")
        return "UNREADY"
    return "READY"


# Special component commands, these can be specified in a component.ini file
special_commands = dict(
    SPECIAL_START_MC_CLIENT=special_start_mc_client_cmd,
    SPECIAL_START_MC_SERVER=special_start_mc_server_cmd,
    SPECIAL_PAIR_MOONLIGHT_CLIENT=special_pair_moonlight_client,
    SPECIAL_START_MOONLIGHT_CLIENT=special_start_moonlight_client_cmd,
    SPECIAL_START_SUNSHINE_SERVER=special_start_sunshine_server_cmd,
    SPECIAL_PAIR_SUNSHINE_SERVER=special_pair_sunshine_server,
    SPECIAL_READY_MC_SERVER=special_ready_mc_server
)
