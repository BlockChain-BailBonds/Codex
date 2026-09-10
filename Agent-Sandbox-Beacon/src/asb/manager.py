from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import BeaconExpiredError, BeaconMismatchError, PolicyDeniedError, SessionMismatchError, StaleSequenceError
from .ledger import HashChainLedger
from .models import Beacon, BeaconState, CapabilityLease, LeaseStatus
from .policy import GeofencePolicyEngine
from .resolver import PathResolver


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class BeaconManager:
    """Trusted coordinator for location state and geofenced capability leases."""

    def __init__(self, sandbox_root: str | Path, policy: GeofencePolicyEngine, *, control_dir: str | Path | None = None, sandbox_id: str = "sandbox-main", lease_seconds: int = 20):
        self.resolver: PathResolver = policy.resolver
        self.sandbox_root = self.resolver.root
        self.policy = policy
        self.control_dir = Path(control_dir).resolve() if control_dir else self.sandbox_root / ".agent-sandbox"
        self.sandbox_id = sandbox_id
        self.lease_seconds = lease_seconds
        self.beacon_dir = self.control_dir / "beacons"
        self.lease_dir = self.control_dir / "capability-leases"
        self.beacon_dir.mkdir(parents=True, exist_ok=True)
        self.lease_dir.mkdir(parents=True, exist_ok=True)
        self.transitions = HashChainLedger(self.control_dir / "transitions.jsonl")
        self.operations = HashChainLedger(self.control_dir / "operations.jsonl")
        self.capability_events = HashChainLedger(self.control_dir / "capability-events.jsonl")
        self._locks: dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()

    def _lock(self, agent_id: str) -> threading.RLock:
        with self._global_lock:
            return self._locks.setdefault(agent_id, threading.RLock())

    def _atomic_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
        payload = json.dumps(data, indent=2, sort_keys=True)
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _beacon_path(self, agent_id: str) -> Path:
        return self.beacon_dir / f"{agent_id}.json"

    def get(self, agent_id: str) -> Beacon | None:
        path = self._beacon_path(agent_id)
        if not path.exists():
            return None
        return Beacon.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_beacons(self) -> list[Beacon]:
        out: list[Beacon] = []
        for path in sorted(self.beacon_dir.glob("*.json")):
            out.append(Beacon.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return out

    def register(self, agent_id: str, initial_folder: str | Path = ".", metadata: dict[str, Any] | None = None) -> Beacon:
        with self._lock(agent_id):
            existing = self.get(agent_id)
            if existing and existing.state not in {BeaconState.DEAD.value, BeaconState.TERMINATED.value, BeaconState.ERROR.value}:
                return existing
            session_id = str(uuid.uuid4())
            return self.activate(agent_id, initial_folder, reason="register", operation_class="REGISTER", session_id=session_id, metadata=metadata)

    def _leases_for(self, agent_id: str) -> list[CapabilityLease]:
        d = self.lease_dir / agent_id
        if not d.exists():
            return []
        leases: list[CapabilityLease] = []
        for p in d.glob("*.json"):
            leases.append(CapabilityLease.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        return leases

    def _revoke_active_leases(self, agent_id: str, reason: str) -> None:
        for lease in self._leases_for(agent_id):
            if lease.status != LeaseStatus.ACTIVE.value:
                continue
            lease.status = reason
            p = self.lease_dir / agent_id / f"{lease.lease_id}.json"
            self._atomic_json(p, lease.to_dict())
            self.capability_events.append({"event_type": "CAPABILITY_REVOKED", "agent_id": agent_id, "lease_id": lease.lease_id, "capability": lease.capability, "reason": reason, "timestamp": iso(utcnow())})

    def _issue_leases(self, beacon: Beacon, capabilities: set[str]) -> None:
        d = self.lease_dir / beacon.agent_id
        d.mkdir(parents=True, exist_ok=True)
        for capability in sorted(capabilities):
            lease = CapabilityLease(schema="ACG-1", lease_id=str(uuid.uuid4()), agent_id=beacon.agent_id, session_id=beacon.session_id, capability=capability, geofence_ids=list(beacon.active_geofences), beacon_sequence=beacon.sequence, capability_revision=beacon.capability_revision, issued_at=beacon.activated_at, expires_at=beacon.lease_expires_at, status=LeaseStatus.ACTIVE.value)
            self._atomic_json(d / f"{lease.lease_id}.json", lease.to_dict())
            self.capability_events.append({"event_type": "CAPABILITY_GRANTED", "agent_id": beacon.agent_id, "lease_id": lease.lease_id, "capability": capability, "beacon_sequence": beacon.sequence, "capability_revision": beacon.capability_revision, "timestamp": beacon.activated_at})

    def _local_marker(self, folder: Path, agent_id: str) -> Path:
        return folder / ".agent-active" / f"{agent_id}.json"

    def activate(self, agent_id: str, folder: str | Path, *, reason: str, operation_class: str, session_id: str | None = None, metadata: dict[str, Any] | None = None) -> Beacon:
        target = self.resolver.resolve(folder)
        target.mkdir(parents=True, exist_ok=True) if not target.exists() else None
        if not target.is_dir():
            raise BeaconMismatchError(f"active location must be a directory: {target}")

        with self._lock(agent_id):
            previous = self.get(agent_id)
            session = session_id or (previous.session_id if previous else str(uuid.uuid4()))
            if previous and session != previous.session_id and previous.state not in {BeaconState.DEAD.value, BeaconState.TERMINATED.value, BeaconState.ERROR.value}:
                raise SessionMismatchError("cannot replace an active session")

            sequence = 1 if previous is None or session != previous.session_id else previous.sequence + 1
            capability_revision = 1 if previous is None or session != previous.session_id else previous.capability_revision + 1
            decision = self.policy.evaluate(target, agent_id)
            now = utcnow()
            transition_id = str(uuid.uuid4())
            beacon = Beacon(schema="ASB-1", beacon_id=str(uuid.uuid4()), agent_id=agent_id, session_id=session, sandbox_id=self.sandbox_id, sandbox_root=str(self.sandbox_root), active_folder=str(target), previous_folder=previous.active_folder if previous else None, sequence=sequence, state=BeaconState.ACTIVE.value, active_geofences=decision.geofences, capability_revision=capability_revision, reason=reason, operation_class=operation_class, transition_id=transition_id, parent_transition_id=previous.transition_id if previous else None, pid=os.getpid(), host_id=socket.gethostname(), activated_at=iso(now), heartbeat_at=iso(now), lease_expires_at=iso(now + timedelta(seconds=self.lease_seconds)), correlation_id=str(uuid.uuid4()), metadata=metadata or (previous.metadata if previous else {}))

            self._revoke_active_leases(agent_id, LeaseStatus.REVOKED_GEOFENCE_EXIT.value)
            self._atomic_json(self._beacon_path(agent_id), beacon.to_dict())
            self._atomic_json(self._local_marker(target, agent_id), beacon.to_dict())
            if previous and Path(previous.active_folder) != target:
                old = self._local_marker(Path(previous.active_folder), agent_id)
                if old.exists():
                    old.unlink()
                try:
                    old.parent.rmdir()
                except OSError:
                    pass
            self._issue_leases(beacon, decision.capabilities)
            self.transitions.append({"event_type": "BEACON_TRANSITION_COMMITTED", "agent_id": agent_id, "session_id": session, "sequence": sequence, "transition_id": transition_id, "from": previous.active_folder if previous else None, "to": str(target), "geofences": decision.geofences, "capability_revision": capability_revision, "reason": reason, "timestamp": beacon.activated_at})
            return beacon

    def heartbeat(self, agent_id: str) -> Beacon:
        with self._lock(agent_id):
            beacon = self.require_live(agent_id)
            now = utcnow()
            beacon.heartbeat_at = iso(now)
            beacon.lease_expires_at = iso(now + timedelta(seconds=self.lease_seconds))
            self._atomic_json(self._beacon_path(agent_id), beacon.to_dict())
            self._atomic_json(self._local_marker(Path(beacon.active_folder), agent_id), beacon.to_dict())
            for lease in self._leases_for(agent_id):
                if lease.status == LeaseStatus.ACTIVE.value and lease.beacon_sequence == beacon.sequence:
                    lease.expires_at = beacon.lease_expires_at
                    self._atomic_json(self.lease_dir / agent_id / f"{lease.lease_id}.json", lease.to_dict())
            return beacon

    def require_live(self, agent_id: str) -> Beacon:
        beacon = self.get(agent_id)
        if beacon is None:
            raise BeaconMismatchError(f"no beacon for {agent_id}")
        if beacon.state not in {BeaconState.ACTIVE.value, BeaconState.IDLE.value}:
            raise BeaconMismatchError(f"beacon state does not permit operations: {beacon.state}")
        if parse_iso(beacon.lease_expires_at) <= utcnow():
            raise BeaconExpiredError(f"beacon lease expired for {agent_id}")
        return beacon

    def authorize(self, agent_id: str, capability: str, *, expected_sequence: int | None = None, expected_revision: int | None = None) -> CapabilityLease:
        beacon = self.require_live(agent_id)
        if expected_sequence is not None and expected_sequence != beacon.sequence:
            raise StaleSequenceError(f"expected sequence {expected_sequence}, current {beacon.sequence}")
        if expected_revision is not None and expected_revision != beacon.capability_revision:
            raise StaleSequenceError(f"expected capability revision {expected_revision}, current {beacon.capability_revision}")
        now = utcnow()
        for lease in self._leases_for(agent_id):
            if lease.status == LeaseStatus.ACTIVE.value and lease.capability == capability and lease.session_id == beacon.session_id and lease.beacon_sequence == beacon.sequence and lease.capability_revision == beacon.capability_revision and parse_iso(lease.expires_at) > now:
                return lease
        raise PolicyDeniedError(f"capability denied at current geofence: {capability}")

    def record_operation(self, event: dict[str, Any]) -> dict[str, Any]:
        return self.operations.append(event)

    def terminate(self, agent_id: str) -> Beacon:
        with self._lock(agent_id):
            beacon = self.get(agent_id)
            if beacon is None:
                raise BeaconMismatchError(f"no beacon for {agent_id}")
            beacon.state = BeaconState.TERMINATED.value
            self._revoke_active_leases(agent_id, LeaseStatus.REVOKED_SESSION_END.value)
            self._atomic_json(self._beacon_path(agent_id), beacon.to_dict())
            local = self._local_marker(Path(beacon.active_folder), agent_id)
            if local.exists():
                local.unlink()
            return beacon

    def expire_stale(self) -> list[str]:
        expired: list[str] = []
        for beacon in self.list_beacons():
            if beacon.state in {BeaconState.ACTIVE.value, BeaconState.IDLE.value} and parse_iso(beacon.lease_expires_at) <= utcnow():
                beacon.state = BeaconState.DEAD.value
                self._revoke_active_leases(beacon.agent_id, LeaseStatus.EXPIRED.value)
                self._atomic_json(self._beacon_path(beacon.agent_id), beacon.to_dict())
                expired.append(beacon.agent_id)
        return expired

    def reconcile(self, agent_id: str) -> dict[str, Any]:
        beacon = self.get(agent_id)
        if beacon is None:
            return {"agent_id": agent_id, "ok": False, "reason": "missing_authoritative_beacon"}
        local = self._local_marker(Path(beacon.active_folder), agent_id)
        if not local.exists():
            self._atomic_json(local, beacon.to_dict())
            return {"agent_id": agent_id, "ok": True, "repaired": "local_projection_created"}
        projected = Beacon.from_dict(json.loads(local.read_text(encoding="utf-8")))
        if projected.sequence != beacon.sequence or projected.session_id != beacon.session_id:
            self._atomic_json(local, beacon.to_dict())
            return {"agent_id": agent_id, "ok": True, "repaired": "stale_local_projection_replaced"}
        return {"agent_id": agent_id, "ok": True, "repaired": None}
