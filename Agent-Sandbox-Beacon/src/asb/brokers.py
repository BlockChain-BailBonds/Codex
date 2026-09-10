from __future__ import annotations

from dataclasses import dataclass

from .errors import PolicyDeniedError
from .manager import BeaconManager


@dataclass(slots=True)
class SecurityPosition:
    agent_id: str
    filesystem_location: str
    filesystem_geofences: list[str]
    beacon_sequence: int
    capability_revision: int


class CapabilityBroker:
    """Generic broker for tool/network/data/credential/process capability checks.

    This does not itself implement an OS firewall. It is intended to sit in the
    trusted host/hypervisor control plane and back concrete adapters.
    """

    def __init__(self, manager: BeaconManager):
        self.manager = manager

    def position(self, agent_id: str) -> SecurityPosition:
        beacon = self.manager.require_live(agent_id)
        return SecurityPosition(
            agent_id=agent_id,
            filesystem_location=beacon.active_folder,
            filesystem_geofences=list(beacon.active_geofences),
            beacon_sequence=beacon.sequence,
            capability_revision=beacon.capability_revision,
        )

    def authorize_tool(self, agent_id: str, tool_name: str):
        return self.manager.authorize(agent_id, f"tool.{tool_name}")

    def authorize_network_host(self, agent_id: str, host: str):
        self.manager.authorize(agent_id, "network.connect")
        try:
            return self.manager.authorize(agent_id, f"network.host:{host}")
        except PolicyDeniedError:
            return self.manager.authorize(agent_id, "network.host:*")

    def authorize_credential(self, agent_id: str, credential_name: str):
        return self.manager.authorize(agent_id, f"credential.{credential_name}")

    def authorize_data(self, agent_id: str, data_zone: str):
        return self.manager.authorize(agent_id, f"data.{data_zone}")
