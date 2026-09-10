# Threat model

## Threats in scope

- buggy or goal-directed agents crossing directory boundaries
- stale capability reuse after movement
- untrusted tool requests
- path traversal and symlink escape attempts
- agent crashes leaving stale local beacons
- replay/rollback of sequence-bound authority
- policy bypass by invoking tools after location changes

## Threats requiring external enforcement

The Python reference cannot prevent an arbitrary process that already has unrestricted host access from calling raw syscalls, opening sockets, changing mount namespaces, or reading host credentials. Production deployment must enforce those boundaries outside the agent process.

## Fail-closed target

If agent identity, session, beacon, location, policy, lease, or target cannot be validated, deny the operation.
