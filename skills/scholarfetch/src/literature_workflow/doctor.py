"""Dependency checks without opening browsers, reading cookies, or making requests."""

from __future__ import annotations

import importlib.util
import os
import sys
from importlib.metadata import PackageNotFoundError, version


def check_dependencies(mode: str = "all") -> dict:
    required = ["requests"]
    if mode in {"all", "download"}:
        required.append("pypdf")
    checks = []
    for package in required:
        available = importlib.util.find_spec(package) is not None
        try:
            installed_version = version(package) if available else None
        except PackageNotFoundError:
            installed_version = None
        checks.append({"name": package, "required": True, "available": available, "version": installed_version})
    browser = importlib.util.find_spec("cloakbrowser") is not None
    checks.append({"name": "cloakbrowser", "required": False, "available": browser,
                   "impact_if_missing": "HTTP acquisition remains available; browser fallback requires the browser extra."})
    missing = [item["name"] for item in checks if item["required"] and not item["available"]]
    python_ok = sys.version_info >= (3, 11)
    return {
        "ok": python_ok and not missing, "mode": mode,
        "python_supported": python_ok, "dependencies": checks,
        "missing_required": missing,
        "remedy": "Install Python 3.11+ and this project in a local virtual environment." if not python_ok or missing else None,
        "source_configuration": {name: bool(os.getenv(name)) for name in ("PUBMED_EMAIL", "NCBI_API_KEY", "OPENALEX_API_KEY", "S2_API_KEY")},
        "notes": ["API credentials are optional for the default Crossref/Europe PMC route.",
                  "PubMed requires PUBMED_EMAIL in this implementation; other services may impose authentication or rate limits.",
                  "This check does not prove connectivity, a downloaded browser binary, institutional access, or publisher coverage."],
    }
