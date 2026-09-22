import os

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


if __name__ == "__main__":
    print("System Stats:", get_system_stats())
    print("\nTop 3 Processes:")
    for p in get_top_processes(3):
        print(f" - {p.name} (PID: {p.pid}): {p.memory_mb} MB")
    print("\nDisk Usage:", get_disk_usage())
