import os
import shutil
from pathlib import Path

import psutil
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    target_id: str
    freed_mb: float
    success: bool
    message: str
    disk_before_gb: float
    disk_after_gb: float


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
                size = item.stat().st_size
                item.unlink()
                freed_bytes += size
            elif item.is_dir():
                for root, _, files in os.walk(item):
                    for f in files:
                        try:
                            freed_bytes += (Path(root) / f).stat().st_size
                        except (PermissionError, FileNotFoundError):
                            pass
                shutil.rmtree(item, ignore_errors=True)
        except (PermissionError, FileNotFoundError):
            continue

    disk_after = get_free_disk_gb()
    freed_mb = round(freed_bytes / (1024 * 1024), 2)

    return ExecutionResult(
        target_id=target_id,
        freed_mb=freed_mb,
        success=True,
        message=f"Cleaned {target.name}",
        disk_before_gb=disk_before,
        disk_after_gb=disk_after,
    )
