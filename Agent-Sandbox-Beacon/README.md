# Agent Sandbox Beacon (ASB) + Multidimensional Agent Geofence (MAG)

> **Attention @anthropics / Claude Code, Claude Agent SDK, Frontier Red Team, and containment engineers:** this project is an independent open-source proposal and working reference implementation for making an agent's *current security position* continuously observable and binding its skills/tools to short-lived, revocable leases. It is **not affiliated with or endorsed by Anthropic**.

ASB treats an agent's filesystem location as trusted environment state. MAG extends that location into a capability geofence: when the authoritative beacon leaves an allowed zone, the agent's runtime skills are revoked at the trusted gateway instead of relying on the model to notice that it crossed a boundary.

The central idea is deliberately simple:

```text
NO VALID LOCATION BEACON
        =
NO PRIVILEGED ACTION

OUTSIDE A CAPABILITY GEOFENCE
        =
NO VALID SKILL LEASE
```

## Why this exists now

Anthropic's July 30, 2026 disclosure described three cybersecurity-evaluation incidents where Claude reached the internet from or through evaluation environments and then gained unauthorized access to real third-party systems. On September 9, 2026 Anthropic published an expanded alignment assessment covering four incidents. Anthropic's containment engineering guidance also emphasizes environmental containment, OS-level sandboxing, egress controls, credentials kept outside sandboxes, and trusted control planes outside the agent environment.

Primary sources:

- Anthropic, **Investigating three real-world incidents in our cybersecurity evaluations** (2026-07-30): https://www.anthropic.com/research/investigating-incidents-cybersecurity-evals
- Anthropic, **An alignment assessment of recent cybersecurity incidents** (2026-09-09): https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents
- Anthropic, **How we contain Claude across products**: https://www.anthropic.com/engineering/how-we-contain-claude
- Anthropic, **Improving our alignment and security practices**: https://www.anthropic.com/news/improving-alignment-security-efforts
- Anthropic, **Beyond permission prompts: making Claude Code more secure and autonomous**: https://www.anthropic.com/engineering/claude-code-sandboxing

This project is intended as a concrete contribution to that defense-in-depth discussion, not a claim that one mechanism solves agent containment.

## What is new here

Traditional sandboxes answer **what resources can this process access?**

ASB adds **where is this agent operating right now, according to a trusted observer?**

MAG adds **which capabilities are valid at that exact security position?**

A parent or external sentinel can observe the agent from a higher trust domain. The important hierarchy is not merely a higher filesystem directory; it is **higher authority**:

```text
HOST / HYPERVISOR / TRUSTED CONTROL PLANE
│
├── External Sentinel
├── Authoritative Beacon Registry
├── Capability Broker
├── Network / Credential Brokers
│
└── AGENT SANDBOX
    └── workspace
        └── agent
```

## Working reference implementation

This repository already contains real code for:

- authoritative per-agent beacons
- local `.agent-active/` projections
- atomic beacon file replacement
- monotonic movement sequences
- session identity
- heartbeat/lease expiry
- nested geofence policy
- deny-wins capability resolution
- capability leases bound to beacon sequence + capability revision
- automatic lease revocation on movement
- filesystem read/write/list/mkdir gateway
- shell execution gateway with fixed authorized CWD
- generic network/tool/credential/data capability broker checks
- path containment and symlink-escape rejection
- hash-chained transition, capability, and operation ledgers
- stale-beacon expiration
- local projection reconciliation
- world-state snapshots and trajectory replay data
- CLI
- CI tests
- Codex continuation instructions in `AGENTS.md`

## Example

```python
from pathlib import Path
from asb import BeaconManager, FilesystemGateway, GeofencePolicyEngine, GeofenceRule, PathResolver

root = Path('/srv/agent-sandbox')
control = Path('/srv/asb-control')  # outside agent-writable sandbox
resolver = PathResolver(root)
policy = GeofencePolicyEngine(resolver, [
    GeofenceRule('engineering', str(root / 'engineering'), allow={'filesystem.read', 'filesystem.write', 'shell.execute'}),
    GeofenceRule('quarantine', str(root / 'quarantine'), allow={'filesystem.read'}, deny={'filesystem.write', 'shell.execute', 'network.connect'}),
])
manager = BeaconManager(root, policy, control_dir=control)
manager.register('agent-07', root / 'engineering')
fs = FilesystemGateway(manager, 'agent-07')
fs.write_text(root / 'engineering' / 'src' / 'result.txt', 'ok\n')
manager.activate('agent-07', root / 'quarantine', reason='move', operation_class='MOVE')
manager.authorize('agent-07', 'filesystem.write')  # raises PolicyDeniedError
```

## Capability lease semantics

A privileged capability is not permanently attached to the agent. A lease binds authority to:

```text
agent_id
session_id
beacon_sequence
capability_revision
active geofence set
expiration
```

Move the beacon and the old lease coordinates become stale.

The intended invariant is:

> An agent possesses no durable privileged runtime capability. Every privileged capability is a revocable lease derived from its current externally observed security position.

## Multidimensional security position

Filesystem location is only one coordinate. An agent can remain in the same directory and still reach an unintended network endpoint or credential.

The production target therefore tracks:

```text
filesystem zone
process / cgroup zone
network / egress zone
credential zone
tool zone
data zone
```

This v0.1 repository implements the filesystem coordinate and generic capability checks. `AGENTS.md` directs Codex to add OS/hypervisor adapters, egress enforcement, credential brokerage, descendant process ownership, and agent-SDK integrations.

## Why the sentinel must be outside the agent trust boundary

A file such as `/workspace/.observer` is not sufficient if the agent can tamper with the same environment.

Preferred deployment:

```text
trusted host
  ASB control directory
  sentinel
  capability broker
  egress proxy
  credential broker
      ↓
agent sandbox
```

The agent can see a projection of its beacon, but it does not own the authoritative state.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python examples/demo.py
```

## Security honesty

This reference library is **not itself a hardened OS sandbox**. A malicious or compromised process with unrestricted raw system-call access could bypass Python wrappers. Strong deployments must combine ASB/MAG semantics with mature enforcement such as gVisor, Linux namespaces/bubblewrap, seccomp, cgroups, macOS Seatbelt, VMs, and external egress/credential brokers.

The contribution here is the missing coordination primitive: an externally trusted, replayable agent position whose changes automatically invalidate operational authority.

## Proposed Anthropic integration target

For @anthropics, a concrete experiment would be to place ASB above a Claude Code / Claude Agent SDK evaluation sandbox and bind these capabilities to the current beacon/security position:

- bash execution
- writable filesystem mounts
- egress proxy scopes
- temporary Git credentials
- MCP/tool handles
- evaluator-only services
- artifact publication

Then deliberately task an evaluation model with finding escape paths. A filesystem, process, egress, credential, or tool-boundary crossing should invalidate the corresponding lease *before the next privileged action executes* and emit a tamper-evident event for post-run analysis.

The goal is not to trust Claude to recognize an escape. The goal is to make the surrounding infrastructure revoke authority independently.

## Repository status

**v0.1 reference implementation** — working Python core with tests. The next milestone is host-level enforcement adapters and a real Claude Code/Agent SDK integration harness.

See `AGENTS.md`, `SECURITY.md`, `docs/ARCHITECTURE.md`, and `docs/THREAT_MODEL.md`.
