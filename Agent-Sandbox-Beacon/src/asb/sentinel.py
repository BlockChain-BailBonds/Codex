from __future__ import annotations

import threading
from collections.abc import Callable

from .manager import BeaconManager


class ExternalSentinel:
    """Host-side watcher for expired beacons and projection reconciliation."""

    def __init__(self, manager: BeaconManager, interval_seconds: float = 1.0, on_expire: Callable[[str], None] | None = None):
        self.manager = manager
        self.interval_seconds = interval_seconds
        self.on_expire = on_expire
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> list[str]:
        expired = self.manager.expire_stale()
        for agent_id in expired:
            if self.on_expire:
                self.on_expire(agent_id)
        for beacon in self.manager.list_beacons():
            if beacon.agent_id not in expired:
                self.manager.reconcile(beacon.agent_id)
        return expired

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="asb-sentinel")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.tick()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(1.0, self.interval_seconds * 2))
