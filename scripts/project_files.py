from __future__ import annotations

import json
import re
import tomllib
import zipfile
from pathlib import Path
from typing import Any

SEMANTIC_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
# a fixed timestamp keeps rebuilt archives byte-identical
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
ZIP_PERMISSIONS = 0o644 << 16


def load_json_object(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_alias_mapping(path: Path) -> dict[str, list[str]]:
    aliases = load_json_object(path).get("aliases")
    if not isinstance(aliases, dict):
        raise ValueError(f"{path} does not contain an aliases object")
    return {
        str(emoji): [alias for alias in values if isinstance(alias, str)]
        for emoji, values in aliases.items()
        if isinstance(values, list)
    }


def project_version(project_path: Path) -> str:
    payload = tomllib.loads(project_path.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not SEMANTIC_VERSION.fullmatch(version):
        raise ValueError(f"{project_path} does not contain a semantic project version")
    return version


def deterministic_zipinfo(filename: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ZIP_PERMISSIONS
    return info
