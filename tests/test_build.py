from __future__ import annotations

import json
import plistlib
import re
import zipfile
from pathlib import Path
from typing import Any

from build import (
    ALIASES_ACTION_UID,
    ALIASES_KEYWORD_UID,
    CLIPBOARD_UID,
    COMMAND_MODIFIER,
    COMPATIBILITY_OUTPUT_PATH,
    COPY_CLIPBOARD_UID,
    DIST_PATH,
    INSTALL_ACTION_UID,
    INSTALL_KEYWORD_UID,
    MAX_CONFIGURABLE_ALIASES,
    OPTION_MODIFIER,
    REFRESH_KEYWORD_UID,
    SCRIPT_FILTER_UID,
    SNIPPET_OUTPUT_PATH,
    WORKFLOW_OUTPUT_PATH,
    alternative_aliases,
    build_category_items,
    build_compatibility_snippets,
    build_snippets,
    build_workflow_items,
    load_catalog,
    write_archive,
    write_workflow_archive,
)

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTED_TRIGGER = re.compile(r"`(:[a-z0-9_+\-]+:)`")


def sample_catalog() -> dict[str, Any]:
    return {
        "emoji_count": 1,
        "unicode_emoji_version": "18.0",
        "emojis": [
            {
                "emoji": "🛎️",
                "group": "Objects",
                "name": "bellhop bell",
                "keywords": ["bellhop", "hotel", "service"],
                "primary_alias": "bellhop",
                "aliases": ["bellhop_bell", "bellhop"],
                "subgroup": "hotel",
                "unicode_name": "bellhop bell",
            }
        ],
    }


def test_build_snippets_creates_one_stable_primary_trigger() -> None:
    snippets = build_snippets(sample_catalog())

    assert [snippet["alfredsnippet"]["keyword"] for snippet in snippets] == [":bellhop:"]
    assert len({snippet["alfredsnippet"]["uid"] for snippet in snippets}) == 1
    assert snippets[0]["alfredsnippet"]["name"] == "🛎️ - :bellhop:"


def test_default_packages_are_built_under_ignored_dist_directory() -> None:
    ignored_paths = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert DIST_PATH == ROOT / "dist"
    assert SNIPPET_OUTPUT_PATH.parent == DIST_PATH
    assert COMPATIBILITY_OUTPUT_PATH.parent == DIST_PATH
    assert WORKFLOW_OUTPUT_PATH.parent == DIST_PATH
    assert "dist/" in ignored_paths


def test_alternative_aliases_exclude_primary_and_cap_visible_aliases() -> None:
    entry = sample_catalog()["emojis"][0]
    entry["aliases"] = [
        "bellhop_bell",
        "service_bell",
        "bellhop",
        "hotel_bell",
        "reception_bell",
    ]

    assert alternative_aliases(entry) == ["hotel_bell", "bellhop_bell", "service_bell"]


def test_workflow_items_search_every_term_but_show_three_aliases() -> None:
    catalog = sample_catalog()
    entry = catalog["emojis"][0]
    entry["aliases"] = ["bellhop", "bellhop_bell", "service_bell", "hotel_bell"]

    item = next(item for item in build_workflow_items(catalog)["items"] if item.get("arg"))

    assert item["title"] == "🛎️ - :bellhop:"
    assert item["subtitle"] == ":hotel_bell: · :bellhop_bell: · :service_bell:"
    assert item["arg"] == "🛎️"
    assert item["autocomplete"] == ":bellhop:"
    assert "bellhop_bell" in item["match"]
    assert "service" in item["match"]
    assert item["mods"] == {
        "alt": {
            "arg": ":bellhop:",
            "subtitle": "Copy :bellhop:",
            "valid": True,
        },
        "cmd": {"arg": "🛎️", "subtitle": "Copy 🛎️", "valid": True},
    }


def test_workflow_categories_filter_the_static_catalog() -> None:
    categories = build_category_items(sample_catalog())

    assert categories == [
        {
            "autocomplete": "Objects",
            "match": "Objects category browse",
            "subtitle": "Browse 1 emoji · press Tab to filter",
            "title": "Objects",
            "uid": categories[0]["uid"],
            "valid": False,
        }
    ]


def test_workflow_alias_count_variants_change_only_visible_alternatives() -> None:
    catalog = sample_catalog()
    entry = catalog["emojis"][0]
    entry["aliases"] = ["bellhop", "bellhop_bell", "service_bell", "hotel_bell"]

    zero_aliases = next(
        item for item in build_workflow_items(catalog, 0)["items"] if item.get("arg")
    )
    two_aliases = next(
        item for item in build_workflow_items(catalog, 2)["items"] if item.get("arg")
    )

    assert zero_aliases["subtitle"] == ""
    assert two_aliases["subtitle"] == ":hotel_bell: · :bellhop_bell:"
    assert zero_aliases["match"] == two_aliases["match"]


def test_compatibility_snippets_include_accepted_legacy_aliases_only() -> None:
    catalog = sample_catalog()
    catalog["emojis"][0]["aliases"] = ["bellhop", "bellhop_bell", "hotel_bell"]

    snippets = build_compatibility_snippets(
        catalog,
        {"🛎️": [":bellhop:", ":bellhop_bell:", ":unknown:"]},
    )

    assert [snippet["alfredsnippet"]["keyword"] for snippet in snippets] == [":bellhop_bell:"]
    assert snippets[0]["alfredsnippet"]["name"].endswith("alias for :bellhop:")


def test_archive_contains_importable_snippet_json_and_icon(tmp_path: Path) -> None:
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")
    output = tmp_path / "emoji.alfredsnippets"
    snippets = build_snippets(sample_catalog())

    write_archive(snippets, icon, output)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[-1] == "icon.png"
        snippet_payload = json.loads(archive.read(names[0]))
        assert snippet_payload["alfredsnippet"]["keyword"] == ":bellhop:"


def test_workflow_archive_contains_browser_and_snippet_installer(tmp_path: Path) -> None:
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")
    snippets = tmp_path / "Emoji Pack.alfredsnippets"
    snippets.write_bytes(b"snippets")
    compatibility = tmp_path / "Emoji Aliases.alfredsnippets"
    compatibility.write_bytes(b"aliases")
    output = tmp_path / "Emoji Pack.alfredworkflow"
    item_variants = {
        count: build_workflow_items(sample_catalog(), count)
        for count in range(MAX_CONFIGURABLE_ALIASES + 1)
    }

    write_workflow_archive(
        item_variants,
        snippets,
        compatibility,
        icon,
        output,
        "2.0.0",
    )

    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {
            "Emoji Aliases.alfredsnippets",
            "Emoji Pack.alfredsnippets",
            "icon.png",
            "info.plist",
            *{f"workflow-items-{count}.json" for count in range(MAX_CONFIGURABLE_ALIASES + 1)},
        }
        assert archive.read("Emoji Pack.alfredsnippets") == b"snippets"
        assert archive.read("Emoji Aliases.alfredsnippets") == b"aliases"
        assert json.loads(archive.read("workflow-items-3.json")) == item_variants[3]
        workflow = plistlib.loads(archive.read("info.plist"))

    objects = {item["uid"]: item for item in workflow["objects"]}
    assert objects[SCRIPT_FILTER_UID]["config"]["alfredfiltersresults"] is True
    assert objects[SCRIPT_FILTER_UID]["config"]["keyword"] == "{var:emoji_keyword}"
    assert "{var:emoji_alias_count}" in objects[SCRIPT_FILTER_UID]["config"]["script"]
    assert objects[CLIPBOARD_UID]["config"]["autopaste"] is True
    assert objects[COPY_CLIPBOARD_UID]["config"]["autopaste"] is False
    assert objects[INSTALL_KEYWORD_UID]["config"]["keyword"] == "emoji-install"
    assert objects[REFRESH_KEYWORD_UID]["config"]["keyword"] == "emoji-refresh"
    assert objects[ALIASES_KEYWORD_UID]["config"]["keyword"] == "emoji-install-aliases"
    assert "Emoji Pack.alfredsnippets" in objects[INSTALL_ACTION_UID]["config"]["script"]
    assert "Emoji Aliases.alfredsnippets" in objects[ALIASES_ACTION_UID]["config"]["script"]
    assert workflow["connections"][SCRIPT_FILTER_UID][0]["destinationuid"] == CLIPBOARD_UID
    assert {
        connection["modifiers"] for connection in workflow["connections"][SCRIPT_FILTER_UID]
    } == {0, COMMAND_MODIFIER, OPTION_MODIFIER}
    assert workflow["connections"][INSTALL_KEYWORD_UID][0]["destinationuid"] == INSTALL_ACTION_UID
    assert workflow["connections"][REFRESH_KEYWORD_UID][0]["destinationuid"] == INSTALL_ACTION_UID
    assert workflow["connections"][ALIASES_KEYWORD_UID][0]["destinationuid"] == ALIASES_ACTION_UID
    configuration = {item["variable"]: item for item in workflow["userconfigurationconfig"]}
    assert configuration["emoji_keyword"]["config"]["default"] == "emoji"
    assert configuration["emoji_alias_count"]["config"]["default"] == "3"


def test_vendored_catalog_is_unicode_18_and_has_unique_triggers() -> None:
    catalog = load_catalog(ROOT / "data" / "emoji.json")
    snippets = build_snippets(catalog)
    triggers = [snippet["alfredsnippet"]["keyword"] for snippet in snippets]
    bellhop_triggers = {
        snippet["alfredsnippet"]["keyword"]
        for snippet in snippets
        if snippet["alfredsnippet"]["snippet"] == "🛎️"
    }

    assert catalog["unicode_emoji_version"] == "18.0"
    assert catalog["skin_tone_variants_included"] is False
    assert len(snippets) == catalog["emoji_count"]
    assert len(triggers) == len(set(triggers))
    assert bellhop_triggers == {":bellhop:"}
    assert (
        next(entry["primary_alias"] for entry in catalog["emojis"] if entry["emoji"] == "☔")
        == "umbrella_rain"
    )
    assert all(
        not any(0x1F3FB <= ord(character) <= 0x1F3FF for character in entry["emoji"])
        for entry in catalog["emojis"]
    )


def test_readme_triggers_exist_in_archive() -> None:
    catalog = load_catalog(ROOT / "data" / "emoji.json")
    generated_triggers = {
        snippet["alfredsnippet"]["keyword"] for snippet in build_snippets(catalog)
    }
    documented_triggers = set(
        DOCUMENTED_TRIGGER.findall((ROOT / "README.md").read_text(encoding="utf-8"))
    )

    assert documented_triggers <= generated_triggers
