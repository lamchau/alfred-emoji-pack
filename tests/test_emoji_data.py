from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from emoji_data import (
    Annotation,
    EmojiRecord,
    compile_catalog,
    has_skin_tone_modifier,
    load_preferred_aliases,
    normalize_legacy_alias,
    parse_emoji_test,
    slugify,
)
from project_files import project_version
from update_emoji_data import (
    PackConfig,
    load_config,
    request_headers,
    resolve_include_skin_tones,
)

PROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def make_record(emoji: str, name: str) -> EmojiRecord:
    return EmojiRecord(
        emoji=emoji,
        unicode_name=name,
        emoji_version="1.0",
        group="Objects",
        subgroup="sound",
    )


def test_parse_emoji_test_keeps_only_fully_qualified_emoji() -> None:
    text = """\
# Version: 18.0
# Date: 2026-04-30
# group: Objects
# subgroup: bell
1F514                                      ; fully-qualified     # 🔔 E0.6 bell
1F6CE FE0F                                 ; fully-qualified     # 🛎️ E0.7 bellhop bell
1F6CE                                      ; unqualified         # 🛎 E0.7 bellhop bell
"""

    metadata, records = parse_emoji_test(text)

    assert metadata["unicode_emoji_version"] == "18.0"
    assert [record.emoji for record in records] == ["🔔", "🛎️"]


def test_aliases_are_descriptive_without_stealing_canonical_trigger() -> None:
    records = [
        make_record("🔔", "bell"),
        make_record("🛎️", "bellhop bell"),
    ]
    annotations = {
        "🔔": Annotation("bell", frozenset({"sound"})),
        "🛎️": Annotation("bellhop bell", frozenset({"bellhop", "hotel", "service"})),
    }

    catalog = compile_catalog(records, annotations, {}, {"🛎️": "bellhop"})
    aliases = {str(entry["emoji"]): cast(list[str], entry["aliases"]) for entry in catalog}
    primary_aliases = {str(entry["emoji"]): str(entry["primary_alias"]) for entry in catalog}

    assert "bell" in aliases["🔔"]
    assert "bell" not in aliases["🛎️"]
    assert "bellhop_bell" in aliases["🛎️"]
    assert "bellhop" in aliases["🛎️"]
    assert "hotel" in aliases["🛎️"]
    assert primary_aliases == {"🔔": "bell", "🛎️": "bellhop"}


def test_canonical_alias_remains_primary_without_override() -> None:
    records = [make_record("😂", "face with tears of joy")]
    annotations = {"😂": Annotation("face with tears of joy", frozenset({"joy", "laugh"}))}

    catalog = compile_catalog(
        records,
        annotations,
        {"😂": ["face_with_tears_of_joy", "joy"]},
    )

    assert catalog[0]["primary_alias"] == "face_with_tears_of_joy"


def test_skin_tone_modifiers_are_detected() -> None:
    assert has_skin_tone_modifier("👍🏽") is True
    assert has_skin_tone_modifier("👍") is False


def test_preferred_aliases_are_loaded_and_normalized(tmp_path: Path) -> None:
    path = tmp_path / "preferred.json"
    path.write_text('{"aliases": {"🛎️": ":Bellhop:"}}', encoding="utf-8")

    assert load_preferred_aliases(path) == {"🛎️": "bellhop"}


def test_github_api_requests_use_available_token() -> None:
    headers = request_headers(
        "https://api.github.com/repos/unicode-org/cldr/commits/main",
        {"GITHUB_TOKEN": "secret"},
    )

    assert headers["Authorization"] == "Bearer secret"
    assert headers["User-Agent"] == f"alfred-emoji-pack/{project_version(PROJECT_PATH)}"
    assert "Authorization" not in request_headers(
        "https://www.unicode.org/Public/emoji/latest/emoji-test.txt",
        {"GITHUB_TOKEN": "secret"},
    )


def test_skin_tone_config_and_override(tmp_path: Path) -> None:
    path = tmp_path / "emoji-pack.toml"
    path.write_text("[emoji]\ninclude_skin_tones = false\n", encoding="utf-8")

    config = load_config(path)

    assert config == PackConfig(include_skin_tones=False)
    assert resolve_include_skin_tones(config, None) is False
    assert resolve_include_skin_tones(config, True) is True


def test_skin_tone_config_requires_boolean(tmp_path: Path) -> None:
    path = tmp_path / "emoji-pack.toml"
    path.write_text('[emoji]\ninclude_skin_tones = "sometimes"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="true or false"):
        load_config(path)


def test_legacy_alias_normalization_preserves_plus_and_minus() -> None:
    assert normalize_legacy_alias(":+1:") == "+1"
    assert normalize_legacy_alias(":-1:") == "-1"
    assert normalize_legacy_alias(":construction worker:") == "construction_worker"


def test_slugify_produces_alfred_friendly_names() -> None:
    assert slugify("Woman’s Hat") == "womans_hat"
    assert slugify("A & B") == "a_and_b"
    assert slugify("keycap: #") == "keycap_hash"
    assert slugify("keycap: *") == "keycap_asterisk"
