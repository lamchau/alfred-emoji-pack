from __future__ import annotations

import json
import plistlib
import sys
import tomllib
import uuid
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "emoji.json"
ICON_PATH = ROOT / "assets" / "icon.png"
PROJECT_PATH = ROOT / "pyproject.toml"
DIST_PATH = ROOT / "dist"
SNIPPET_OUTPUT_PATH = DIST_PATH / "Emoji Pack.alfredsnippets"
WORKFLOW_OUTPUT_PATH = DIST_PATH / "Emoji Pack.alfredworkflow"
UID_NAMESPACE = uuid.UUID("56f99baa-f412-54d0-a3ac-77bb3d94af21")
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
MAX_ALTERNATIVE_ALIASES = 3
SCRIPT_FILTER_UID = "D1120E91-53C1-5142-A5FE-D72D1169240A"
CLIPBOARD_UID = "D328392E-D1D8-5A75-8F6E-E93FC6FBC2C0"
INSTALL_KEYWORD_UID = "6B9A1630-9EBF-55AE-B292-4CB57F6C655A"
INSTALL_ACTION_UID = "AC983391-67E8-5BC2-BA9C-C7B2F3F71FF6"


def load_catalog(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("emojis"), list):
        raise ValueError(f"{path} is not a valid emoji catalog")
    return payload


def snippet_name(entry: dict[str, Any]) -> str:
    emoji = str(entry["emoji"])
    primary_alias = str(entry["primary_alias"])
    return f"{emoji} - :{primary_alias}:"


def alternative_aliases(entry: dict[str, Any]) -> list[str]:
    primary_alias = str(entry["primary_alias"])
    aliases = [
        str(alias)
        for alias in entry.get("aliases", [])
        if str(alias) and str(alias) != primary_alias
    ]
    aliases.sort(key=lambda alias: (len(alias), alias))
    return aliases[:MAX_ALTERNATIVE_ALIASES]


def workflow_match_text(entry: dict[str, Any]) -> str:
    terms = {
        str(entry[field]).strip()
        for field in ("name", "unicode_name", "group", "subgroup")
        if str(entry.get(field, "")).strip()
    }
    for field in ("aliases", "keywords"):
        values = entry.get(field, [])
        if isinstance(values, list):
            terms.update(str(value).strip() for value in values if str(value).strip())

    aliases = entry.get("aliases", [])
    if isinstance(aliases, list):
        terms.update(str(alias).replace("_", " ") for alias in aliases)
    return " ".join(sorted(terms))


def build_workflow_items(catalog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    for raw_entry in catalog["emojis"]:
        if not isinstance(raw_entry, dict):
            raise ValueError("emoji catalog entries must be objects")
        emoji = str(raw_entry["emoji"])
        name = str(raw_entry["name"])
        primary_alias = str(raw_entry["primary_alias"])
        aliases = alternative_aliases(raw_entry)
        items.append(
            {
                "arg": emoji,
                "autocomplete": f":{primary_alias}:",
                "match": workflow_match_text(raw_entry),
                "subtitle": " · ".join(f":{alias}:" for alias in aliases),
                "text": {"copy": emoji, "largetype": f"{emoji} {name}"},
                "title": f"{emoji} - :{primary_alias}:",
                "uid": str(uuid.uuid5(UID_NAMESPACE, f"workflow|{emoji}")),
            }
        )
    return {"items": items}


def build_snippets(catalog: dict[str, Any]) -> list[dict[str, dict[str, str]]]:
    snippets: list[dict[str, dict[str, str]]] = []
    trigger_owners: dict[str, str] = {}

    for raw_entry in catalog["emojis"]:
        if not isinstance(raw_entry, dict):
            raise ValueError("emoji catalog entries must be objects")
        emoji = str(raw_entry["emoji"])
        aliases = raw_entry.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"{emoji} has no aliases")
        primary_alias = raw_entry.get("primary_alias")
        if not isinstance(primary_alias, str) or primary_alias not in aliases:
            raise ValueError(f"{emoji} has an invalid primary alias")

        trigger = f":{primary_alias}:"
        existing_owner = trigger_owners.setdefault(trigger, emoji)
        if existing_owner != emoji:
            raise ValueError(f"trigger {trigger} belongs to multiple emoji")
        uid = str(uuid.uuid5(UID_NAMESPACE, f"{emoji}|{trigger}"))
        snippets.append(
            {
                "alfredsnippet": {
                    "snippet": emoji,
                    "uid": uid,
                    "name": snippet_name(raw_entry),
                    "keyword": trigger,
                }
            }
        )

    return sorted(
        snippets,
        key=lambda snippet: (
            snippet["alfredsnippet"]["keyword"],
            snippet["alfredsnippet"]["snippet"],
        ),
    )


def write_archive(
    snippets: list[dict[str, dict[str, str]]], icon_path: Path, output_path: Path
) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for snippet in snippets:
            uid = snippet["alfredsnippet"]["uid"]
            info = zipfile.ZipInfo(f"{uid}.json", ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(
                info,
                json.dumps(snippet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )

        icon_info = zipfile.ZipInfo("icon.png", ZIP_TIMESTAMP)
        icon_info.compress_type = zipfile.ZIP_DEFLATED
        icon_info.external_attr = 0o644 << 16
        archive.writestr(icon_info, icon_path.read_bytes())


def workflow_plist(version: str) -> dict[str, Any]:
    return {
        "bundleid": "com.lamchau.alfred-emoji-pack",
        "category": "Tools",
        "connections": {
            SCRIPT_FILTER_UID: [
                {
                    "destinationuid": CLIPBOARD_UID,
                    "modifiers": 0,
                    "modifiersubtext": "",
                    "vitoclose": False,
                }
            ],
            INSTALL_KEYWORD_UID: [
                {
                    "destinationuid": INSTALL_ACTION_UID,
                    "modifiers": 0,
                    "modifiersubtext": "",
                    "vitoclose": False,
                }
            ],
        },
        "createdby": "Lam Chau",
        "description": "Browse, paste, and expand current Unicode emoji",
        "disabled": False,
        "name": "Emoji Pack",
        "objects": [
            {
                "config": {
                    "alfredfiltersresults": True,
                    "alfredfiltersresultsmatchmode": 0,
                    "argumenttreatemptyqueryasnil": False,
                    "argumenttrimmode": 0,
                    "argumenttype": 1,
                    "escaping": 102,
                    "keyword": "emoji",
                    "queuedelaycustom": 1,
                    "queuedelayimmediatelyinitially": True,
                    "queuedelaymode": 0,
                    "queuemode": 1,
                    "runningsubtext": "Loading emoji...",
                    "script": "/bin/cat workflow-items.json",
                    "scriptargtype": 0,
                    "scriptfile": "",
                    "subtext": "Search names, aliases, and descriptive keywords",
                    "title": "Browse Emoji",
                    "type": 0,
                    "withspace": True,
                },
                "type": "alfred.workflow.input.scriptfilter",
                "uid": SCRIPT_FILTER_UID,
                "version": 3,
            },
            {
                "config": {
                    "autopaste": True,
                    "clipboardtext": "{query}",
                    "ignoredynamicplaceholders": False,
                    "transient": False,
                },
                "type": "alfred.workflow.output.clipboard",
                "uid": CLIPBOARD_UID,
                "version": 3,
            },
            {
                "config": {
                    "argumenttype": 2,
                    "keyword": "emoji-install",
                    "subtext": "Import colon triggers into Alfred Snippets",
                    "text": "Install Emoji Expansion",
                    "withspace": False,
                },
                "type": "alfred.workflow.input.keyword",
                "uid": INSTALL_KEYWORD_UID,
                "version": 1,
            },
            {
                "config": {
                    "concurrently": False,
                    "escaping": 0,
                    "script": '/usr/bin/open "Emoji Pack.alfredsnippets"',
                    "scriptargtype": 0,
                    "scriptfile": "",
                    "type": 0,
                },
                "type": "alfred.workflow.action.script",
                "uid": INSTALL_ACTION_UID,
                "version": 2,
            },
        ],
        "readme": (
            "Type “emoji” followed by a query to browse and paste emoji.\n\n"
            "Run “emoji-install” once to import the bundled colon-trigger snippets."
        ),
        "uidata": {
            SCRIPT_FILTER_UID: {"xpos": 30, "ypos": 30},
            CLIPBOARD_UID: {"xpos": 300, "ypos": 30},
            INSTALL_KEYWORD_UID: {"xpos": 30, "ypos": 180},
            INSTALL_ACTION_UID: {"xpos": 300, "ypos": 180},
        },
        "version": version,
        "webaddress": "https://github.com/lamchau/alfred-emoji-pack",
    }


def write_workflow_archive(
    workflow_items: dict[str, list[dict[str, Any]]],
    snippet_path: Path,
    icon_path: Path,
    output_path: Path,
    version: str,
) -> None:
    entries = {
        "Emoji Pack.alfredsnippets": snippet_path.read_bytes(),
        "icon.png": icon_path.read_bytes(),
        "info.plist": plistlib.dumps(workflow_plist(version), sort_keys=False),
        "workflow-items.json": (
            json.dumps(workflow_items, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode(),
    }
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in entries.items():
            info = zipfile.ZipInfo(filename, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)


def project_version(project_path: Path) -> str:
    payload = tomllib.loads(project_path.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str):
        raise ValueError(f"{project_path} does not contain a project version")
    return version


def run(
    catalog_path: Path,
    icon_path: Path,
    project_path: Path,
    snippet_output_path: Path,
    workflow_output_path: Path,
) -> None:
    catalog = load_catalog(catalog_path)
    snippets = build_snippets(catalog)
    snippet_output_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_output_path.parent.mkdir(parents=True, exist_ok=True)
    write_archive(snippets, icon_path, snippet_output_path)
    write_workflow_archive(
        build_workflow_items(catalog),
        snippet_output_path,
        icon_path,
        workflow_output_path,
        project_version(project_path),
    )
    print(
        f"Built {snippet_output_path.name} and {workflow_output_path.name}: "
        f"{len(snippets)} emoji (Unicode Emoji {catalog['unicode_emoji_version']})"
    )


def main() -> None:
    try:
        run(
            CATALOG_PATH,
            ICON_PATH,
            PROJECT_PATH,
            SNIPPET_OUTPUT_PATH,
            WORKFLOW_OUTPUT_PATH,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
