"""Convert repository metadata into normalized package records."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from .cache import MetadataCache
from .constants import BASE_R_PACKAGES, BIOCONDUCTOR_R_MATRIX
from .exceptions import MetadataFetchError
from .fetchers import fetch_bioconductor_release, fetch_cran_package, fetch_github_description
from .models import Dependency, PackageVersion
from .rversion import RVersion, VersionConstraint, compare_versions, parse_constraint_expression

_DEP_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9._]+)(?:\s*\((?P<constraints>[^)]+)\))?$")


@dataclass
class GithubMetadata:
    owner: str
    repo: str
    commit: str
    description: Dict[str, str]
    ref: Optional[str]
    url: Optional[str]
    timestamp: Optional[str]


def _parse_dependency_entry(entry: str) -> Tuple[str, List[VersionConstraint]]:
    match = _DEP_PATTERN.match(entry.strip())
    if not match:
        return entry.strip(), []
    name = match.group("name")
    constraints_expr = match.group("constraints") or ""
    constraints = parse_constraint_expression(constraints_expr)
    return name, constraints


def _parse_dep_section(section: object) -> List[Tuple[str, List[VersionConstraint]]]:
    items: List[Tuple[str, List[VersionConstraint]]] = []
    if not section:
        return items
    if isinstance(section, dict):
        for name, spec in section.items():
            if not isinstance(spec, str):
                spec = str(spec)
            parsed = parse_constraint_expression(spec)
            items.append((name, parsed))
        return items
    if isinstance(section, str):
        entries = section.split(",")
    elif isinstance(section, Iterable):  # type: ignore[unreachable]
        entries = section
    else:
        return items
    for raw in entries:
        if raw is None:
            continue
        name, constraints = _parse_dependency_entry(str(raw))
        items.append((name, constraints))
    return items


def _split_r_requirement(dependencies: List[Dependency]) -> Tuple[Optional[str], List[Dependency]]:
    remaining: List[Dependency] = []
    r_requirement: Optional[str] = None
    for dep in dependencies:
        if dep.name.lower() == "r":
            candidate = None
            for constraint in dep.constraints:
                if constraint.operator in {">=", ">"}:
                    candidate = constraint.version
            if candidate:
                if not r_requirement or compare_versions(candidate, r_requirement) > 0:
                    r_requirement = candidate
            continue
        remaining.append(dep)
    return r_requirement, remaining


def _build_dependencies(payload: Dict, include_optional: bool = False) -> Tuple[List[Dependency], Optional[str]]:
    dependencies: List[Dependency] = []
    for field, kind, optional in (
        (payload.get("Depends"), "Depends", False),
        (payload.get("Imports"), "Imports", False),
        (payload.get("LinkingTo"), "LinkingTo", False),
        (payload.get("Suggests"), "Suggests", True),
    ):
        if optional and not include_optional:
            continue
        for name, constraints in _parse_dep_section(field):
            dependency = Dependency(name=name, constraints=constraints, kind=kind, optional=optional)
            dependencies.append(dependency)
    r_min, non_r_dependencies = _split_r_requirement(dependencies)
    filtered = [dep for dep in non_r_dependencies if dep.name.lower() not in BASE_R_PACKAGES]
    return filtered, r_min


def _normalize_cran_payload(package: str, payload: Dict, version: str) -> PackageVersion:
    dependencies, r_min = _build_dependencies(payload)
    metadata: Dict[str, str] = {}
    for field in ("MD5sum", "NeedsCompilation", "Repository"):
        if field in payload:
            metadata[field] = str(payload[field])
    published = payload.get("Date/Publication")
    return PackageVersion(
        name=package,
        version=version,
        repo="CRAN",
        r_min=r_min,
        dependencies=dependencies,
        source_url=f"https://cran.r-project.org/package={package}",
        published=published,
        metadata=metadata,
    )


def _normalize_bioc_payload(package: str, payload: Dict, release: str) -> PackageVersion:
    dependencies, r_min = _build_dependencies(payload)
    source_url = payload.get("git_url") or f"https://bioconductor.org/packages/{release}/bioc/html/{package}.html"
    published = payload.get("Date/Publication") or payload.get("git_last_commit_date")
    metadata = {
        "category": payload.get(".category", "bioc"),
        "git_branch": payload.get("git_branch", ""),
    }
    return PackageVersion(
        name=package,
        version=str(payload.get("Version")),
        repo="Bioconductor",
        r_min=r_min,
        dependencies=dependencies,
        bioc_release=release,
        source_url=source_url,
        published=published,
        metadata=metadata,
    )


def _parse_description(raw: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    current_key: Optional[str] = None
    current_value: List[str] = []
    for line in raw.splitlines():
        if not line.strip():
            if current_key:
                result[current_key] = " ".join(part.strip() for part in current_value if part)
            current_key = None
            current_value = []
            continue
        if not line.startswith(" ") and ":" in line:
            if current_key:
                result[current_key] = " ".join(part.strip() for part in current_value if part)
            key, value = line.split(":", 1)
            current_key = key.strip()
            current_value = [value.strip()]
        else:
            current_value.append(line)
    if current_key:
        result[current_key] = " ".join(part.strip() for part in current_value if part)
    return result


def _normalize_github_payload(info: GithubMetadata) -> PackageVersion:
    desc = info.description
    package = desc.get("Package")
    if not package:
        raise MetadataFetchError("GitHub DESCRIPTION missing Package field")
    version = desc.get("Version", "0.0.0")
    dependencies, r_min = _build_dependencies(desc)
    metadata = {
        "commit": info.commit,
        "repo": f"{info.owner}/{info.repo}",
        "ref": info.ref or "",
    }
    return PackageVersion(
        name=package,
        version=version,
        repo="GitHub",
        r_min=r_min,
        dependencies=dependencies,
        source_url=info.url,
        published=info.timestamp,
        metadata=metadata,
    )


class MetadataProvider:
    def __init__(self, cache_root: Path | str = "cache"):
        self.cache = MetadataCache(Path(cache_root))
        self.cache.ensure()
        self.session = requests.Session()
        self._cran: Dict[str, List[PackageVersion]] = {}
        self._bioc: Dict[str, Dict[str, PackageVersion]] = {}
        self._github: Dict[Tuple[str, str, str], PackageVersion] = {}

    def close(self) -> None:
        self.session.close()

    # CRAN -----------------------------------------------------------------

    def get_cran_versions(self, package: str) -> List[PackageVersion]:
        if package in self._cran:
            return self._cran[package]
        cache_key = f"{package}.json"
        raw = self.cache.load("cran", cache_key)
        if not raw:
            raw = fetch_cran_package(package, session=self.session)
            self.cache.store(raw, "cran", cache_key)
        versions: List[PackageVersion] = []
        for version, payload in raw.get("versions", {}).items():
            try:
                normalized = _normalize_cran_payload(package, payload, version)
            except Exception as exc:  # pragma: no cover - defensive
                raise MetadataFetchError(f"Failed to normalize CRAN metadata for {package} {version}") from exc
            versions.append(normalized)
        versions.sort(key=lambda item: RVersion(item.version), reverse=True)
        self._cran[package] = versions
        return versions

    # Bioconductor ---------------------------------------------------------

    def _load_bioc_release(self, release: str) -> Dict[str, PackageVersion]:
        if release in self._bioc:
            return self._bioc[release]
        cache_key = f"{release}.json"
        raw = self.cache.load("bioconductor", cache_key)
        if not raw:
            raw = fetch_bioconductor_release(release, session=self.session)
            self.cache.store(raw, "bioconductor", cache_key)
        normalized: Dict[str, PackageVersion] = {}
        for name, payload in raw.items():
            try:
                normalized[name] = _normalize_bioc_payload(name, payload, release)
            except Exception as exc:  # pragma: no cover - defensive
                raise MetadataFetchError(f"Failed to normalize Bioconductor metadata for {name}@{release}") from exc
        self._bioc[release] = normalized
        return normalized

    def get_bioconductor_versions(self, package: str, release: str) -> List[PackageVersion]:
        release_data = self._load_bioc_release(release)
        if package not in release_data:
            raise MetadataFetchError(f"{package} not found in Bioconductor release {release}")
        return [release_data[package]]

    # GitHub ---------------------------------------------------------------

    def get_github_version(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
        token: Optional[str] = None,
    ) -> PackageVersion:
        descriptor = fetch_github_description(owner, repo, ref=ref, token=token, session=self.session)
        description = _parse_description(descriptor["description"])
        info = GithubMetadata(
            owner=owner,
            repo=repo,
            commit=descriptor["commit"],
            description=description,
            ref=descriptor.get("ref"),
            url=descriptor.get("url"),
            timestamp=descriptor.get("commit_timestamp"),
        )
        package_version = _normalize_github_payload(info)
        self._github[(owner, repo, info.commit)] = package_version
        cache_key = f"{owner}__{repo}__{info.commit}.json"
        payload = {
            "owner": owner,
            "repo": repo,
            "commit": info.commit,
            "ref": info.ref,
            "timestamp": info.timestamp,
            "url": info.url,
            "description": description,
        }
        self.cache.store(payload, "github", cache_key)
        return package_version

    # Generic --------------------------------------------------------------


    def prime_bioconductor_release(self, release: str) -> None:
        self._load_bioc_release(release)
    def get_versions(
        self,
        package: str,
        source: str = "cran",
        bioc_release: Optional[str] = None,
        github_ref: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> List[PackageVersion]:
        source = source.lower()
        if source == "cran":
            return self.get_cran_versions(package)
        if source == "bioc" or source == "bioconductor":
            if not bioc_release:
                raise MetadataFetchError("Bioconductor release must be specified for Bioconductor packages")
            return self.get_bioconductor_versions(package, bioc_release)
        if source == "github":
            if "/" not in package:
                raise MetadataFetchError("GitHub packages must be provided as owner/repo")
            owner, repo = package.split("/", 1)
            version = self.get_github_version(owner, repo, ref=github_ref, token=github_token)
            return [version]
        raise MetadataFetchError(f"Unsupported source: {source}")

    def bioconductor_r_version(self, release: str) -> Optional[str]:
        return BIOCONDUCTOR_R_MATRIX.get(release)

    def latest_bioconductor_release(self) -> Optional[str]:
        if not BIOCONDUCTOR_R_MATRIX:
            return None
        return sorted(BIOCONDUCTOR_R_MATRIX.keys())[-1]




