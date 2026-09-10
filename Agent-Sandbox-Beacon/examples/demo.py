from __future__ import annotations

import json
import tempfile
from pathlib import Path

from asb import BeaconManager, FilesystemGateway, GeofencePolicyEngine, GeofenceRule, PathResolver, WorldModel
from asb.errors import PolicyDeniedError

with tempfile.TemporaryDirectory() as sandbox_tmp, tempfile.TemporaryDirectory() as control_tmp:
    root = Path(sandbox_tmp)
    (root / "engineering" / "src").mkdir(parents=True)
    (root / "external").mkdir()
    resolver = PathResolver(root)
    policy = GeofencePolicyEngine(resolver, [
        GeofenceRule("root-read", str(root), allow={"filesystem.read"}),
        GeofenceRule("engineering", str(root / "engineering"), allow={"filesystem.write", "shell.execute"}),
    ])
    manager = BeaconManager(root, policy, control_dir=control_tmp)
    manager.register("agent-07", root / "engineering")
    fs = FilesystemGateway(manager, "agent-07")
    fs.write_text(root / "engineering" / "src" / "hello.txt", "ASB online\n")
    print(fs.read_text(root / "engineering" / "src" / "hello.txt").strip())
    manager.activate("agent-07", root / "external", reason="demo_exit", operation_class="MOVE")
    try:
        manager.authorize("agent-07", "filesystem.write")
    except PolicyDeniedError as exc:
        print("expected geofence revocation:", exc)
    print(json.dumps(WorldModel(manager).snapshot(), indent=2))
    print("transition ledger:", manager.transitions.verify())
    print("capability ledger:", manager.capability_events.verify())
