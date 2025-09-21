"""CLI entry point for the R package resolver."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .config import load_config
from .metadata import MetadataProvider
from .report import generate_json, generate_text
from .solver import build_report, build_target_contexts
from .exceptions import MetadataFetchError, ResolutionError


def _add_common_cache_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache-root",
        default="cache",
        help="Directory where metadata cache files are stored (default: %(default)s)",
    )


def cmd_update_cache(args: argparse.Namespace) -> int:
    cache_root = Path(args.cache_root)
    metadata = MetadataProvider(cache_root)
    try:
        processed: List[str] = []
        for package in args.package or []:
            metadata.get_cran_versions(package)
            processed.append(f"CRAN:{package}")
        for release in args.bioc_release or []:
            metadata.prime_bioconductor_release(release)
            processed.append(f"Bioconductor release {release}")
        if args.config:
            config_path = Path(args.config)
            config = load_config(config_path)
            contexts = build_target_contexts(config, metadata)
            for context in contexts:
                if context.source == "cran":
                    metadata.get_cran_versions(context.package)
                elif context.source in {"bioc", "bioconductor"}:
                    release = context.bioc_release or metadata.latest_bioconductor_release()
                    if release:
                        try:
                            metadata.get_bioconductor_versions(context.package, release)
                        except MetadataFetchError:
                            pass
                elif context.source == "github":
                    slug = context.github_slug or context.package
                    try:
                        metadata.get_versions(slug, source="github", github_ref=context.github_ref, github_token=context.github_token)
                    except MetadataFetchError:
                        pass
            processed.append(f"config:{config_path.name}")
        if processed:
            print("Primed cache entries:")
            for item in processed:
                print(f"  - {item}")
        else:
            print("No cache entries updated.")
        return 0
    finally:
        metadata.close()


def cmd_solve(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    cache_root = Path(args.cache_root)
    metadata = MetadataProvider(cache_root)
    try:
        config = load_config(config_path)
        contexts = build_target_contexts(config, metadata)
        prefer_bioc = args.prefer_bioc or config.options.prefer_bioc_release
        include_optional = args.include_optional or config.options.include_optional
        locked_r = args.lock_r or config.options.current_r

        report = build_report(
            metadata,
            contexts,
            include_optional=include_optional,
            prefer_bioc_release=prefer_bioc,
            locked_r=locked_r,
        )
        if args.format == "json":
            output = generate_json(report)
        else:
            output = generate_text(report)
        print(output)
        return 0
    except (MetadataFetchError, ResolutionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        metadata.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve R package dependency stacks across repositories")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser("update-cache", help="Prime the metadata cache for selected sources")
    _add_common_cache_argument(update)
    update.add_argument("--package", action="append", help="CRAN package to fetch metadata for", default=[])
    update.add_argument("--bioc-release", dest="bioc_release", action="append", help="Bioconductor release to cache", default=[])
    update.add_argument("--config", help="Project configuration file to scan for dependencies")
    update.set_defaults(func=cmd_update_cache)

    solve = subparsers.add_parser("solve", help="Resolve package versions for a project config")
    _add_common_cache_argument(solve)
    solve.add_argument("config", help="Path to the project configuration file")
    solve.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    solve.add_argument("--lock-r", dest="lock_r", help="Override the R version to lock during resolution")
    solve.add_argument("--prefer-bioc", help="Preferred Bioconductor release to evaluate against")
    solve.add_argument("--include-optional", action="store_true", help="Include Suggests dependencies where possible")
    solve.set_defaults(func=cmd_solve)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

