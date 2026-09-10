from __future__ import annotations

from .manager import BeaconManager


class WorldModel:
    def __init__(self, manager: BeaconManager):
        self.manager = manager

    def snapshot(self) -> dict:
        agents = []
        for beacon in self.manager.list_beacons():
            agents.append({
                "agent_id": beacon.agent_id,
                "session_id": beacon.session_id,
                "state": beacon.state,
                "location": beacon.active_folder,
                "previous_location": beacon.previous_folder,
                "sequence": beacon.sequence,
                "capability_revision": beacon.capability_revision,
                "geofences": beacon.active_geofences,
                "heartbeat_at": beacon.heartbeat_at,
                "lease_expires_at": beacon.lease_expires_at,
            })
        return {"sandbox": str(self.manager.sandbox_root), "agents": agents}

    def trajectory(self, agent_id: str) -> list[dict]:
        return [e for e in self.manager.transitions.read_all() if e.get("agent_id") == agent_id]
