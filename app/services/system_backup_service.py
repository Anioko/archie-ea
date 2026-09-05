"""Repository-managed PostgreSQL backup artefacts for the Settings UI."""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


class BackupError(RuntimeError):
    """A backup operation could not be completed safely."""


class SystemBackupService:
    _NAME = re.compile(r"^backup_\d{8}T\d{6}Z_[0-9a-f]{8}\.dump$")

    def __init__(self, backup_dir: str | Path, database_url: str):
        self.backup_dir = Path(backup_dir)
        self.database_url = database_url
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        if not self._NAME.fullmatch(name or ""):
            raise BackupError("Invalid backup name")
        return self.backup_dir / name

    @staticmethod
    def _metadata(path: Path) -> dict:
        stat = path.stat()
        return {
            "name": path.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def list(self) -> list[dict]:
        paths = [p for p in self.backup_dir.glob("backup_*.dump") if self._NAME.fullmatch(p.name)]
        return [self._metadata(p) for p in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)]

    def create(self) -> dict:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"backup_{stamp}_{uuid.uuid4().hex[:8]}.dump"
        final_path = self.path_for(name)
        temporary = final_path.with_suffix(".partial")
        try:
            subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(temporary), self.database_url],
                check=True,
                capture_output=True,
                text=True,
            )
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise BackupError("pg_dump did not produce a backup archive")
            os.replace(temporary, final_path)
            return self._metadata(final_path)
        except FileNotFoundError as exc:
            raise BackupError("PostgreSQL backup tools are not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise BackupError((exc.stderr or "pg_dump failed").strip()) from exc
        finally:
            temporary.unlink(missing_ok=True)

    def delete(self, name: str) -> None:
        path = self.path_for(name)
        if not path.is_file():
            raise FileNotFoundError(name)
        path.unlink()

    def restore(self, name: str) -> dict:
        source = self.path_for(name)
        if not source.is_file():
            raise FileNotFoundError(name)
        safety = self.create()
        try:
            subprocess.run(
                ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "--dbname", self.database_url, str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise BackupError("PostgreSQL restore tools are not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise BackupError((exc.stderr or "pg_restore failed").strip()) from exc
        return {"restored": name, "safety_backup": safety["name"]}
