from __future__ import annotations

import json
import plistlib
import re
import zipfile
from pathlib import Path
from typing import Any

from build import (
    CLIPBOARD_UID,
    DIST_PATH,
    INSTALL_ACTION_UID,
    INSTALL_KEYWORD_UID,
    SCRIPT_FILTER_UID,
    SNIPPET_OUTPUT_PATH,
    WORKFLOW_OUTPUT_PATH,
    alternative_aliases,
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
                "name": "bellhop bell",
                "keywords": ["bellhop", "hotel", "service"],
                "primary_alias": "bellhop",
                "aliases": ["bellhop_bell", "bellhop"],
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

    item = build_workflow_items(catalog)["items"][0]

    assert item["title"] == "🛎️ - :bellhop:"
    assert item["subtitle"] == ":hotel_bell: · :bellhop_bell: · :service_bell:"
    assert item["arg"] == "🛎️"
    assert item["autocomplete"] == ":bellhop:"
    assert "bellhop_bell" in item["match"]
    assert "service" in item["match"]


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
    output = tmp_path / "Emoji Pack.alfredworkflow"
    items = build_workflow_items(sample_catalog())

    write_workflow_archive(items, snippets, icon, output, "2.0.0")

    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {
            "Emoji Pack.alfredsnippets",
            "icon.png",
            "info.plist",
            "workflow-items.json",
        }
        assert archive.read("Emoji Pack.alfredsnippets") == b"snippets"
        assert json.loads(archive.read("workflow-items.json")) == items
        workflow = plistlib.loads(archive.read("info.plist"))

    objects = {item["uid"]: item for item in workflow["objects"]}
    assert objects[SCRIPT_FILTER_UID]["config"]["alfredfiltersresults"] is True
    assert objects[CLIPBOARD_UID]["config"]["autopaste"] is True
    assert objects[INSTALL_KEYWORD_UID]["config"]["keyword"] == "emoji-install"
    assert "Emoji Pack.alfredsnippets" in objects[INSTALL_ACTION_UID]["config"]["script"]
    assert workflow["connections"][SCRIPT_FILTER_UID][0]["destinationuid"] == CLIPBOARD_UID
    assert workflow["connections"][INSTALL_KEYWORD_UID][0]["destinationuid"] == INSTALL_ACTION_UID


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
