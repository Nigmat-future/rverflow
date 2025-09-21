"""Functions that download metadata from public package repositories."""
from __future__ import annotations

from typing import Dict, Optional

import requests

from .exceptions import MetadataFetchError

DEFAULT_TIMEOUT = 30
USER_AGENT = "rpkg-resolver/0.1"


def _request_json(url: str, session: Optional[requests.Session] = None) -> Dict:
    sess = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    response = sess.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    if response.status_code >= 400:
        raise MetadataFetchError(f"Failed to fetch {url}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover - network only
        raise MetadataFetchError(f"Invalid JSON from {url}") from exc


def fetch_cran_package(package: str, session: Optional[requests.Session] = None) -> Dict:
    url = f"https://crandb.r-pkg.org/{package}/all"
    return _request_json(url, session=session)


_BIOC_CATEGORIES = ["bioc", "data/annotation", "data/experiment", "workflows"]


def fetch_bioconductor_release(release: str, session: Optional[requests.Session] = None) -> Dict[str, Dict]:
    aggregated: Dict[str, Dict] = {}
    sess = session or requests.Session()
    for category in _BIOC_CATEGORIES:
        url = f"https://bioconductor.org/packages/json/{release}/{category}/packages.json"
        try:
            data = _request_json(url, session=sess)
        except MetadataFetchError:
            # Older releases might not have all categories; skip silently.
            continue
        for name, payload in data.items():
            payload = dict(payload)
            payload[".category"] = category
            aggregated[name] = payload
    if not aggregated:
        raise MetadataFetchError(f"No packages found for Bioconductor release {release}")
    return aggregated


def fetch_github_description(owner: str, repo: str, ref: Optional[str] = None, token: Optional[str] = None, session: Optional[requests.Session] = None) -> Dict:
    sess = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if ref is None:
        repo_resp = sess.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=DEFAULT_TIMEOUT)
        if repo_resp.status_code >= 400:
            raise MetadataFetchError(f"Failed to resolve default branch for {owner}/{repo}")
        ref = repo_resp.json().get("default_branch")
        if not ref:
            raise MetadataFetchError(f"Repository {owner}/{repo} has no default branch metadata")

    commit_resp = sess.get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}", headers=headers, timeout=DEFAULT_TIMEOUT
    )
    if commit_resp.status_code >= 400:
        raise MetadataFetchError(f"Failed to resolve commit for {owner}/{repo}@{ref}")
    commit_data = commit_resp.json()
    sha = commit_data.get("sha")
    if not sha:
        raise MetadataFetchError(f"Commit information missing for {owner}/{repo}@{ref}")

    raw_headers = dict(headers)
    raw_headers.setdefault("Accept", "application/vnd.github.v3.raw")
    desc_resp = sess.get(
        f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/DESCRIPTION",
        headers=raw_headers,
        timeout=DEFAULT_TIMEOUT,
    )
    if desc_resp.status_code >= 400:
        raise MetadataFetchError(f"DESCRIPTION not found for {owner}/{repo}@{sha}")

    return {
        "owner": owner,
        "repo": repo,
        "commit": sha,
        "ref": ref,
        "description": desc_resp.text,
        "commit_timestamp": commit_data.get("commit", {}).get("committer", {}).get("date"),
        "url": commit_data.get("html_url"),
    }
