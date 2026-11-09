import os
import shutil
import time
from pathlib import Path

_last_cpu = None


def _cpu_percent():
    global _last_cpu
    try:
        vals = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        now = (idle, total)
        old, _last_cpu = _last_cpu, now
        if old is None or total == old[1]:
            return None
        return round(100 * (1 - (idle - old[0]) / (total - old[1])), 1)
    except (OSError, ValueError, IndexError):
        return None


def snapshot():
    page = os.sysconf("SC_PAGE_SIZE")
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            mem[k] = int(v.split()[0]) * 1024
    except (OSError, ValueError):
        pass
    try:
        load = os.getloadavg()
    except (OSError, AttributeError):
        load = None
    try:
        proc_count = sum(1 for p in Path("/proc").iterdir() if p.name.isdigit())
    except OSError:
        proc_count = None
    disk = shutil.disk_usage(Path.home())
    return {"cpu_percent": _cpu_percent(), "cpu_cores": os.cpu_count(), "load_average": load,
            "ram_total_bytes": mem.get("MemTotal"), "ram_available_bytes": mem.get("MemAvailable"),
            "storage_total_bytes": disk.total, "storage_free_bytes": disk.free, "process_count": proc_count,
            "temperature_c": _temperature(), "uptime_seconds": _uptime(),
            "termux": Path("/data/data/com.termux/files/usr").exists(), "root": os.geteuid() == 0}


def _temperature():
    for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            raw = int(p.read_text().strip())
            return round(raw / 1000 if raw > 1000 else raw, 1)
        except (OSError, ValueError):
            continue
    return None


def _uptime():
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
