from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from build import (
    ALIASES_ACTION_UID,
    ALIASES_KEYWORD_UID,
    CACHE_SECONDS,
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
    build_compatibility_snippets,
    build_snippets,
    build_workflow_items,
    load_catalog,
    run,
    workflow_plist,
    write_archive,
    write_workflow_archive,
)
from project_files import load_alias_mapping

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTED_TRIGGER = re.compile(r"`(:[a-z0-9_+\-]+:)`")
UNICODE_VERSION = re.compile(r"\d+\.\d+")


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


def test_every_shown_trigger_is_searchable() -> None:
    catalog = load_catalog(ROOT / "data" / "emoji.json")
    items = build_workflow_items(catalog)["items"]

    for item in items:
        terms = item["match"].split()
        # the title and autocomplete offer :alias:, so pasting it back must match
        assert item["autocomplete"] in terms, item["title"]


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


def test_every_result_is_an_actionable_emoji() -> None:
    items = build_workflow_items(load_catalog(ROOT / "data" / "emoji.json"))["items"]

    # category browsing was removed: searching beats tabbing through 200-emoji
    # groups, so every row must be a selectable emoji
    assert all(item.get("arg") for item in items)
    assert all(item.get("valid") is not False for item in items)


def test_group_and_subgroup_remain_searchable_terms() -> None:
    catalog = load_catalog(ROOT / "data" / "emoji.json")
    items = build_workflow_items(catalog)["items"]

    cat_face = next(item for item in items if item["arg"] == "😺")

    # the Unicode group and subgroup still feed search even without category rows
    assert "Smileys" in cat_face["match"]
    assert "cat-face" in cat_face["match"]


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

    assert zero_aliases["subtitle"] == "bellhop bell"
    assert two_aliases["subtitle"] == ":hotel_bell: · :bellhop_bell:"
    assert zero_aliases["match"] == two_aliases["match"]
    assert zero_aliases["uid"] == two_aliases["uid"]


def test_workflow_items_declare_cache_for_static_catalog() -> None:
    cache = build_workflow_items(sample_catalog())["cache"]

    assert cache == {"seconds": CACHE_SECONDS}
    # a long TTL served a stale catalog after reinstalling an updated workflow
    assert CACHE_SECONDS <= 60


def test_workflow_subtitle_never_blank_without_alternate_aliases() -> None:
    catalog = sample_catalog()
    catalog["emojis"][0]["aliases"] = ["bellhop"]

    item = next(item for item in build_workflow_items(catalog)["items"] if item.get("arg"))

    assert item["subtitle"] == "bellhop bell"


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
    assert "${emoji_alias_count" in objects[SCRIPT_FILTER_UID]["config"]["script"]
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


def test_script_filter_command_resolves_against_the_real_archive(tmp_path: Path) -> None:
    run(
        ROOT / "data" / "emoji.json",
        ROOT / "assets" / "icon.png",
        ROOT / "pyproject.toml",
        ROOT / "data" / "legacy_aliases.json",
        tmp_path / "Emoji Pack.alfredsnippets",
        tmp_path / "Emoji Aliases.alfredsnippets",
        tmp_path / "Emoji Pack.alfredworkflow",
    )
    workflow_directory = tmp_path / "workflow"
    with zipfile.ZipFile(tmp_path / "Emoji Pack.alfredworkflow") as archive:
        archive.extractall(workflow_directory)
    plist = plistlib.loads((workflow_directory / "info.plist").read_bytes())
    script = next(
        item["config"]["script"] for item in plist["objects"] if item["uid"] == SCRIPT_FILTER_UID
    )

    # Alfred runs the script filter through bash from the workflow directory,
    # so the expanded command must find a real file for every configured count
    for count in [None, *range(MAX_CONFIGURABLE_ALIASES + 1)]:
        environment = dict(os.environ)
        if count is None:
            environment.pop("emoji_alias_count", None)
        else:
            environment["emoji_alias_count"] = str(count)
        result = subprocess.run(
            ["/bin/bash", "-c", script],
            capture_output=True,
            cwd=workflow_directory,
            env=environment,
        )

        assert result.returncode == 0, result.stderr.decode()
        assert json.loads(result.stdout)["items"]


def test_workflow_canvas_lays_out_left_to_right_without_overlap() -> None:
    plist = workflow_plist("2.0.0")
    positions = plist["uidata"]

    coordinates = [(item["xpos"], item["ypos"]) for item in positions.values()]

    assert len(set(coordinates)) == len(coordinates)
    for source, connections in plist["connections"].items():
        for connection in connections:
            destination = connection["destinationuid"]
            # every wire must flow into the output column, never backwards
            assert positions[source]["xpos"] < positions[destination]["xpos"]


def test_vendored_catalog_is_current_and_has_unique_triggers() -> None:
    catalog = load_catalog(ROOT / "data" / "emoji.json")
    snippets = build_snippets(catalog)
    compatibility_snippets = build_compatibility_snippets(
        catalog, load_alias_mapping(ROOT / "data" / "legacy_aliases.json")
    )
    triggers = [snippet["alfredsnippet"]["keyword"] for snippet in snippets]
    compatibility_triggers = [
        snippet["alfredsnippet"]["keyword"] for snippet in compatibility_snippets
    ]
    bellhop_triggers = {
        snippet["alfredsnippet"]["keyword"]
        for snippet in snippets
        if snippet["alfredsnippet"]["snippet"] == "🛎️"
    }

    # pinning an exact version would break the scheduled update job on every
    # Unicode release, before it can open its pull request
    assert UNICODE_VERSION.fullmatch(str(catalog["unicode_emoji_version"]))
    assert catalog["skin_tone_variants_included"] is False
    assert len(snippets) == catalog["emoji_count"]
    assert len(triggers) == len(set(triggers))
    assert len(compatibility_triggers) == len(set(compatibility_triggers))
    assert set(triggers).isdisjoint(compatibility_triggers)
    assert compatibility_snippets
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
