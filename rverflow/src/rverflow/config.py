"""Parse user configuration for the resolver."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class ResolverOptions:
    current_r: Optional[str] = None
    prefer_bioc_release: Optional[str] = None
    include_optional: bool = False
    github_token: Optional[str] = None


@dataclass
class TargetSpec:
    package: str
    source: str = "cran"
    constraint: Optional[str] = None
    alias: Optional[str] = None
    bioc_release: Optional[str] = None
    github_ref: Optional[str] = None
    github_token: Optional[str] = None


@dataclass
class ProjectConfig:
    name: str
    targets: List[TargetSpec]
    options: ResolverOptions


def _normalize_target(entry: dict, global_options: ResolverOptions) -> TargetSpec:
    package = entry.get("package") or entry.get("name")
    if not package:
        raise ValueError("Target entry missing 'package'")
    source = (entry.get("source") or "cran").lower()
    constraint = entry.get("constraint") or entry.get("version")
    alias = entry.get("alias") or entry.get("id")
    bioc_release = entry.get("bioc_release")
    github_ref = entry.get("ref") or entry.get("github_ref")
    github_token = entry.get("github_token") or global_options.github_token
    return TargetSpec(
        package=package,
        source=source,
        constraint=constraint,
        alias=alias,
        bioc_release=bioc_release,
        github_ref=github_ref,
        github_token=github_token,
    )


def load_config(path: Path) -> ProjectConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping")

    project_name = data.get("project", {}).get("name") if isinstance(data.get("project"), dict) else data.get("project")
    if not project_name:
        project_name = path.stem

    options_raw = data.get("options") or {}
    options = ResolverOptions(
        current_r=options_raw.get("current_r"),
        prefer_bioc_release=options_raw.get("prefer_bioc_release"),
        include_optional=bool(options_raw.get("include_optional")),
        github_token=options_raw.get("github_token"),
    )

    targets_data = data.get("targets")
    if not isinstance(targets_data, list) or not targets_data:
        raise ValueError("Configuration must include a non-empty 'targets' list")

    targets = [_normalize_target(entry, options) for entry in targets_data]
    return ProjectConfig(name=project_name, targets=targets, options=options)
