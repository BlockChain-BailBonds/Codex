from __future__ import annotations

import argparse
import json

from .config import load_policy
from .manager import BeaconManager
from .world_model import WorldModel


def build_manager(args) -> BeaconManager:
    policy = load_policy(args.config, args.root)
    return BeaconManager(args.root, policy, control_dir=args.control)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="asb", description="Agent Sandbox Beacon + capability geofence")
    p.add_argument("--root", required=True, help="agent sandbox root")
    p.add_argument("--config", required=True, help="JSON geofence policy")
    p.add_argument("--control", help="trusted control directory; recommended outside sandbox root")
    sub = p.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register"); reg.add_argument("agent"); reg.add_argument("folder", nargs="?", default=".")
    where = sub.add_parser("where"); where.add_argument("agent")
    move = sub.add_parser("move"); move.add_argument("agent"); move.add_argument("folder")
    sub.add_parser("status"); sub.add_parser("verify")
    rec = sub.add_parser("reconcile"); rec.add_argument("agent")
    term = sub.add_parser("terminate"); term.add_argument("agent")
    args = p.parse_args(argv)
    manager = build_manager(args)
    if args.cmd == "register": print(json.dumps(manager.register(args.agent, args.folder).to_dict(), indent=2))
    elif args.cmd == "where":
        b = manager.get(args.agent); print(json.dumps(b.to_dict() if b else None, indent=2))
    elif args.cmd == "move": print(json.dumps(manager.activate(args.agent, args.folder, reason="cli_move", operation_class="MOVE").to_dict(), indent=2))
    elif args.cmd == "status": print(json.dumps(WorldModel(manager).snapshot(), indent=2))
    elif args.cmd == "verify":
        results = {"transitions": manager.transitions.verify(), "operations": manager.operations.verify(), "capability_events": manager.capability_events.verify()}
        print(json.dumps(results, indent=2)); return 0 if all(ok for ok, _ in results.values()) else 2
    elif args.cmd == "reconcile": print(json.dumps(manager.reconcile(args.agent), indent=2))
    elif args.cmd == "terminate": print(json.dumps(manager.terminate(args.agent).to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
