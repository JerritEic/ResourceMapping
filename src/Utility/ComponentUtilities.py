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
