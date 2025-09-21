"""Lightweight on-disk cache for package metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _sanitize(segment: str) -> str:
    return segment.replace("/", "__")


class MetadataCache:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, *segments: str) -> Path:
        safe_segments = [_sanitize(segment) for segment in segments]
        path = self.root.joinpath(*safe_segments)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def load(self, *segments: str) -> Optional[Dict[str, Any]]:
        path = self._path(*segments)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def store(self, data: Dict[str, Any], *segments: str) -> None:
        path = self._path(*segments)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2, sort_keys=True)

    def exists(self, *segments: str) -> bool:
        return self._path(*segments).exists()

    def drop(self, *segments: str) -> None:
        path = self._path(*segments)
        if path.exists():
            path.unlink()
