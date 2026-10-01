from __future__ import annotations

from alias_report import render_report


def test_alias_report_lists_overrides_triggers_and_shared_terms() -> None:
    catalog = {
        "emojis": [
            {
                "emoji": "🔔",
                "name": "bell",
                "primary_alias": "bell",
                "aliases": ["bell"],
                "keywords": ["sound"],
            },
            {
                "emoji": "🛎️",
                "name": "bellhop bell",
                "primary_alias": "bellhop",
                "aliases": ["bellhop", "bellhop_bell"],
                "keywords": ["hotel", "sound"],
            },
        ]
    }
    preferred_aliases = {"aliases": {"🛎️": "bellhop"}}

    report = render_report(catalog, preferred_aliases)

    assert "Preferred overrides: 1" in report
    assert "Shared search terms: 1" in report
    assert "| `sound` | 🔔 🛎️ |" in report
    assert "| 🛎️ | bellhop bell | `:bellhop:` | `bellhop_bell` |" in report
