import os
from pathlib import Path

import docker
import psutil
from docker.errors import DockerException
from pydantic import BaseModel
from send2trash import send2trash


class ExecutionResult(BaseModel):
    target_id: str
    freed_mb: float
    success: bool
    message: str
    disk_before_gb: float
    disk_after_gb: float


class ProcessResult(BaseModel):
    pid: int
    name: str
    success: bool
    message: str
    freed_mb: float


def get_free_disk_gb() -> float:
    path = "C:\\" if os.name == "nt" else "/"
    return round(psutil.disk_usage(path).free / (1024 * 1024 * 1024), 2)


def execute_cache_cleanup(target_path: str, target_id: str) -> ExecutionResult:
    target = Path(target_path)

    if not target.exists() or len(target.parts) < 3:
        return ExecutionResult(
            target_id=target_id,
            freed_mb=0.0,
            success=False,
            message="Refused: Path is invalid or too close to root.",
            disk_before_gb=get_free_disk_gb(),
            disk_after_gb=get_free_disk_gb(),
        )

    disk_before = get_free_disk_gb()
    freed_bytes = 0

    for item in target.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                freed_bytes += item.stat().st_size
            elif item.is_dir():
                for root, _, files in os.walk(item):
                    for f in files:
                        try:
                            freed_bytes += (Path(root) / f).stat().st_size
                        except (PermissionError, FileNotFoundError):
                            pass

            send2trash(str(item))

        except (PermissionError, FileNotFoundError):
            continue

    disk_after = get_free_disk_gb()
    freed_mb = round(freed_bytes / (1024 * 1024), 2)

    return ExecutionResult(
        target_id=target_id,
        freed_mb=freed_mb,
        success=True,
        message=f"Moved contents of {target.name} to Recycle Bin",
        disk_before_gb=disk_before,
        disk_after_gb=disk_after,
    )


def execute_terminate_process(pid: int) -> ProcessResult:
    try:
        proc = psutil.Process(pid)
        name = proc.name()

        protected = [
            "explorer.exe",
            "svchost.exe",
            "smss.exe",
            "csrss.exe",
            "wininit.exe",
            "services.exe",
            "lsass.exe",
            "winlogon.exe",
            "system",
            "registry",
            "memorycompression",
        ]

        if name.lower() in protected or pid <= 4:
            return ProcessResult(
                pid=pid,
                name=name,
                success=False,
                message="Refused: Protected system process.",
                freed_mb=0.0,
            )

        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
        proc.terminate()
        proc.wait(timeout=3)

        return ProcessResult(
            pid=pid,
            name=name,
            success=True,
            message=f"Terminated {name}",
            freed_mb=mem_mb,
        )

    except psutil.NoSuchProcess:
        return ProcessResult(
            pid=pid,
            name="Unknown",
            success=False,
            message="Process no longer exists.",
            freed_mb=0.0,
        )
    except psutil.AccessDenied:
        return ProcessResult(
            pid=pid,
            name="Unknown",
            success=False,
            message="Access denied. Administrator rights required.",
            freed_mb=0.0,
        )
    except Exception as e:
        return ProcessResult(
            pid=pid, name="Unknown", success=False, message=str(e), freed_mb=0.0
        )


def execute_docker_cleanup(target_id: str) -> ExecutionResult:
    disk_before = get_free_disk_gb()
    freed_bytes = 0
    message = ""

    try:
        client = docker.from_env()

        if target_id == "docker_dangling_images":
            result = client.images.prune(filters={"dangling": True})
            freed_bytes = result.get("SpaceReclaimed") or 0
            message = "Pruned dangling images."

        elif target_id == "docker_stopped_containers":
            result = client.containers.prune()
            freed_bytes = result.get("SpaceReclaimed") or 0
            deleted = result.get("ContainersDeleted") or []
            message = f"Pruned {len(deleted)} stopped containers."

        elif target_id == "docker_unused_volumes":
            result = client.volumes.prune()
            freed_bytes = result.get("SpaceReclaimed") or 0
            deleted = result.get("VolumesDeleted") or []
            message = f"Pruned {len(deleted)} unused volumes."

        else:
            return ExecutionResult(
                target_id=target_id,
                freed_mb=0.0,
                success=False,
                message=f"Unknown Docker target ID: {target_id}",
                disk_before_gb=disk_before,
                disk_after_gb=disk_before,
            )

    except DockerException as e:
        return ExecutionResult(
            target_id=target_id,
            freed_mb=0.0,
            success=False,
            message=f"Docker error: {str(e)}",
            disk_before_gb=disk_before,
            disk_after_gb=disk_before,
        )

    disk_after = get_free_disk_gb()
    return ExecutionResult(
        target_id=target_id,
        freed_mb=round(freed_bytes / (1024 * 1024), 2),
        success=True,
        message=message,
        disk_before_gb=disk_before,
        disk_after_gb=disk_after,
    )
