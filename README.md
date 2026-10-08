# Emoji Pack for Alfred 5

[![CI](https://github.com/lamchau/alfred-emoji-pack/actions/workflows/ci.yml/badge.svg)](https://github.com/lamchau/alfred-emoji-pack/actions/workflows/ci.yml)

Find any emoji in Alfred, or type `:joy:` anywhere to get 😂.

Generated from official Unicode and CLDR releases and refreshed automatically
each month, so new emoji show up without anyone editing a list. No Python,
Node, or network access needed once installed.

## Install

Requires macOS and Alfred 5 with the Powerpack.

1. Download `Emoji Pack.alfredworkflow` from the [latest release](https://github.com/lamchau/alfred-emoji-pack/releases/latest).
2. Open it and approve the import.
3. Run `emoji-install` in Alfred to add the typing shortcuts.

> Already have an older Emoji Pack snippet collection? Remove it before step 3,
> or you will get duplicate triggers.

Want only the typing shortcuts, without the Alfred browser? Download and open
`Emoji Pack.alfredsnippets` instead.

## Search

Type `emoji` and what you're looking for:

```text
emoji rain
```

```text
☔ - :umbrella_rain:
:umbrella_with_rain_drops:
```

| Key | Action |
|---|---|
| <kbd>Return</kbd> | Paste the emoji |
| <kbd>⌘</kbd> <kbd>Return</kbd> | Copy the emoji |
| <kbd>⌥</kbd> <kbd>Return</kbd> | Copy its colon trigger |

Search matches names, aliases, keywords, and Unicode categories — so `emoji
smileys` or `emoji cat-face` narrows to a whole section. The subtitle shows a
few alternate triggers, but every alias is searchable.

Open `emoji` with no query to see what you use most. Alfred learns your picks
automatically; there is no favorites list to maintain.

## Type

After running `emoji-install`, colon triggers expand in any app:

```text
:umbrella_rain:  →  ☔
:bellhop:        →  🛎️
:joy:            →  😂
```

Each emoji gets exactly one trigger, since Alfred allows one keyword per
snippet. Triggers come from the English CLDR name, with
[reviewed exceptions](data/preferred_aliases.json) where that name was awkward.

Two optional commands:

- `emoji-install-aliases` — adds legacy triggers from older emoji packs
- `emoji-refresh` — re-imports triggers after installing a workflow update

Missing a trigger you expected? [Open an alias request](https://github.com/lamchau/alfred-emoji-pack/issues/new/choose).

## Configure

In Alfred's workflow settings you can change the search keyword (default
`emoji`) and how many alternate triggers appear under each result (0–5).

Skin-tone variants are excluded by default, since macOS already offers them
natively. To include them, set `include_skin_tones = true` in `emoji-pack.toml`
and run `just update`.

## Development

<details>
<summary>Building, testing, and releasing</summary>

Python 3.12+ and the standard library. Development tools are locked with `uv`.

```fish
uv sync
just        # lists every recipe
```

| Recipe | Purpose |
|---|---|
| `just build` | Build the Alfred packages from vendored data |
| `just update` | Download current Unicode and CLDR data, then rebuild |
| `just test` | Run the test suite |
| `just check` | Format, lint, type-check, and test |
| `just alias-report` | Generate the alias review report |
| `just release` | Validate, tag, and publish a GitHub release |

Packages are written to the ignored `dist/` directory and are not committed.
Builds are reproducible: stable IDs and fixed ZIP timestamps mean the same
input always produces byte-identical archives.

### Emoji data

`data/emoji.json` is the generated source of truth. It records the Unicode
Emoji version, the exact CLDR commit, source URLs with SHA-256 hashes, and
every name, alias, keyword, and category.

`just update` refreshes it from upstream and needs network access. Every other
command works offline.

### Releasing

1. Set the version in `pyproject.toml` — the monthly data update already bumps
   the minor version, so a data-only release can skip this.
2. Run `just check` and `just build`.
3. Commit and push.
4. Run `just release`.

It refuses to publish from a dirty worktree, an unpushed commit, or over an
existing tag or release. Use `docs/release-checklist.md` for the manual Alfred
import checks.

### Automation

CI runs the locked checks on Python 3.12 and 3.14, rebuilds the packages,
verifies a second build is byte-identical, and rejects generated-file drift.

A scheduled job refreshes Unicode and CLDR data on the 1st of each month,
bumps the minor version, and opens a pull request when anything changed.
Merging it leaves the repository ready for `just release`. Dependabot checks
development tools and pinned actions monthly.

</details>

## Credits

Forked from Joel Califa's
[Alfred Emoji Snippet Pack](https://joelcalifa.com/blog/alfred-emoji-snippet-pack/),
which has not been updated since 2021 and predates Alfred 5.

This version replaces the hand-maintained snippet list with a pipeline that
generates everything from official Unicode and CLDR releases, and keeps it
current automatically:

- the catalog is regenerated from upstream data rather than edited by hand
- a scheduled job refreshes it monthly and opens a pull request
- builds are reproducible and verified in CI
- the Alfred 5 workflow, tests, and release tooling were written from scratch

Legacy trigger names are kept wherever they are still clear and unambiguous,
so existing muscle memory keeps working.

Because nothing of the original source survived the rewrite, this repository
starts from a fresh commit history rather than the upstream one. It is a fork
in lineage only — there is no shared git ancestry with
[califa/alfred-emoji-pack](https://github.com/califa/alfred-emoji-pack).

Code is [ISC licensed](LICENSE). Emoji data comes from the
[Unicode emoji files](https://www.unicode.org/Public/emoji/latest/) and
[CLDR](https://github.com/unicode-org/cldr), subject to the
[Unicode Terms of Use](https://www.unicode.org/terms_of_use.html).
