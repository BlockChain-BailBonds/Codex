from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from .errors import SandboxEscapeError


class SymlinkPolicy(str, Enum):
    DENY_ALL = "DENY_ALL"
    ALLOW_INTERNAL_ONLY = "ALLOW_INTERNAL_ONLY"
    ALLOW_WITH_RESOLUTION = "ALLOW_WITH_RESOLUTION"


class PathResolver:
    def __init__(self, root: str | Path, symlink_policy: SymlinkPolicy = SymlinkPolicy.ALLOW_INTERNAL_ONLY):
        self.root = Path(root).expanduser().resolve()
        self.symlink_policy = symlink_policy

    def _contains_symlink(self, raw: Path) -> bool:
        candidate = raw if raw.is_absolute() else self.root / raw
        current = candidate
        seen: list[Path] = []
        while True:
            seen.append(current)
            if current == self.root or current.parent == current:
                break
            current = current.parent
        return any(p.exists() and p.is_symlink() for p in seen)

    def resolve(self, path: str | Path) -> Path:
        raw = Path(path).expanduser()
        if self.symlink_policy == SymlinkPolicy.DENY_ALL and self._contains_symlink(raw):
            raise SandboxEscapeError(f"symlink denied by policy: {path}")

        candidate = raw if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve(strict=False)

        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SandboxEscapeError(f"path escapes sandbox: {path}") from exc

        if os.path.commonpath([str(self.root), str(resolved)]) != str(self.root):
            raise SandboxEscapeError(f"path escapes sandbox: {path}")

        return resolved
