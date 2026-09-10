from __future__ import annotations

import json
from pathlib import Path
import pytest
from asb import BeaconManager, CapabilityBroker, FilesystemGateway, GeofencePolicyEngine, GeofenceRule, PathResolver
from asb.errors import BeaconExpiredError, PolicyDeniedError, SandboxEscapeError, StaleSequenceError
from asb.ledger import HashChainLedger


def stack(tmp_path: Path, lease_seconds: int = 20):
    root = tmp_path / "sandbox"; control = tmp_path / "control"
    (root / "engineering" / "src").mkdir(parents=True); (root / "external").mkdir(); (root / "quarantine").mkdir()
    resolver = PathResolver(root)
    policy = GeofencePolicyEngine(resolver, [
        GeofenceRule("root", str(root), allow={"filesystem.read"}),
        GeofenceRule("engineering", str(root / "engineering"), allow={"filesystem.write", "shell.execute", "network.connect", "network.host:example.com", "tool.test"}),
        GeofenceRule("quarantine", str(root / "quarantine"), allow={"tool.explain"}, deny={"filesystem.write", "shell.execute", "network.connect"}),
    ])
    manager = BeaconManager(root, policy, control_dir=control, lease_seconds=lease_seconds); manager.register("agent-1", root / "engineering")
    return root, control, manager


def test_register_and_beacon_projection(tmp_path):
    root, _, manager = stack(tmp_path); b = manager.get("agent-1"); assert b is not None; assert Path(b.active_folder) == root / "engineering"; assert (root / "engineering" / ".agent-active" / "agent-1.json").exists()

def test_move_increments_sequence_and_moves_projection(tmp_path):
    root, _, manager = stack(tmp_path); before = manager.get("agent-1"); after = manager.activate("agent-1", root / "engineering" / "src", reason="test", operation_class="MOVE"); assert after.sequence == before.sequence + 1; assert not (root / "engineering" / ".agent-active" / "agent-1.json").exists(); assert (root / "engineering" / "src" / ".agent-active" / "agent-1.json").exists()

def test_geofence_revokes_skill_on_exit(tmp_path):
    root, _, manager = stack(tmp_path); manager.authorize("agent-1", "filesystem.write"); manager.activate("agent-1", root / "external", reason="leave", operation_class="MOVE");
    with pytest.raises(PolicyDeniedError): manager.authorize("agent-1", "filesystem.write")

def test_stale_sequence_denied(tmp_path):
    root, _, manager = stack(tmp_path); old = manager.get("agent-1"); manager.activate("agent-1", root / "engineering" / "src", reason="move", operation_class="MOVE")
    with pytest.raises(StaleSequenceError): manager.authorize("agent-1", "filesystem.write", expected_sequence=old.sequence)

def test_filesystem_gateway_tracks_location(tmp_path):
    root, _, manager = stack(tmp_path); fs = FilesystemGateway(manager, "agent-1"); p = root / "engineering" / "src" / "x.txt"; fs.write_text(p, "hello"); assert fs.read_text(p) == "hello"; assert Path(manager.get("agent-1").active_folder) == p.parent; assert manager.operations.verify()[0]

def test_shell_requires_geofenced_capability(tmp_path):
    root, _, manager = stack(tmp_path); fs = FilesystemGateway(manager, "agent-1"); ok = fs.execute(["python", "-c", "print('ok')"], cwd=root / "engineering"); assert ok.returncode == 0; manager.activate("agent-1", root / "external", reason="leave", operation_class="MOVE")
    with pytest.raises(PolicyDeniedError): fs.execute(["python", "-c", "print('no')"], cwd=root / "external")

def test_sandbox_escape_rejected(tmp_path):
    root, _, manager = stack(tmp_path)
    with pytest.raises(SandboxEscapeError): manager.resolver.resolve(root.parent / "outside")

def test_symlink_escape_rejected(tmp_path):
    root, _, manager = stack(tmp_path); outside = tmp_path / "outside"; outside.mkdir(); link = root / "engineering" / "src" / "out"; link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SandboxEscapeError): manager.resolver.resolve(link / "secret.txt")

def test_network_broker_requires_host_scope(tmp_path):
    _, _, manager = stack(tmp_path); broker = CapabilityBroker(manager); broker.authorize_network_host("agent-1", "example.com")
    with pytest.raises(PolicyDeniedError): broker.authorize_network_host("agent-1", "evil.example")

def test_quarantine_deny_wins(tmp_path):
    root, _, manager = stack(tmp_path); manager.activate("agent-1", root / "quarantine", reason="quarantine", operation_class="MOVE")
    with pytest.raises(PolicyDeniedError): manager.authorize("agent-1", "filesystem.write")
    manager.authorize("agent-1", "tool.explain")

def test_ledger_detects_tamper(tmp_path):
    p = tmp_path / "events.jsonl"; ledger = HashChainLedger(p); ledger.append({"event_type": "A", "value": 1}); ledger.append({"event_type": "B", "value": 2}); assert ledger.verify() == (True, 2); rows = ledger.read_all(); rows[0]["value"] = 999; p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"); assert ledger.verify()[0] is False

def test_reconcile_recreates_missing_projection(tmp_path):
    root, _, manager = stack(tmp_path); marker = root / "engineering" / ".agent-active" / "agent-1.json"; marker.unlink(); result = manager.reconcile("agent-1"); assert result["ok"]; assert marker.exists()

def test_expired_beacon_denies_actions(tmp_path):
    _, _, manager = stack(tmp_path, lease_seconds=0)
    with pytest.raises(BeaconExpiredError): manager.require_live("agent-1")
