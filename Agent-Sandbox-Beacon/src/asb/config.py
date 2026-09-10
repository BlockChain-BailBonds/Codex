from __future__ import annotations

import json
from pathlib import Path

from .policy import GeofencePolicyEngine, GeofenceRule
from .resolver import PathResolver, SymlinkPolicy


def load_policy(path: str | Path, sandbox_root: str | Path) -> GeofencePolicyEngine:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    resolver = PathResolver(sandbox_root, SymlinkPolicy(data.get("symlink_policy", "ALLOW_INTERNAL_ONLY")))
    engine = GeofencePolicyEngine(resolver)
    for raw in data.get("geofences", []):
        engine.add_rule(GeofenceRule(
            geofence_id=raw["id"],
            root=raw["root"],
            recursive=raw.get("recursive", True),
            allow=set(raw.get("allow", [])),
            deny=set(raw.get("deny", [])),
            agents=set(raw["agents"]) if raw.get("agents") else None,
        ))
    return engine
