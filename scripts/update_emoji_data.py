from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from emoji_data import (
    compile_catalog,
    extract_legacy_aliases,
    has_skin_tone_modifier,
    load_legacy_aliases,
    load_preferred_aliases,
    parse_annotations,
    parse_emoji_test,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMOJI_URL = "https://www.unicode.org/Public/emoji/latest/emoji-test.txt"
CLDR_COMMIT_API = "https://api.github.com/repos/unicode-org/cldr/commits/main"
CLDR_RAW_URL = "https://raw.githubusercontent.com/unicode-org/cldr/{ref}/{path}"


@dataclass(frozen=True)
class PackConfig:
    include_skin_tones: bool


def load_config(path: Path) -> PackConfig:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    emoji_config = payload.get("emoji")
    if not isinstance(emoji_config, dict):
        raise ValueError(f"{path} does not contain an emoji table")
    include_skin_tones = emoji_config.get("include_skin_tones")
    if not isinstance(include_skin_tones, bool):
        raise ValueError(f"{path} must define emoji.include_skin_tones as true or false")
    return PackConfig(include_skin_tones=include_skin_tones)


def resolve_include_skin_tones(config: PackConfig, override: bool | None) -> bool:
    if override is not None:
        return override
    return config.include_skin_tones


def request_headers(url: str, environment: Mapping[str, str]) -> dict[str, str]:
    headers = {"User-Agent": "alfred-emoji-pack/2.0"}
    token = environment.get("GITHUB_TOKEN") or environment.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=request_headers(url, os.environ))
    with urllib.request.urlopen(request, timeout=60) as response:
        return cast(bytes, response.read())


def download_text(url: str) -> str:
    return download_bytes(url).decode("utf-8")


def resolve_cldr_ref(requested_ref: str) -> str:
    if requested_ref != "main":
        return requested_ref
    payload: Any = json.loads(download_text(CLDR_COMMIT_API))
    sha = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(sha, str) or len(sha) != 40:
        raise ValueError("GitHub did not return a valid CLDR commit SHA")
    return sha


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the vendored Unicode emoji catalog")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "emoji-pack.toml",
    )
    parser.add_argument(
        "--include-skin-tones",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override emoji.include_skin_tones from the configuration file",
    )
    parser.add_argument("--emoji-url", default=DEFAULT_EMOJI_URL)
    parser.add_argument("--cldr-ref", default="main")
    parser.add_argument(
        "--legacy-archive",
        type=Path,
        help="Extract compatibility aliases from an existing .alfredsnippets archive",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "emoji.json",
    )
    parser.add_argument(
        "--legacy-output",
        type=Path,
        default=ROOT / "data" / "legacy_aliases.json",
    )
    parser.add_argument(
        "--preferred-aliases",
        type=Path,
        default=ROOT / "data" / "preferred_aliases.json",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    include_skin_tones = resolve_include_skin_tones(config, args.include_skin_tones)
    cldr_ref = resolve_cldr_ref(args.cldr_ref)
    annotation_url = CLDR_RAW_URL.format(ref=cldr_ref, path="common/annotations/en.xml")
    derived_url = CLDR_RAW_URL.format(ref=cldr_ref, path="common/annotationsDerived/en.xml")

    emoji_test_bytes = download_bytes(args.emoji_url)
    annotations_bytes = download_bytes(annotation_url)
    derived_annotations_bytes = download_bytes(derived_url)
    emoji_test = emoji_test_bytes.decode("utf-8")
    annotations_xml = annotations_bytes.decode("utf-8")
    derived_annotations_xml = derived_annotations_bytes.decode("utf-8")

    metadata, all_records = parse_emoji_test(emoji_test)
    records = [
        record
        for record in all_records
        if include_skin_tones or not has_skin_tone_modifier(record.emoji)
    ]
    annotations = parse_annotations(annotations_xml, derived_annotations_xml)

    if args.legacy_archive:
        legacy_aliases = extract_legacy_aliases(args.legacy_archive)
        args.legacy_output.parent.mkdir(parents=True, exist_ok=True)
        args.legacy_output.write_text(
            json.dumps(
                {
                    "source": str(args.legacy_archive),
                    "aliases": legacy_aliases,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        legacy_aliases = load_legacy_aliases(args.legacy_output)

    preferred_aliases = load_preferred_aliases(args.preferred_aliases)
    catalog = compile_catalog(records, annotations, legacy_aliases, preferred_aliases)
    payload = {
        "schema_version": 1,
        **metadata,
        "cldr_ref": cldr_ref,
        "skin_tone_variants_included": include_skin_tones,
        "sources": {
            "emoji_test": args.emoji_url,
            "cldr_annotations": annotation_url,
            "cldr_annotations_derived": derived_url,
        },
        "source_sha256": {
            "emoji_test": hashlib.sha256(emoji_test_bytes).hexdigest(),
            "cldr_annotations": hashlib.sha256(annotations_bytes).hexdigest(),
            "cldr_annotations_derived": hashlib.sha256(derived_annotations_bytes).hexdigest(),
        },
        "emoji_count": len(catalog),
        "emojis": catalog,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    try:
        run(parse_args())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
