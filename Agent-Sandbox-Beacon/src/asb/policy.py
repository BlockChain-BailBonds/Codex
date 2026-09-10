from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .resolver import PathResolver


@dataclass(slots=True)
class GeofenceRule:
    geofence_id: str
    root: str
    recursive: bool = True
    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)
    agents: set[str] | None = None


@dataclass(slots=True)
class PolicyDecision:
    geofences: list[str]
    capabilities: set[str]
    denied: set[str]


class GeofencePolicyEngine:
    """Deterministic deny-wins policy engine for nested filesystem geofences."""

    def __init__(self, resolver: PathResolver, rules: list[GeofenceRule] | None = None):
        self.resolver = resolver
        self.rules = rules or []

    def add_rule(self, rule: GeofenceRule) -> None:
        self.resolver.resolve(rule.root)
        self.rules.append(rule)

    def _matches(self, path: Path, agent_id: str, rule: GeofenceRule) -> bool:
        if rule.agents is not None and agent_id not in rule.agents:
            return False
        root = self.resolver.resolve(rule.root)
        if rule.recursive:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                return False
        return path == root

    def evaluate(self, path: str | Path, agent_id: str) -> PolicyDecision:
        resolved = self.resolver.resolve(path)
        active = [r for r in self.rules if self._matches(resolved, agent_id, r)]
        active.sort(key=lambda r: len(self.resolver.resolve(r.root).parts))
        allowed: set[str] = set()
        denied: set[str] = set()
        for rule in active:
            allowed.update(rule.allow)
            denied.update(rule.deny)
        allowed.difference_update(denied)
        return PolicyDecision(
            geofences=[r.geofence_id for r in active],
            capabilities=allowed,
            denied=denied,
        )
