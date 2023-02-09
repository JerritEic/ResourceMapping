import logging
from os.path import exists
from threading import Event

import psutil


def check_if_jar_running(jar_name, kill=False):
    listOfProcessObjects = []
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            if 'java' in proc.exe():
                if jar_name.lower() in proc.cmdline()[1].lower():
                    listOfProcessObjects.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if kill:
        for proc in listOfProcessObjects:
            proc.kill()
    return listOfProcessObjects


# read from a process stdout, looking for target strings.
def read_proc_stdout_until(proc, targets: tuple[str, Event]):
    targets = targets if isinstance(targets, list) else [targets]
    for b_line in iter(proc.stdout.readline, b''):
        line = b_line.decode('utf-8')
        logging.debug(line)
        for t in targets:
            if t[0] in line:
                t[1].set()


# Returns true if file at 'file_path' exists and contains string 'target'
def search_file(file_path, target):
    if file_path is None or not exists(file_path):
        return False
    with open(file_path, 'r') as fp:
        for row in fp.readlines():
            if target in row:
                return True
    return False
