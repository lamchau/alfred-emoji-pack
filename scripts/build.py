from __future__ import annotations

import json
import plistlib
import sys
import tomllib
import uuid
import zipfile
from pathlib import Path
from typing import Any

from emoji_data import normalize_legacy_alias
from project_files import (
    deterministic_zipinfo,
    load_alias_mapping,
    load_json_object,
    project_version,
)

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "emoji.json"
LEGACY_ALIASES_PATH = ROOT / "data" / "legacy_aliases.json"
ICON_PATH = ROOT / "assets" / "icon.png"
PROJECT_PATH = ROOT / "pyproject.toml"
DIST_PATH = ROOT / "dist"
SNIPPET_OUTPUT_PATH = DIST_PATH / "Emoji Pack.alfredsnippets"
COMPATIBILITY_OUTPUT_PATH = DIST_PATH / "Emoji Aliases.alfredsnippets"
WORKFLOW_OUTPUT_PATH = DIST_PATH / "Emoji Pack.alfredworkflow"
UID_NAMESPACE = uuid.UUID("56f99baa-f412-54d0-a3ac-77bb3d94af21")
MAX_ALTERNATIVE_ALIASES = 3
# keep results warm between keystrokes without serving a stale catalog after an
# update; Alfred's minimum is 5 seconds
CACHE_SECONDS = 5
MAX_CONFIGURABLE_ALIASES = 5
SCRIPT_FILTER_UID = "D1120E91-53C1-5142-A5FE-D72D1169240A"
CLIPBOARD_UID = "D328392E-D1D8-5A75-8F6E-E93FC6FBC2C0"
COPY_CLIPBOARD_UID = "421A4BF8-2354-58C9-9254-D5E538CB8742"
INSTALL_KEYWORD_UID = "6B9A1630-9EBF-55AE-B292-4CB57F6C655A"
INSTALL_ACTION_UID = "AC983391-67E8-5BC2-BA9C-C7B2F3F71FF6"
REFRESH_KEYWORD_UID = "A84DA05A-C425-55E0-8D14-3D6364D9AE67"
ALIASES_KEYWORD_UID = "1F40BB79-8CDD-51B6-9A49-B17733C46C62"
ALIASES_ACTION_UID = "5D897E58-D220-5283-BA6F-98526474AA3F"
COMMAND_MODIFIER = 1_048_576
OPTION_MODIFIER = 524_288
INPUT_COLUMN = 30
OUTPUT_COLUMN = 300


def load_catalog(path: Path) -> dict[str, Any]:
    payload = load_json_object(path)
    if not isinstance(payload.get("emojis"), list):
        raise ValueError(f"{path} is not a valid emoji catalog")
    return payload


def snippet_name(entry: dict[str, Any]) -> str:
    emoji = str(entry["emoji"])
    primary_alias = str(entry["primary_alias"])
    return f"{emoji} - :{primary_alias}:"


def alternative_aliases(entry: dict[str, Any], maximum: int = MAX_ALTERNATIVE_ALIASES) -> list[str]:
    primary_alias = str(entry["primary_alias"])
    aliases = [
        str(alias)
        for alias in entry.get("aliases", [])
        if str(alias) and str(alias) != primary_alias
    ]
    aliases.sort(key=lambda alias: (len(alias), alias))
    return aliases[:maximum]


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
        # the title and autocomplete both show :alias:, so searching for the
        # trigger Alfred just offered has to match
        terms.update(f":{alias}:" for alias in aliases if str(alias))
    return " ".join(sorted(terms))


def workflow_subtitle(entry: dict[str, Any], aliases: list[str]) -> str:
    if aliases:
        return " · ".join(f":{alias}:" for alias in aliases)
    # most emoji have no alternate alias; fall back so the row is never blank
    name = str(entry.get("name", "")).strip()
    subgroup = str(entry.get("subgroup", "")).strip()
    return name or subgroup


def build_workflow_items(
    catalog: dict[str, Any], maximum_alternative_aliases: int = MAX_ALTERNATIVE_ALIASES
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for raw_entry in catalog["emojis"]:
        if not isinstance(raw_entry, dict):
            raise ValueError("emoji catalog entries must be objects")
        emoji = str(raw_entry["emoji"])
        name = str(raw_entry["name"])
        primary_alias = str(raw_entry["primary_alias"])
        trigger = f":{primary_alias}:"
        aliases = alternative_aliases(raw_entry, maximum_alternative_aliases)
        items.append(
            {
                "arg": emoji,
                "autocomplete": trigger,
                "match": workflow_match_text(raw_entry),
                "mods": {
                    "alt": {
                        "arg": trigger,
                        "subtitle": f"Copy {trigger}",
                        "valid": True,
                    },
                    "cmd": {
                        "arg": emoji,
                        "subtitle": f"Copy {emoji}",
                        "valid": True,
                    },
                },
                "subtitle": workflow_subtitle(raw_entry, aliases),
                "text": {"copy": emoji, "largetype": f"{emoji} {name}"},
                "title": f"{emoji} - {trigger}",
                "uid": str(uuid.uuid5(UID_NAMESPACE, f"workflow|{emoji}")),
            }
        )
    return {
        # a short TTL keeps repeated keystrokes fast; loosereload is off so an
        # updated catalog is never served from a stale cache
        "cache": {"seconds": CACHE_SECONDS},
        "items": items,
    }


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


def build_compatibility_snippets(
    catalog: dict[str, Any], legacy_aliases: dict[str, list[str]]
) -> list[dict[str, dict[str, str]]]:
    snippets: list[dict[str, dict[str, str]]] = []
    trigger_owners: dict[str, str] = {}

    for raw_entry in catalog["emojis"]:
        if not isinstance(raw_entry, dict):
            raise ValueError("emoji catalog entries must be objects")
        emoji = str(raw_entry["emoji"])
        primary_alias = str(raw_entry["primary_alias"])
        accepted_aliases = {str(alias) for alias in raw_entry.get("aliases", [])}
        legacy_values = legacy_aliases.get(
            emoji, legacy_aliases.get(emoji.replace("\ufe0f", ""), [])
        )
        aliases = {
            alias
            for value in legacy_values
            if (alias := normalize_legacy_alias(value)) in accepted_aliases
            and alias != primary_alias
        }
        for alias in aliases:
            trigger = f":{alias}:"
            existing_owner = trigger_owners.setdefault(trigger, emoji)
            if existing_owner != emoji:
                raise ValueError(f"compatibility trigger {trigger} belongs to multiple emoji")
            uid = str(uuid.uuid5(UID_NAMESPACE, f"{emoji}|{trigger}"))
            snippets.append(
                {
                    "alfredsnippet": {
                        "keyword": trigger,
                        "name": f"{emoji} - {trigger} - alias for :{primary_alias}:",
                        "snippet": emoji,
                        "uid": uid,
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
            archive.writestr(
                deterministic_zipinfo(f"{uid}.json"),
                json.dumps(snippet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )

        archive.writestr(deterministic_zipinfo("icon.png"), icon_path.read_bytes())


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
                },
                {
                    "destinationuid": COPY_CLIPBOARD_UID,
                    "modifiers": COMMAND_MODIFIER,
                    "modifiersubtext": "Copy emoji",
                    "vitoclose": False,
                },
                {
                    "destinationuid": COPY_CLIPBOARD_UID,
                    "modifiers": OPTION_MODIFIER,
                    "modifiersubtext": "Copy preferred trigger",
                    "vitoclose": False,
                },
            ],
            INSTALL_KEYWORD_UID: [
                {
                    "destinationuid": INSTALL_ACTION_UID,
                    "modifiers": 0,
                    "modifiersubtext": "",
                    "vitoclose": False,
                }
            ],
            REFRESH_KEYWORD_UID: [
                {
                    "destinationuid": INSTALL_ACTION_UID,
                    "modifiers": 0,
                    "modifiersubtext": "",
                    "vitoclose": False,
                }
            ],
            ALIASES_KEYWORD_UID: [
                {
                    "destinationuid": ALIASES_ACTION_UID,
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
                    "keyword": "{var:emoji_keyword}",
                    "queuedelaycustom": 1,
                    "queuedelayimmediatelyinitially": True,
                    "queuedelaymode": 0,
                    "queuemode": 1,
                    "runningsubtext": "Loading emoji...",
                    # Alfred expands {var:...} in keywords, but exports workflow
                    # configuration to scripts as environment variables instead
                    "script": (
                        "/bin/cat "
                        f'"workflow-items-${{emoji_alias_count:-{MAX_ALTERNATIVE_ALIASES}}}.json"'
                    ),
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
                    "autopaste": False,
                    "clipboardtext": "{query}",
                    "ignoredynamicplaceholders": False,
                    "transient": False,
                },
                "type": "alfred.workflow.output.clipboard",
                "uid": COPY_CLIPBOARD_UID,
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
                    "subtext": "Import preferred colon triggers into Alfred Snippets",
                    "text": "Install Emoji Expansion",
                    "withspace": False,
                },
                "type": "alfred.workflow.input.keyword",
                "uid": INSTALL_KEYWORD_UID,
                "version": 1,
            },
            {
                "config": {
                    "argumenttype": 2,
                    "keyword": "emoji-refresh",
                    "subtext": "Reimport the current preferred trigger collection",
                    "text": "Refresh Emoji Expansion",
                    "withspace": False,
                },
                "type": "alfred.workflow.input.keyword",
                "uid": REFRESH_KEYWORD_UID,
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
            {
                "config": {
                    "argumenttype": 2,
                    "keyword": "emoji-install-aliases",
                    "subtext": "Optional legacy triggers create duplicate snippet results",
                    "text": "Install Legacy Emoji Aliases",
                    "withspace": False,
                },
                "type": "alfred.workflow.input.keyword",
                "uid": ALIASES_KEYWORD_UID,
                "version": 1,
            },
            {
                "config": {
                    "concurrently": False,
                    "escaping": 0,
                    "script": '/usr/bin/open "Emoji Aliases.alfredsnippets"',
                    "scriptargtype": 0,
                    "scriptfile": "",
                    "type": 0,
                },
                "type": "alfred.workflow.action.script",
                "uid": ALIASES_ACTION_UID,
                "version": 2,
            },
        ],
        "readme": (
            "Type “emoji” followed by a query to browse and paste emoji.\n\n"
            "Run “emoji-install” once to import preferred colon triggers. "
            "Use “emoji-refresh” after updates, or “emoji-install-aliases” "
            "for optional legacy expansion triggers."
        ),
        # positions mirror the canvas arranged by hand in Alfred's editor
        "uidata": {
            CLIPBOARD_UID: {"xpos": OUTPUT_COLUMN, "ypos": 45},
            SCRIPT_FILTER_UID: {"xpos": INPUT_COLUMN, "ypos": 105},
            COPY_CLIPBOARD_UID: {"xpos": OUTPUT_COLUMN, "ypos": 165},
            INSTALL_KEYWORD_UID: {"xpos": INPUT_COLUMN, "ypos": 300},
            INSTALL_ACTION_UID: {"xpos": OUTPUT_COLUMN, "ypos": 360},
            REFRESH_KEYWORD_UID: {"xpos": INPUT_COLUMN, "ypos": 420},
            ALIASES_KEYWORD_UID: {"xpos": INPUT_COLUMN, "ypos": 585},
            ALIASES_ACTION_UID: {"xpos": OUTPUT_COLUMN, "ypos": 585},
        },
        "userconfigurationconfig": [
            {
                "config": {
                    "default": "emoji",
                    "placeholder": "emoji",
                    "required": True,
                    "trim": True,
                },
                "description": "Keyword used to open the emoji browser.",
                "label": "Search keyword",
                "type": "textfield",
                "variable": "emoji_keyword",
            },
            {
                "config": {
                    "default": str(MAX_ALTERNATIVE_ALIASES),
                    "pairs": [
                        [str(count), str(count)] for count in range(MAX_CONFIGURABLE_ALIASES + 1)
                    ],
                },
                "description": "Number of alternate aliases shown below each result.",
                "label": "Displayed alternate aliases",
                "type": "popupbutton",
                "variable": "emoji_alias_count",
            },
        ],
        "variablesdontexport": [],
        "version": version,
        "webaddress": "https://github.com/lamchau/alfred-emoji-pack",
    }


def write_workflow_archive(
    workflow_item_variants: dict[int, dict[str, Any]],
    snippet_path: Path,
    compatibility_path: Path,
    icon_path: Path,
    output_path: Path,
    version: str,
) -> None:
    entries = {
        "Emoji Aliases.alfredsnippets": compatibility_path.read_bytes(),
        "Emoji Pack.alfredsnippets": snippet_path.read_bytes(),
        "icon.png": icon_path.read_bytes(),
        "info.plist": plistlib.dumps(workflow_plist(version), sort_keys=False),
    }
    entries.update(
        {
            f"workflow-items-{count}.json": (
                # compact separators cut ~26% off files Alfred re-reads per keystroke
                json.dumps(items, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            ).encode()
            for count, items in workflow_item_variants.items()
        }
    )
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in entries.items():
            archive.writestr(deterministic_zipinfo(filename), content)


def run(
    catalog_path: Path,
    icon_path: Path,
    project_path: Path,
    legacy_aliases_path: Path,
    snippet_output_path: Path,
    compatibility_output_path: Path,
    workflow_output_path: Path,
) -> None:
    catalog = load_catalog(catalog_path)
    snippets = build_snippets(catalog)
    compatibility_snippets = build_compatibility_snippets(
        catalog, load_alias_mapping(legacy_aliases_path)
    )
    snippet_output_path.parent.mkdir(parents=True, exist_ok=True)
    write_archive(snippets, icon_path, snippet_output_path)
    write_archive(compatibility_snippets, icon_path, compatibility_output_path)
    write_workflow_archive(
        {
            count: build_workflow_items(catalog, count)
            for count in range(MAX_CONFIGURABLE_ALIASES + 1)
        },
        snippet_output_path,
        compatibility_output_path,
        icon_path,
        workflow_output_path,
        project_version(project_path),
    )
    print(
        f"Built {workflow_output_path.name}, {snippet_output_path.name}, and "
        f"{compatibility_output_path.name}: {len(snippets)} emoji and "
        f"{len(compatibility_snippets)} legacy aliases "
        f"(Unicode Emoji {catalog['unicode_emoji_version']})"
    )


def main() -> None:
    try:
        run(
            CATALOG_PATH,
            ICON_PATH,
            PROJECT_PATH,
            LEGACY_ALIASES_PATH,
            SNIPPET_OUTPUT_PATH,
            COMPATIBILITY_OUTPUT_PATH,
            WORKFLOW_OUTPUT_PATH,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
