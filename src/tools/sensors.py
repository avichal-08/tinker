import os
import winreg

import psutil
from pydantic import BaseModel


class SystemStats(BaseModel):
    cpu_percent: float
    ram_percent: float
    disk_percent: float


class ProcessInfo(BaseModel):
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float


class DiskInfo(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


def get_system_stats() -> SystemStats:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent

    path = "C:\\" if os.name == "nt" else "/"
    disk = psutil.disk_usage(path).percent

    return SystemStats(cpu_percent=cpu, ram_percent=ram, disk_percent=disk)


def get_top_processes(limit: int = 5) -> list[ProcessInfo]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            mem_mb = proc.info["memory_info"].rss / (1024 * 1024)
            processes.append(
                ProcessInfo(
                    pid=proc.info["pid"],
                    name=proc.info["name"],
                    memory_mb=round(mem_mb, 2),
                    cpu_percent=proc.info["cpu_percent"] or 0.0,
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda x: x.memory_mb, reverse=True)
    return processes[:limit]


def get_disk_usage() -> DiskInfo:
    path = "C:\\" if os.name == "nt" else "/"
    usage = psutil.disk_usage(path)
    gb_divisor = 1024 * 1024 * 1024

    return DiskInfo(
        total_gb=round(usage.total / gb_divisor, 2),
        used_gb=round(usage.used / gb_divisor, 2),
        free_gb=round(usage.free / gb_divisor, 2),
        percent=usage.percent,
    )


def get_listening_ports() -> list[dict]:
    ports = []
    try:
        connections = psutil.net_connections(kind="inet")
        for conn in connections:
            if conn.status == "LISTEN" and conn.pid and conn.laddr:
                try:
                    proc = psutil.Process(conn.pid)
                    ports.append(
                        {
                            "port": conn.laddr[1],
                            "pid": conn.pid,
                            "process_name": proc.name(),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    except psutil.AccessDenied:
        pass

    unique_ports = {p["port"]: p for p in ports}.values()

    return sorted(unique_ports, key=lambda x: x["port"])


def get_power_and_thermal_stats() -> dict:
    stats = {}

    if hasattr(psutil, "sensors_battery"):
        battery = psutil.sensors_battery()
        if battery:
            time_left = "Unlimited/Unknown"
            if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft > 0:
                time_left = f"{round(battery.secsleft / 60)} minutes"

            stats["battery"] = {
                "percent_charged": round(battery.percent, 1),
                "is_plugged_in": battery.power_plugged,
                "time_left": time_left,
            }
        else:
            stats["battery"] = "No battery detected (desktop or restricted VM)."

    if hasattr(psutil, "cpu_freq"):
        freq = psutil.cpu_freq()
        if freq:
            stats["cpu_freq"] = {
                "current_mhz": round(freq.current, 1),
                "min_mhz": round(freq.min, 1),
                "max_mhz": round(freq.max, 1),
            }

    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        if temps:
            simplified_temps = {}
            for name, entries in temps.items():
                simplified_temps[name] = [
                    round(e.current, 1) for e in entries if e.current > 0
                ]
            stats["temperatures_celsius"] = simplified_temps
        else:
            stats["temperatures_celsius"] = (
                "Hardware temperature sensors not exposed by OS."
            )

    return stats


def get_startup_programs() -> list[dict]:
    startup_apps = []

    hives = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]

    for hive, subkey in hives:
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        startup_apps.append(
                            {
                                "name": name,
                                "command": value,
                                "scope": "Current User"
                                if hive == winreg.HKEY_CURRENT_USER
                                else "System-Wide",
                            }
                        )
                        i += 1
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            continue

    return startup_apps


if __name__ == "__main__":
    print("System Stats:", get_system_stats())
    print("\nTop 3 Processes:")
    for p in get_top_processes(3):
        print(f" - {p.name} (PID: {p.pid}): {p.memory_mb} MB")
    print("\nDisk Usage:", get_disk_usage())
