# Verification evidence

Reference implementation verification performed on 2026-09-10.

```text
PYTHONPATH=src python3 -m pytest -q
.............                                                            [100%]
13 passed
```

Demo evidence:

- write capability available inside the engineering geofence
- beacon moved to the accessed file's directory
- movement to an external zone revoked `filesystem.write`
- transition hash chain verified
- capability-event hash chain verified

The reference Python gateway is not an OS/hypervisor sandbox. See `SECURITY.md` and `docs/THREAT_MODEL.md`.
