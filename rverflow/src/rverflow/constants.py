"""Static data for the resolver."""
from __future__ import annotations

BASE_R_PACKAGES = {
    "base",
    "compiler",
    "datasets",
    "graphics",
    "grDevices",
    "grid",
    "methods",
    "parallel",
    "splines",
    "stats",
    "stats4",
    "tcltk",
    "tools",
    "utils",
}

SUPPORTED_R_VERSIONS = [
    "3.6.0",
    "3.6.3",
    "4.0.0",
    "4.0.2",
    "4.0.5",
    "4.1.0",
    "4.1.2",
    "4.1.3",
    "4.2.0",
    "4.2.1",
    "4.2.2",
    "4.2.3",
    "4.3.0",
    "4.3.1",
    "4.3.2",
    "4.3.3",
    "4.4.0",
    "4.4.1",
]

BIOCONDUCTOR_R_MATRIX = {
    "3.12": "4.0",
    "3.13": "4.1",
    "3.14": "4.1",
    "3.15": "4.2",
    "3.16": "4.2",
    "3.17": "4.3",
    "3.18": "4.3",
    "3.19": "4.4",
}
