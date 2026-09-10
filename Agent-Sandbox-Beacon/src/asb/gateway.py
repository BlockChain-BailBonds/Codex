from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from pathlib import Path
from typing import Sequence

from .manager import BeaconManager, iso, utcnow


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class FilesystemGateway:
    """Beacon-aware filesystem/process gateway. Agents should use this instead of raw OS APIs."""

    def __init__(self, manager: BeaconManager, agent_id: str):
        self.manager = manager
        self.agent_id = agent_id

    def _enter(self, folder: Path, capability: str, reason: str):
        beacon = self.manager.activate(self.agent_id, folder, reason=reason, operation_class=capability)
        lease = self.manager.authorize(self.agent_id, capability, expected_sequence=beacon.sequence, expected_revision=beacon.capability_revision)
        return beacon, lease

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        target = self.manager.resolver.resolve(path)
        beacon, lease = self._enter(target.parent, "filesystem.read", "read")
        started = iso(utcnow())
        data = target.read_text(encoding=encoding)
        self.manager.record_operation({"event_type": "OPERATION_FINISHED", "operation_id": str(uuid.uuid4()), "agent_id": self.agent_id, "session_id": beacon.session_id, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "lease_id": lease.lease_id, "operation_type": "READ", "active_location": beacon.active_folder, "resolved_path": str(target), "started_at": started, "ended_at": iso(utcnow()), "result": "ok", "content_sha256": _sha256(target)})
        return data

    def write_text(self, path: str | Path, data: str, encoding: str = "utf-8") -> None:
        target = self.manager.resolver.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        beacon, lease = self._enter(target.parent, "filesystem.write", "write")
        before = _sha256(target)
        started = iso(utcnow())
        tmp = target.with_name(target.name + f".{uuid.uuid4().hex}.tmp")
        tmp.write_text(data, encoding=encoding)
        os.replace(tmp, target)
        after = _sha256(target)
        self.manager.record_operation({"event_type": "OPERATION_FINISHED", "operation_id": str(uuid.uuid4()), "agent_id": self.agent_id, "session_id": beacon.session_id, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "lease_id": lease.lease_id, "operation_type": "WRITE", "active_location": beacon.active_folder, "resolved_path": str(target), "started_at": started, "ended_at": iso(utcnow()), "result": "ok", "delta": {"before_sha256": before, "after_sha256": after}})

    def listdir(self, path: str | Path = ".") -> list[str]:
        target = self.manager.resolver.resolve(path)
        beacon, lease = self._enter(target, "filesystem.read", "list")
        names = sorted(p.name for p in target.iterdir())
        self.manager.record_operation({"event_type": "OPERATION_FINISHED", "operation_id": str(uuid.uuid4()), "agent_id": self.agent_id, "session_id": beacon.session_id, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "lease_id": lease.lease_id, "operation_type": "ENUMERATE", "active_location": beacon.active_folder, "resolved_path": str(target), "ended_at": iso(utcnow()), "result": "ok"})
        return names

    def mkdir(self, path: str | Path) -> Path:
        target = self.manager.resolver.resolve(path)
        beacon, lease = self._enter(target.parent, "filesystem.write", "mkdir")
        target.mkdir(parents=True, exist_ok=True)
        self.manager.record_operation({"event_type": "OPERATION_FINISHED", "operation_id": str(uuid.uuid4()), "agent_id": self.agent_id, "session_id": beacon.session_id, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "lease_id": lease.lease_id, "operation_type": "CREATE_DIRECTORY", "active_location": beacon.active_folder, "resolved_path": str(target), "ended_at": iso(utcnow()), "result": "ok"})
        return target

    def execute(self, command: Sequence[str], cwd: str | Path | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        if not command:
            raise ValueError("command must not be empty")
        if cwd is None:
            current = self.manager.require_live(self.agent_id)
            target_cwd = Path(current.active_folder)
        else:
            target_cwd = self.manager.resolver.resolve(cwd)
        beacon, lease = self._enter(target_cwd, "shell.execute", "execute")
        started = iso(utcnow())
        result = subprocess.run(list(command), cwd=beacon.active_folder, text=True, capture_output=True, timeout=timeout, check=False, shell=False)
        self.manager.record_operation({"event_type": "OPERATION_FINISHED", "operation_id": str(uuid.uuid4()), "agent_id": self.agent_id, "session_id": beacon.session_id, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "lease_id": lease.lease_id, "operation_type": "EXECUTE", "active_location": beacon.active_folder, "command": list(command), "started_at": started, "ended_at": iso(utcnow()), "exit_code": result.returncode, "result": "ok" if result.returncode == 0 else "nonzero"})
        return result
