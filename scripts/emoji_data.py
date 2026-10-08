from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ElementTree
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

EMOJI_LINE = re.compile(r"^([0-9A-F ]+)\s*;\s*([^#]+)#\s*(\S+)\s+E([\d.]+)\s+(.+)$")
VERSION_LINE = re.compile(r"^# Version:\s*(.+)$")
DATE_LINE = re.compile(r"^# Date:\s*(.+)$")
SAFE_LEGACY_ALIAS = re.compile(r"[^a-z0-9_+\-]")
SKIN_TONE_MODIFIERS = range(0x1F3FB, 0x1F400)


@dataclass(frozen=True)
class EmojiRecord:
    emoji: str
    unicode_name: str
    emoji_version: str
    group: str
    subgroup: str


@dataclass(frozen=True)
class Annotation:
    name: str | None
    keywords: frozenset[str]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("#", " hash ")
    normalized = normalized.replace("*", " asterisk ")
    normalized = normalized.replace("’", "").replace("'", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", normalized)).strip("_")


def normalize_legacy_alias(value: str) -> str:
    alias = value.strip().strip(":").lower().replace(" ", "_")
    alias = SAFE_LEGACY_ALIAS.sub("", alias)
    return re.sub(r"_+", "_", alias).strip("_")


def has_skin_tone_modifier(emoji: str) -> bool:
    return any(ord(character) in SKIN_TONE_MODIFIERS for character in emoji)


def parse_emoji_test(text: str) -> tuple[dict[str, str], list[EmojiRecord]]:
    metadata: dict[str, str] = {}
    records: list[EmojiRecord] = []
    current_group = ""
    current_subgroup = ""

    for line in text.splitlines():
        if version_match := VERSION_LINE.match(line):
            metadata["unicode_emoji_version"] = version_match.group(1).strip()
            continue
        if date_match := DATE_LINE.match(line):
            metadata["unicode_data_date"] = date_match.group(1).strip()
            continue
        if line.startswith("# group:"):
            current_group = line.partition(":")[2].strip()
            continue
        if line.startswith("# subgroup:"):
            current_subgroup = line.partition(":")[2].strip()
            continue

        match = EMOJI_LINE.match(line)
        if match is None or match.group(2).strip() != "fully-qualified":
            continue

        code_points, _, emoji, emoji_version, unicode_name = match.groups()
        expected_emoji = "".join(chr(int(code_point, 16)) for code_point in code_points.split())
        if emoji != expected_emoji:
            raise ValueError(f"emoji-test character mismatch for {code_points}")

        records.append(
            EmojiRecord(
                emoji=emoji,
                unicode_name=unicode_name.strip(),
                emoji_version=emoji_version,
                group=current_group,
                subgroup=current_subgroup,
            )
        )

    if "unicode_emoji_version" not in metadata or not records:
        raise ValueError("emoji-test data is missing its version or fully-qualified emoji")
    if len({record.emoji for record in records}) != len(records):
        raise ValueError("emoji-test data contains duplicate fully-qualified emoji")
    return metadata, records


def parse_annotations(*xml_documents: str) -> dict[str, Annotation]:
    names: dict[str, str] = {}
    keywords: dict[str, set[str]] = defaultdict(set)

    for xml_document in xml_documents:
        root = ElementTree.fromstring(xml_document)
        for element in root.iter("annotation"):
            emoji = element.attrib.get("cp")
            text = element.text
            if not emoji or not text:
                continue
            if element.attrib.get("type") == "tts":
                names[emoji] = text.strip()
            else:
                keywords[emoji].update(
                    keyword.strip() for keyword in text.split("|") if keyword.strip()
                )

    return {
        emoji: Annotation(name=names.get(emoji), keywords=frozenset(keywords.get(emoji, set())))
        for emoji in names.keys() | keywords.keys()
    }


def extract_legacy_aliases(archive_path: Path) -> dict[str, list[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    with zipfile.ZipFile(archive_path) as archive:
        for filename in archive.namelist():
            if not filename.endswith(".json"):
                continue
            payload = json.loads(archive.read(filename))
            snippet = payload.get("alfredsnippet")
            if not isinstance(snippet, dict):
                continue
            emoji = snippet.get("snippet")
            keyword = snippet.get("keyword")
            if not isinstance(emoji, str) or not isinstance(keyword, str):
                continue
            alias = normalize_legacy_alias(keyword)
            if alias:
                aliases[emoji].add(alias)
    return {emoji: sorted(values) for emoji, values in sorted(aliases.items())}


def load_preferred_aliases(path: Path) -> dict[str, str]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("aliases"), dict):
        raise ValueError(f"{path} does not contain an aliases object")

    aliases: dict[str, str] = {}
    for emoji, alias in payload["aliases"].items():
        if isinstance(emoji, str) and isinstance(alias, str):
            normalized_alias = normalize_legacy_alias(alias)
            if not normalized_alias:
                raise ValueError(f"{path} contains an empty preferred alias for {emoji}")
            aliases[emoji] = normalized_alias
    return aliases


def _annotation_for(
    emoji: str, annotations: dict[str, Annotation], normalized: dict[str, Annotation]
) -> Annotation:
    return annotations.get(
        emoji, normalized.get(emoji.replace("\ufe0f", ""), Annotation(None, frozenset()))
    )


def compile_catalog(
    records: list[EmojiRecord],
    annotations: dict[str, Annotation],
    legacy_aliases: dict[str, list[str]],
    preferred_aliases: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    preferred_aliases = preferred_aliases or {}
    normalized_annotations = {
        emoji.replace("\ufe0f", ""): annotation for emoji, annotation in annotations.items()
    }

    prepared: list[dict[str, object]] = []
    canonical_owners: dict[str, str] = {}
    requested_legacy: dict[str, set[str]] = defaultdict(set)
    candidate_owners: dict[str, set[str]] = defaultdict(set)

    for record in records:
        annotation = _annotation_for(record.emoji, annotations, normalized_annotations)
        name = annotation.name or record.unicode_name
        canonical_aliases = {slugify(name), slugify(record.unicode_name)}
        canonical_aliases.discard("")

        for alias in canonical_aliases:
            owner = canonical_owners.setdefault(alias, record.emoji)
            if owner != record.emoji:
                raise ValueError(f"canonical alias {alias!r} belongs to multiple emoji")

        legacy_values = legacy_aliases.get(record.emoji, [])
        if not legacy_values:
            legacy_values = legacy_aliases.get(record.emoji.replace("\ufe0f", ""), [])

        normalized_legacy = {
            alias for value in legacy_values if (alias := normalize_legacy_alias(value))
        }
        for alias in normalized_legacy:
            requested_legacy[alias].add(record.emoji)

        phrases = {name, record.unicode_name, *annotation.keywords}
        for phrase in phrases:
            phrase_alias = slugify(phrase)
            if phrase_alias:
                candidate_owners[phrase_alias].add(record.emoji)
                for token in phrase_alias.split("_"):
                    if len(token) >= 3:
                        candidate_owners[token].add(record.emoji)

        prepared.append(
            {
                "emoji": record.emoji,
                "name": name,
                "unicode_name": record.unicode_name,
                "emoji_version": record.emoji_version,
                "group": record.group,
                "subgroup": record.subgroup,
                "keywords": sorted(annotation.keywords),
                "_canonical_aliases": canonical_aliases,
            }
        )

    reserved_aliases = dict(canonical_owners)
    accepted_legacy: dict[str, set[str]] = defaultdict(set)
    for alias, owners in requested_legacy.items():
        if len(owners) != 1:
            continue
        owner = next(iter(owners))
        if alias in reserved_aliases and reserved_aliases[alias] != owner:
            continue
        reserved_aliases[alias] = owner
        accepted_legacy[owner].add(alias)

    accepted_candidates: dict[str, set[str]] = defaultdict(set)
    for alias, owners in candidate_owners.items():
        if len(owners) != 1:
            continue
        owner = next(iter(owners))
        if alias in reserved_aliases and reserved_aliases[alias] != owner:
            continue
        reserved_aliases[alias] = owner
        accepted_candidates[owner].add(alias)

    catalog: list[dict[str, object]] = []
    for item in prepared:
        emoji = str(item["emoji"])
        canonical_aliases = cast(set[str], item.pop("_canonical_aliases"))
        aliases = canonical_aliases.copy()
        aliases.update(accepted_legacy[emoji])
        aliases.update(accepted_candidates[emoji])
        canonical_alias = slugify(str(item["name"]))
        preferred_alias = preferred_aliases.get(emoji)
        if preferred_alias:
            if preferred_alias not in aliases:
                raise ValueError(f"preferred alias {preferred_alias!r} is unavailable for {emoji}")
            primary_alias = preferred_alias
        else:
            primary_alias = canonical_alias
        item["primary_alias"] = primary_alias
        item["aliases"] = [primary_alias, *sorted(aliases - {primary_alias})]
        catalog.append(item)

    unused_preferences = set(preferred_aliases) - {str(item["emoji"]) for item in catalog}
    if unused_preferences:
        raise ValueError(f"preferred aliases reference missing emoji: {sorted(unused_preferences)}")
    return catalog
