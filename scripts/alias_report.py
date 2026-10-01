from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "emoji.json"
PREFERRED_ALIASES_PATH = ROOT / "data" / "preferred_aliases.json"
OUTPUT_PATH = ROOT / "dist" / "alias-report.md"


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def load_json(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def render_report(catalog: dict[str, Any], preferred_aliases: dict[str, Any]) -> str:
    entries = catalog.get("emojis")
    overrides = preferred_aliases.get("aliases")
    if not isinstance(entries, list) or not isinstance(overrides, dict):
        raise ValueError("catalog and preferred aliases have invalid shapes")

    search_term_owners: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("catalog entries must be objects")
        emoji = str(entry["emoji"])
        primary_alias = str(entry["primary_alias"])
        for field in ("aliases", "keywords"):
            values = entry.get(field, [])
            if not isinstance(values, list):
                raise ValueError(f"{emoji} has invalid {field}")
            for value in values:
                term = str(value)
                if term != primary_alias:
                    search_term_owners[term].add(emoji)

    collisions = {
        term: sorted(owners) for term, owners in search_term_owners.items() if len(owners) > 1
    }
    lines = [
        "# Alias report",
        "",
        f"- Emoji: {len(entries)}",
        f"- Preferred overrides: {len(overrides)}",
        f"- Shared search terms: {len(collisions)}",
        "",
        "## Preferred overrides",
        "",
        "| Emoji | Trigger |",
        "|---|---|",
    ]
    for emoji, alias in sorted(overrides.items(), key=lambda item: str(item[1])):
        lines.append(f"| {escape_cell(emoji)} | `:{escape_cell(alias)}:` |")

    lines.extend(
        [
            "",
            "## Shared search terms",
            "",
            "| Term | Emoji |",
            "|---|---|",
        ]
    )
    for term, owners in sorted(collisions.items()):
        lines.append(f"| `{escape_cell(term)}` | {' '.join(owners)} |")

    lines.extend(
        [
            "",
            "## Primary triggers",
            "",
            "| Emoji | Name | Trigger | Other aliases |",
            "|---|---|---|---|",
        ]
    )
    for entry in entries:
        primary_alias = str(entry["primary_alias"])
        aliases = [str(alias) for alias in entry.get("aliases", []) if str(alias) != primary_alias]
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(entry["emoji"]),
                    escape_cell(entry["name"]),
                    f"`:{escape_cell(primary_alias)}:`",
                    ", ".join(f"`{escape_cell(alias)}`" for alias in aliases),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an emoji alias review report")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--preferred-aliases", type=Path, default=PREFERRED_ALIASES_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        report = render_report(
            load_json(args.catalog),
            load_json(args.preferred_aliases),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
