"""Custom exceptions raised by the resolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class MetadataFetchError(RuntimeError):
    """Raised when metadata for a package cannot be retrieved."""


@dataclass
class ResolutionError(Exception):
    package: str
    required_by: List[str]
    message: str
    candidates: Optional[List[str]] = None

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.package}: {self.message}"
