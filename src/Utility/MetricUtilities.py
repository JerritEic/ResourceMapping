import psutil


# Gets report of hardware stats that will not change, eg cpu count
def get_static_hardware_stats():
    hardware_report = dict(
        num_cpu=psutil.cpu_count(logical=True),
        cpu_speed=psutil.cpu_freq(percpu=False).max,
        ram=psutil.virtual_memory().total
    )
    return hardware_report
