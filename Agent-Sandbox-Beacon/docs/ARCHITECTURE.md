# Architecture

## Trust boundary

```mermaid
flowchart TD
    A[Agent reasoning - untrusted] --> G[ASB tool/filesystem/process gateway]
    G --> R[Path resolver]
    R --> P[Geofence policy engine]
    P --> B[Authoritative beacon manager]
    B --> C[Capability lease broker]
    C --> O[OS / hypervisor enforcement adapter]
    O --> E[Environment]
    B --> L[Hash-chained ledgers]
    B --> W[World model]
    S[External sentinel] --> B
```

The strongest deployment places B, C, L, S, and preferably O outside the agent-writable environment.

## Security position

The reference release implements the filesystem coordinate and generic capability broker. The intended production security position is multidimensional:

- filesystem zone
- process/cgroup zone
- network/egress zone
- credential zone
- tool zone
- data zone

Every privileged capability is a revocable lease derived from the current authoritative security position.
