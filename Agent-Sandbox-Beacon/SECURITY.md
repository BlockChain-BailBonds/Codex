# Security policy

ASB is security infrastructure. Please report vulnerabilities privately to the repository owner before public disclosure when practical.

## Security boundaries

The reference Python implementation enforces beacon/geofence policy only for operations routed through its gateways. It is **not** an OS sandbox by itself and must not be represented as one.

For strong containment, place the ASB control plane outside the agent's writable sandbox and combine it with OS/hypervisor controls such as namespaces, seccomp, gVisor, bubblewrap, Seatbelt, VMs, cgroups, and a network egress proxy.

## Especially valuable reports

- gateway bypasses
- stale lease reuse
- sequence rollback/replay
- symlink or mount escapes
- TOCTOU bugs
- projection/authoritative-state divergence
- policy-confusion bugs
- cross-agent delegation bypass
