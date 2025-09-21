"""Dependency resolution engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .constants import BIOCONDUCTOR_R_MATRIX, SUPPORTED_R_VERSIONS
from .exceptions import MetadataFetchError, ResolutionError
from .metadata import MetadataProvider
from .models import Conflict, Dependency, PackageSelection, PackageVersion, ResolutionPlan, ResolutionReport
from .rversion import RVersion, VersionConstraint, satisfies_all, parse_constraint_expression, compare_versions


@dataclass
class TargetContext:
    identifier: str
    package: str
    source: str
    constraints: List[VersionConstraint] = field(default_factory=list)
    bioc_release: Optional[str] = None
    github_ref: Optional[str] = None
    github_token: Optional[str] = None
    github_slug: Optional[str] = None


@dataclass
class PackageRequest:
    package: str
    source: Optional[str]
    constraints: List[VersionConstraint]
    required_by: List[str]
    bioc_release: Optional[str]
    github_ref: Optional[str]
    github_token: Optional[str]
    github_slug: Optional[str] = None


@dataclass
class ResolutionState:
    candidate_r: str
    include_optional: bool
    prefer_bioc_release: Optional[str]
    assignments: Dict[str, PackageSelection] = field(default_factory=dict)
    constraints: Dict[str, List[VersionConstraint]] = field(default_factory=dict)
    visiting: Set[str] = field(default_factory=set)
    failure_traces: List[Conflict] = field(default_factory=list)


class EnvironmentSolver:
    def __init__(self, metadata: MetadataProvider, include_optional: bool = False, prefer_bioc_release: Optional[str] = None):
        self.metadata = metadata
        self.include_optional = include_optional
        self.prefer_bioc_release = prefer_bioc_release

    # ------------------------------------------------------------------

    def solve(self, targets: Sequence[TargetContext], candidate_r: str) -> ResolutionPlan:
        state = ResolutionState(
            candidate_r=candidate_r,
            include_optional=self.include_optional,
            prefer_bioc_release=self.prefer_bioc_release,
        )
        for target in targets:
            request = PackageRequest(
                package=target.package,
                source=target.source,
                constraints=target.constraints,
                required_by=[target.identifier],
                bioc_release=target.bioc_release,
                github_ref=target.github_ref,
                github_token=target.github_token,
            )
            self._resolve_package(request, state)
        return ResolutionPlan(r_version=candidate_r, selections=dict(state.assignments))

    # ------------------------------------------------------------------

    def _resolve_package(self, request: PackageRequest, state: ResolutionState) -> PackageSelection:
        package = request.package
        if package in state.visiting:
            # Dependency cycle detected; assume already being handled higher up.
            if package in state.assignments:
                return state.assignments[package]
            raise ResolutionError(package=package, required_by=request.required_by, message="Dependency cycle detected")

        existing_selection = state.assignments.get(package)
        aggregated_constraints = list(state.constraints.get(package, [])) + request.constraints
        if existing_selection:
            if not satisfies_all(existing_selection.version, aggregated_constraints):
                raise ResolutionError(
                    package=package,
                    required_by=request.required_by,
                    message=(
                        f"Selected version {existing_selection.version} does not satisfy new constraints "
                        f"{[c.operator + c.version for c in request.constraints]}"
                    ),
                    candidates=[existing_selection.version],
                )
            # Ensure R requirement satisfied under current candidate R
            if existing_selection.r_min and compare_versions(state.candidate_r, existing_selection.r_min) < 0:
                raise ResolutionError(
                    package=package,
                    required_by=request.required_by,
                    message=(
                        f"Selected version {existing_selection.version} requires R>={existing_selection.r_min}"
                    ),
                    candidates=[existing_selection.version],
                )
            state.constraints[package] = aggregated_constraints
            return existing_selection

        candidates = self._candidate_versions(request, state, aggregated_constraints)
        if not candidates:
            raise ResolutionError(
                package=package,
                required_by=request.required_by,
                message="No candidate versions satisfy constraints",
                candidates=["(none)"]
            )

        state.visiting.add(package)
        previous_constraints = list(state.constraints.get(package, []))
        failures: List[ResolutionError] = []
        for candidate in candidates:
            selection = PackageSelection(
                package=candidate.name,
                version=candidate.version,
                repo=candidate.repo,
                source_url=candidate.source_url,
                dependencies=candidate.dependencies,
                r_min=candidate.r_min,
                bioc_release=candidate.bioc_release,
            )
            state.assignments[package] = selection
            state.constraints[package] = aggregated_constraints
            try:
                self._resolve_dependencies(selection, request, state)
                state.visiting.remove(package)
                return selection
            except ResolutionError as error:
                failures.append(error)
                del state.assignments[package]
                continue
        # Exhausted candidates
        state.visiting.remove(package)
        if previous_constraints:
            state.constraints[package] = previous_constraints
        else:
            state.constraints.pop(package, None)
        merged_candidates = [f"{cand.repo} {cand.version}" for cand in candidates]
        message = ", ".join(sorted({failure.message for failure in failures})) or "Unresolvable dependency chain"
        raise ResolutionError(
            package=package,
            required_by=request.required_by,
            message=message,
            candidates=merged_candidates,
        )

    # ------------------------------------------------------------------

    def _resolve_dependencies(self, selection: PackageSelection, request: PackageRequest, state: ResolutionState) -> None:
        dependencies = selection.dependencies
        if not dependencies:
            return
        for dependency in dependencies:
            if dependency.optional and not state.include_optional:
                continue
            child_constraints = dependency.constraints
            child_request = PackageRequest(
                package=dependency.name,
                source=self._infer_source(selection, dependency),
                constraints=child_constraints,
                required_by=request.required_by + [selection.package],
                bioc_release=self._infer_bioc_release(selection, dependency, request.bioc_release),
                github_ref=None,
                github_token=None,
            )
            self._resolve_package(child_request, state)

    # ------------------------------------------------------------------

    def _infer_source(self, parent: PackageSelection, dependency: Dependency) -> Optional[str]:
        if parent.repo.lower() == "bioconductor":
            return "bioc"
        if parent.repo.lower() == "github":
            return None
        return None

    def _infer_bioc_release(
        self,
        parent: PackageSelection,
        dependency: Dependency,
        parent_release: Optional[str],
    ) -> Optional[str]:
        if parent.repo.lower() == "bioconductor":
            return parent.bioc_release or parent_release or self.prefer_bioc_release
        return None

    # ------------------------------------------------------------------

    def _candidate_versions(
        self,
        request: PackageRequest,
        state: ResolutionState,
        constraints: List[VersionConstraint],
    ) -> List[PackageVersion]:
        source_order: List[str] = []
        if request.source:
            source_order.append(request.source)
        for fallback in ("cran", "bioc"):
            if fallback not in source_order:
                source_order.append(fallback)

        seen: Set[Tuple[str, str]] = set()
        results: List[PackageVersion] = []
        for source in source_order:
            try:
                versions = self._load_versions_for_source(request, source)
            except MetadataFetchError:
                continue
            for version in versions:
                if version.r_min and compare_versions(state.candidate_r, version.r_min) < 0:
                    continue
                if constraints and not satisfies_all(version.version, constraints):
                    continue
                key = (version.repo, version.version)
                if key in seen:
                    continue
                seen.add(key)
                results.append(version)

        def source_priority(version: PackageVersion) -> int:
            repo = version.repo.lower()
            for idx, src in enumerate(source_order):
                if repo.startswith(src[:4]):
                    return idx
            return len(source_order)

        results.sort(key=lambda version: RVersion(version.version), reverse=True)
        results.sort(key=source_priority)
        return results

    def _load_versions_for_source(self, request: PackageRequest, source: str):
        source = source.lower()
        if source == "cran":
            return self.metadata.get_versions(request.package, source="cran")
        if source in {"bioc", "bioconductor"}:
            release = request.bioc_release or self.prefer_bioc_release or self.metadata.latest_bioconductor_release()
            if not release:
                raise MetadataFetchError("No Bioconductor release available")
            return self.metadata.get_versions(request.package, source="bioc", bioc_release=release)
        if source == "github":
            slug = request.github_slug or request.package
            return self.metadata.get_versions(
                slug,
                source="github",
                github_ref=request.github_ref,
                github_token=request.github_token,
            )
        raise MetadataFetchError(f"Unsupported source {source}")

def build_target_contexts(config: ProjectConfig, metadata: MetadataProvider) -> List[TargetContext]:
    contexts: List[TargetContext] = []
    for spec in config.targets:
        source = spec.source.lower()
        identifier = spec.alias or spec.package
        constraint_expr = spec.constraint or ""
        constraints = parse_constraint_expression(constraint_expr) if constraint_expr else []
        bioc_release = spec.bioc_release or config.options.prefer_bioc_release
        github_token = spec.github_token or config.options.github_token
        github_ref = spec.github_ref
        github_slug: Optional[str] = None
        package_name = spec.package

        if source in {"bioc", "bioconductor"}:
            if not bioc_release:
                bioc_release = metadata.latest_bioconductor_release()
        if source == "github":
            if "/" not in package_name:
                raise ValueError("GitHub target must use owner/repo format")
            github_slug = package_name
            owner, repo = github_slug.split("/", 1)
            version = metadata.get_github_version(owner, repo, ref=github_ref, token=github_token)
            package_name = version.name

        contexts.append(
            TargetContext(
                identifier=identifier,
                package=package_name,
                source=source,
                constraints=constraints,
                bioc_release=bioc_release,
                github_ref=github_ref,
                github_token=github_token,
                github_slug=github_slug,
            )
        )
    return contexts
def _bioc_release_requirements(targets: Sequence[TargetContext], metadata: MetadataProvider, default_release: Optional[str]) -> Dict[str, str]:
    requirements: Dict[str, str] = {}
    for target in targets:
        if target.source not in {"bioc", "bioconductor"}:
            continue
        release = target.bioc_release or default_release or metadata.latest_bioconductor_release()
        if not release:
            continue
        required_r = metadata.bioconductor_r_version(release)
        if required_r:
            requirements[release] = required_r
            target.bioc_release = release
    return requirements


def compute_resolution(metadata: MetadataProvider, targets: Sequence[TargetContext], include_optional: bool, prefer_bioc_release: Optional[str], locked_r: Optional[str] = None) -> Tuple[Optional[ResolutionPlan], List[Conflict]]:
    cloned_targets = [
        TargetContext(
            identifier=target.identifier,
            package=target.package,
            source=target.source,
            constraints=list(target.constraints),
            bioc_release=target.bioc_release,
            github_ref=target.github_ref,
            github_token=target.github_token,
            github_slug=target.github_slug,
        )
        for target in targets
    ]
    solver = EnvironmentSolver(metadata, include_optional=include_optional, prefer_bioc_release=prefer_bioc_release)
    default_release = prefer_bioc_release or metadata.latest_bioconductor_release()
    release_requirements = _bioc_release_requirements(cloned_targets, metadata, default_release)

    conflicts: List[Conflict] = []

    if locked_r:
        try:
            plan = solver.solve(cloned_targets, locked_r)
            return plan, conflicts
        except ResolutionError as error:
            conflicts.append(
                Conflict(
                    package=error.package,
                    required_by=error.required_by,
                    message=error.message,
                    candidates=error.candidates or [],
                )
            )
            return None, conflicts

    candidate_versions = sorted({RVersion(ver) for ver in SUPPORTED_R_VERSIONS}, key=lambda v: v, reverse=False)
    for release, required_r in release_requirements.items():
        candidate_versions.append(RVersion(required_r))
    candidate_versions = sorted(set(candidate_versions))

    for candidate in candidate_versions:
        candidate_str = str(candidate)
        # Bioconductor compatibility check
        incompatible = False
        for release, required_r in release_requirements.items():
            if compare_versions(candidate_str, required_r) < 0:
                incompatible = True
                break
        if incompatible:
            continue
        try:
            plan = solver.solve(cloned_targets, candidate_str)
            return plan, conflicts
        except ResolutionError as error:
            conflicts.append(
                Conflict(
                    package=error.package,
                    required_by=error.required_by,
                    message=error.message,
                    candidates=error.candidates or [],
                )
            )
            continue
    return None, conflicts


def build_report(
    metadata: MetadataProvider,
    targets: Sequence[TargetContext],
    include_optional: bool,
    prefer_bioc_release: Optional[str],
    locked_r: Optional[str],
) -> ResolutionReport:
    minimal_plan, minimal_conflicts = compute_resolution(
        metadata,
        targets,
        include_optional=include_optional,
        prefer_bioc_release=prefer_bioc_release,
        locked_r=None,
    )

    locked_plan = None
    locked_conflicts: List[Conflict] = []
    if locked_r:
        locked_plan, locked_conflicts = compute_resolution(
            metadata,
            targets,
            include_optional=include_optional,
            prefer_bioc_release=prefer_bioc_release,
            locked_r=locked_r,
        )
    return ResolutionReport(
        minimal_plan=minimal_plan,
        locked_plan=locked_plan,
        conflicts=minimal_conflicts,
        locked_conflicts=locked_conflicts,
        r_version_locked=locked_r,
    )



























