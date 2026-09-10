from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BeaconState(str, Enum):
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    MOVING = "MOVING"
    SUSPENDED = "SUSPENDED"
    RECOVERING = "RECOVERING"
    DEAD = "DEAD"
    TERMINATED = "TERMINATED"
    ERROR = "ERROR"


class LeaseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    REVOKED_GEOFENCE_EXIT = "REVOKED_GEOFENCE_EXIT"
    REVOKED_POLICY_CHANGE = "REVOKED_POLICY_CHANGE"
    REVOKED_SESSION_END = "REVOKED_SESSION_END"
    REVOKED_SUPERVISOR = "REVOKED_SUPERVISOR"


@dataclass(slots=True)
class Beacon:
    schema: str
    beacon_id: str
    agent_id: str
    session_id: str
    sandbox_id: str
    sandbox_root: str
    active_folder: str
    previous_folder: str | None
    sequence: int
    state: str
    active_geofences: list[str]
    capability_revision: int
    reason: str
    operation_class: str
    transition_id: str
    parent_transition_id: str | None
    pid: int
    host_id: str
    activated_at: str
    heartbeat_at: str
    lease_expires_at: str
    correlation_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Beacon":
        return cls(**data)


@dataclass(slots=True)
class CapabilityLease:
    schema: str
    lease_id: str
    agent_id: str
    session_id: str
    capability: str
    geofence_ids: list[str]
    beacon_sequence: int
    capability_revision: int
    issued_at: str
    expires_at: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityLease":
        return cls(**data)
