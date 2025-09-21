"""Top-level package for R package dependency resolver."""

from .cli import main as cli_main

__all__ = ["cli_main"]
