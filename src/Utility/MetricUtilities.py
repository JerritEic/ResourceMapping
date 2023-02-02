import logging
import psutil
from pynvml import *


# For now, only support NVIDIA GPUs
def basic_gpu_stats():
    has_gpu = False
    vram = 0
    clock_speed = 0
    try:
        nvmlInit()
        nvmlDeviceGetCount()
        handle = nvmlDeviceGetHandleByIndex(0)
        has_gpu = True
        mem = nvmlDeviceGetMemoryInfo(handle)
        vram = mem.total
        clock_speed = nvmlDeviceGetMaxClockInfo(handle, NVML_CLOCK_GRAPHICS)

        logging.debug(f"GPU Device discovered: {nvmlDeviceGetName(handle)} with memory {vram} and clock speed {clock_speed}")
    except NVMLError as error:
        logging.error(f"NVML error: {error}")
    if has_gpu:
        return dict(
            has_gpu=has_gpu,
            vram_total=vram,
            clock_speed=clock_speed
        )
    else:
        return dict(
            has_gpu=has_gpu
        )


# Gets report of hardware stats that will not change, eg cpu count
def get_static_hardware_stats():
    hardware_report = dict(
        num_cpu=psutil.cpu_count(logical=True),
        cpu_speed=psutil.cpu_freq(percpu=False).max,
        ram=psutil.virtual_memory().total,
        gpu_info=basic_gpu_stats()
    )
    return hardware_report

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}
