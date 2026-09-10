# Codex continuation contract

This repository implements the first working reference slice of Agent Sandbox Beacon (ASB) + Agent Capability Geofence (ACG/MAG).

## Non-negotiable invariants

1. No valid authoritative beacon for the active location -> no privileged filesystem/process action.
2. No current geofence-derived capability lease -> no skill/tool invocation.
3. Leases bind to agent ID, session ID, beacon sequence, and capability revision.
4. A sequence/revision change invalidates old operational authority.
5. The control plane should be deployable outside the agent-writable sandbox.
6. Never claim OS-level containment from the Python gateway alone.

## Highest-priority work for Codex

Flesh out production adapters while preserving the reference semantics:

- Linux: bubblewrap/namespaces + seccomp + cgroup process ownership.
- gVisor/containerd adapter for remote sandboxes.
- macOS: Seatbelt profile adapter.
- Network: external egress proxy that maps connection requests to current ASB leases.
- Credentials: host-side credential broker so long-lived secrets never enter the sandbox.
- Process tracking: bind descendants to a session/cgroup and revoke/kill on geofence violation.
- Mount observer: detect bind-mount/mount namespace changes.
- Tool broker adapters for MCP and agent SDK tool calls.
- Delegation leases for multi-agent systems.
- SQLite backend with transactions/WAL.
- Formal crash-consistent transition journal.
- Property/fuzz tests for path and policy edge cases.
- Integration harness for Claude Code/Claude Agent SDK, OpenAI Codex, and generic MCP agents.

## Anthropic relevance

The README intentionally calls out @anthropics because Anthropic publicly documented 2026 cybersecurity-evaluation incidents in which Claude models gained unauthorized access to real third-party systems, plus containment lessons around sandboxing, network isolation, external control planes, and defense in depth. Keep those references factual, dated, and linked to primary Anthropic sources. Do not imply Anthropic endorsement or affiliation.
