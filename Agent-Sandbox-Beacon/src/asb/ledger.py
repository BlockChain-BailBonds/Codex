from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any


ZERO_HASH = "0" * 64


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class HashChainLedger:
    """Append-only JSONL ledger with a simple SHA-256 hash chain."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _last_hash(self) -> str:
        records = self.read_all()
        if not records:
            return ZERO_HASH
        return records[-1]["event_hash"]

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = dict(event)
            record["previous_hash"] = self._last_hash()
            material = canonical_json(record)
            record["event_hash"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
            line = canonical_json(record) + "\n"
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            return record

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> tuple[bool, int]:
        previous = ZERO_HASH
        count = 0
        for record in self.read_all():
            count += 1
            event_hash = record.get("event_hash")
            if record.get("previous_hash") != previous:
                return False, count
            unsigned = dict(record)
            unsigned.pop("event_hash", None)
            expected = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
            if event_hash != expected:
                return False, count
            previous = event_hash
        return True, count
