import os
from pathlib import Path

import docker
from docker.errors import DockerException
from pydantic import BaseModel


class CleanupTarget(BaseModel):
    id: str
    name: str
    category: str
    path: str
    size_mb: float
    risk_level: str
    description: str


def get_dir_size_mb(path: Path) -> float:
    total_bytes = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total_bytes += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total_bytes += int(get_dir_size_mb(Path(entry.path)) * 1024 * 1024)
            except (PermissionError, FileNotFoundError):
                continue
    except (PermissionError, FileNotFoundError):
        return 0.0
    return round(total_bytes / (1024 * 1024), 2)


def scan_developer_caches() -> list[CleanupTarget]:
    user_home = Path.home()
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")
    )
    app_data = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming"))

    candidate_locations = [
        {
            "id": "npm_cache",
            "name": "NPM Cache",
            "category": "package_manager",
            "path": local_app_data / "npm-cache",
            "risk_level": "LOW",
            "description": "Cached package downloads for npm.",
        },
        {
            "id": "pip_cache",
            "name": "Pip Cache",
            "category": "package_manager",
            "path": local_app_data / "pip" / "cache",
            "risk_level": "LOW",
            "description": "Cached Python wheels and source distributions.",
        },
        {
            "id": "pnpm_cache",
            "name": "pnpm Store",
            "category": "package_manager",
            "path": local_app_data / "pnpm" / "store",
            "risk_level": "LOW",
            "description": "Global content-addressable store for pnpm packages.",
        },
        {
            "id": "windows_temp",
            "name": "User Temp Folder",
            "category": "system_temp",
            "path": local_app_data / "Temp",
            "risk_level": "LOW",
            "description": "Temporary files created by installed apps and installers.",
        },
    ]

    found_targets = []
    for candidate in candidate_locations:
        p = Path(candidate["path"])
        if p.exists() and p.is_dir():
            size = get_dir_size_mb(p)
            if size > 1.0:
                found_targets.append(
                    CleanupTarget(
                        id=candidate["id"],
                        name=candidate["name"],
                        category=candidate["category"],
                        path=str(p),
                        size_mb=size,
                        risk_level=candidate["risk_level"],
                        description=candidate["description"],
                    )
                )

    return found_targets


def scan_docker_bloat() -> list[CleanupTarget]:
    try:
        client = docker.from_env()
        client.ping()
    except DockerException:
        return []

    targets = []

    dangling_images = client.images.list(filters={"dangling": True})
    dangling_size = sum(img.attrs.get("Size", 0) for img in dangling_images)
    if dangling_size > 1024 * 1024:
        targets.append(
            CleanupTarget(
                id="docker_dangling_images",
                name="Docker Dangling Images",
                category="docker",
                path="Docker Engine",
                size_mb=round(dangling_size / (1024 * 1024), 2),
                risk_level="LOW",
                description="Unused, untagged Docker image layers.",
            )
        )

    stopped_containers = client.containers.list(filters={"status": "exited"})
    if stopped_containers:
        targets.append(
            CleanupTarget(
                id="docker_stopped_containers",
                name=f"Stopped Docker Containers ({len(stopped_containers)})",
                category="docker",
                path="Docker Engine",
                size_mb=0.0,
                risk_level="MEDIUM",
                description="Containers that have exited and are no longer running.",
            )
        )

    volumes = client.volumes.list()
    unused_volumes = [
        v for v in volumes if not v.attrs.get("UsageData", {}).get("RefCount", 1) > 0
    ]
    if unused_volumes:
        targets.append(
            CleanupTarget(
                id="docker_unused_volumes",
                name=f"Unused Docker Volumes ({len(unused_volumes)})",
                category="docker",
                path="Docker Engine",
                size_mb=0.0,
                risk_level="MEDIUM",
                description="Persistent volumes not attached to any container.",
            )
        )

    return targets


if __name__ == "__main__":
    targets = scan_developer_caches()
    print("Found Cleanup Targets:")
    for t in targets:
        print(f" - [{t.risk_level}] {t.name}: {t.size_mb} MB ({t.path})")
