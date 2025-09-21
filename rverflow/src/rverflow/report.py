"""Formatting helpers for presenting resolution results."""
from __future__ import annotations

import json
from typing import Iterable, List, Tuple

from .models import Conflict, ResolutionPlan, ResolutionReport
from .rversion import compare_versions


def _format_plan(plan: ResolutionPlan) -> List[str]:
    lines = [f"R {plan.r_version}"]
    for name in sorted(plan.selections):
        selection = plan.selections[name]
        repo = selection.repo
        version = selection.version
        extras: List[str] = []
        if selection.bioc_release:
            extras.append(f"Bioconductor {selection.bioc_release}")
        if selection.r_min:
            extras.append(f"needs R>={selection.r_min}")
        if selection.source_url:
            extras.append(selection.source_url)
        meta = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"  - {name} {version} [{repo}]{meta}")
    return lines


def _format_conflicts(conflicts: Iterable[Conflict]) -> List[str]:
    lines: List[str] = []
    for conflict in conflicts:
        chain = " -> ".join(conflict.required_by)
        lines.append(f"  * {conflict.package} (via {chain}): {conflict.message}")
        if conflict.candidates:
            lines.append(f"    candidates: {', '.join(conflict.candidates)}")
    return lines


def _compute_downgrades(minimal: ResolutionPlan, locked: ResolutionPlan) -> List[Tuple[str, str, str]]:
    downgrades: List[Tuple[str, str, str]] = []
    for package, desired in minimal.selections.items():
        if package not in locked.selections:
            continue
        locked_selection = locked.selections[package]
        if compare_versions(locked_selection.version, desired.version) < 0:
            downgrades.append((package, desired.version, locked_selection.version))
    return downgrades


def generate_text(report: ResolutionReport) -> str:
    lines: List[str] = []
    if report.minimal_plan:
        lines.append("Minimal feasible environment:")
        lines.extend(_format_plan(report.minimal_plan))
    else:
        lines.append("Failed to determine a compatible environment.")
        if report.conflicts:
            lines.append("Conflicts encountered while searching versions:")
            lines.extend(_format_conflicts(report.conflicts))

    if report.r_version_locked:
        lines.append("")
        lines.append(f"When locking R to {report.r_version_locked}:")
        if report.locked_plan:
            lines.extend(_format_plan(report.locked_plan))
            if report.minimal_plan:
                downgrades = _compute_downgrades(report.minimal_plan, report.locked_plan)
                if downgrades:
                    lines.append("  Downgrades required relative to minimal plan:")
                    for package, desired, locked in downgrades:
                        lines.append(f"    - {package}: {desired} -> {locked}")
        elif report.locked_conflicts:
            lines.append("  Conflicts:")
            lines.extend(_format_conflicts(report.locked_conflicts))
        else:
            lines.append("  No solution found.")
    return "\n".join(lines)


def generate_json(report: ResolutionReport) -> str:
    payload = {
        "minimal_plan": _plan_to_dict(report.minimal_plan) if report.minimal_plan else None,
        "locked_plan": _plan_to_dict(report.locked_plan) if report.locked_plan else None,
        "conflicts": [conflict.__dict__ for conflict in report.conflicts],
        "locked_conflicts": [conflict.__dict__ for conflict in report.locked_conflicts],
        "r_version_locked": report.r_version_locked,
    }
    return json.dumps(payload, indent=2)


def _plan_to_dict(plan: ResolutionPlan | None):
    if not plan:
        return None
    return {
        "r_version": plan.r_version,
        "selections": {
            name: {
                "version": selection.version,
                "repo": selection.repo,
                "r_min": selection.r_min,
                "bioc_release": selection.bioc_release,
                "source_url": selection.source_url,
            }
            for name, selection in plan.selections.items()
        },
        "notes": plan.notes,
    }
