"""Dataclasses shared across resolver components."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .rversion import VersionConstraint


@dataclass
class Dependency:
    name: str
    constraints: List[VersionConstraint] = field(default_factory=list)
    kind: str = "Depends"
    optional: bool = False
    source_hint: Optional[str] = None


@dataclass
class PackageVersion:
    name: str
    version: str
    repo: str
    r_min: Optional[str]
    dependencies: List[Dependency] = field(default_factory=list)
    bioc_release: Optional[str] = None
    source_url: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    published: Optional[str] = None


@dataclass
class PackageSelection:
    package: str
    version: str
    repo: str
    source_url: Optional[str]
    dependencies: List[Dependency]
    r_min: Optional[str]
    bioc_release: Optional[str] = None


@dataclass
class ResolutionPlan:
    r_version: str
    selections: Dict[str, PackageSelection]
    notes: List[str] = field(default_factory=list)


@dataclass
class Conflict:
    package: str
    required_by: List[str]
    message: str
    candidates_considered: List[str] = field(default_factory=list)


@dataclass
class ResolutionReport:
    minimal_plan: Optional[ResolutionPlan]
    locked_plan: Optional[ResolutionPlan]
    conflicts: List[Conflict] = field(default_factory=list)
    locked_conflicts: List[Conflict] = field(default_factory=list)
    r_version_locked: Optional[str] = None
