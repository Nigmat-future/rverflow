"""Helpers for dealing with R-style version strings."""
from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering
from itertools import zip_longest
from typing import Iterable, List, Optional, Sequence, Tuple

import re

_COMPONENT_RE = re.compile(r"[0-9A-Za-z]+")


def _tokenize(version: str) -> Tuple[str, ...]:
    version = version.strip()
    if not version:
        return ("0",)
    parts = []
    for chunk in re.split(r"[._-]", version):
        if not chunk:
            continue
        parts.append(chunk)
    return tuple(parts) if parts else ("0",)


@total_ordering
@dataclass(frozen=True)
class RVersion:
    """Comparable representation of an R (or R package) version string."""

    raw: str
    components: Tuple[Tuple[int, str], ...]

    def __init__(self, raw: str):
        object.__setattr__(self, "raw", raw)
        comps: List[Tuple[int, str]] = []
        for token in _tokenize(raw):
            if token.isdigit():
                comps.append((int(token), ""))
            else:
                match = re.match(r"(\d+)([A-Za-z].*)", token)
                if match:
                    comps.append((int(match.group(1)), match.group(2)))
                else:
                    comps.append((0, token))
        object.__setattr__(self, "components", tuple(comps))

    def __lt__(self, other: "RVersion") -> bool:  # type: ignore[override]
        return self._compare(other) < 0

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, RVersion):
            return NotImplemented
        return self.components == other.components

    def _compare(self, other: "RVersion") -> int:
        for (left_num, left_suffix), (right_num, right_suffix) in zip_longest(
            self.components, other.components, fillvalue=(0, "")
        ):
            if left_num != right_num:
                return -1 if left_num < right_num else 1
            if left_suffix != right_suffix:
                return -1 if left_suffix < right_suffix else 1
        return 0

    def __str__(self) -> str:  # type: ignore[override]
        return self.raw

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(self.components)


def compare_versions(a: str, b: str) -> int:
    """Return -1, 0, or 1 comparing two version strings."""

    left = RVersion(a)
    right = RVersion(b)
    return left._compare(right)


@dataclass(frozen=True)
class VersionConstraint:
    """Represents a simple comparator-based version constraint."""

    operator: str
    version: str

    def is_satisfied_by(self, candidate: str) -> bool:
        cmp = compare_versions(candidate, self.version)
        if self.operator == ">":
            return cmp > 0
        if self.operator == ">=":
            return cmp >= 0
        if self.operator == "<":
            return cmp < 0
        if self.operator == "<=":
            return cmp <= 0
        if self.operator in {"==", "="}:
            return cmp == 0
        if self.operator == "!=":
            return cmp != 0
        raise ValueError(f"Unsupported operator: {self.operator}")


_CONSTRAINT_TOKEN_RE = re.compile(r"(>=|<=|==|=|!=|>|<)\s*([0-9A-Za-z_.-]+)")


def parse_constraint_expression(expr: str) -> List[VersionConstraint]:
    """Parse a comma-separated constraint string into VersionConstraint objects."""

    constraints: List[VersionConstraint] = []
    for fragment in expr.split(","):
        fragment = fragment.strip()
        if not fragment:
            continue
        match = _CONSTRAINT_TOKEN_RE.search(fragment)
        if not match:
            continue
        op, version = match.group(1), match.group(2)
        constraints.append(VersionConstraint(op, version))
    return constraints


def satisfies_all(candidate: str, constraints: Sequence[VersionConstraint]) -> bool:
    return all(constraint.is_satisfied_by(candidate) for constraint in constraints)


def pick_highest_satisfying(candidates: Iterable[str], constraints: Sequence[VersionConstraint]) -> Optional[str]:
    """Return the highest version from *candidates* that satisfies *constraints*."""

    filtered = [version for version in candidates if satisfies_all(version, constraints)]
    if not filtered:
        return None
    filtered.sort(key=RVersion, reverse=True)
    return filtered[0]

