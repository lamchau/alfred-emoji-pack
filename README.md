# Emoji Pack for Alfred 5

[![CI](https://github.com/lamchau/alfred-emoji-pack/actions/workflows/ci.yml/badge.svg)](https://github.com/lamchau/alfred-emoji-pack/actions/workflows/ci.yml)

Search current Unicode emoji in Alfred or expand colon triggers while typing.
The release includes an Alfred workflow and a standalone snippet collection,
both generated from the same catalog.

## Features

| Feature | Behavior |
|---|---|
| Alfred browser | Search names, aliases, and CLDR keywords with `emoji <query>` |
| Direct paste | Press Return to paste the selected emoji into the active application |
| Copy actions | Command-Return copies the emoji; Option-Return copies its preferred trigger |
| Text expansion | Type a preferred colon trigger such as `:bellhop:` |
| Alias display | Show the preferred trigger in the title and configured alternatives below it |
| Readable rows | Fall back to the emoji name when a result has no alternate alias |
| Learned ranking | Let Alfred promote frequently and recently selected emoji |
| Workflow settings | Configure the search keyword and show 0–5 alternate aliases |
| Current data | Build from official Unicode Emoji and English CLDR data |
| Default tones | Omit skin-tone sequences unless enabled in configuration |
| Offline use | Require no Python, Node.js, JavaScript, or network access after installation |
| Repeatable builds | Produce stable IDs, ZIP timestamps, and package contents |

## Requirements

- macOS
- Alfred 5 with the Powerpack

## Install

### Workflow and snippets

1. Download `Emoji Pack.alfredworkflow` from the latest release.
2. Open the file and approve the Alfred workflow import.
3. Run `emoji-install` in Alfred.
4. Approve the snippet collection import.

Remove an older Emoji Pack snippet collection before step 3 to avoid duplicate
triggers.

### Snippets only

Download and open `Emoji Pack.alfredsnippets` if you only want colon-trigger
expansion.

`Emoji Aliases.alfredsnippets` is optional. It adds accepted legacy expansion
triggers and creates duplicate rows in Alfred's snippet browser.

## Use

Type `emoji` followed by a search term:

```text
emoji rain
```

Alfred displays the preferred expansion as the result title and alternate
expansions as the subtitle:

```text
☔ - :umbrella_rain:
:umbrella_with_rain_drops:
```

Press Return to paste the emoji. Alfred searches the full Unicode name, CLDR
name, aliases, keywords, group, and subgroup even though the result only shows
3 alternate aliases.

Hold Command while pressing Return to copy the emoji without pasting it. Hold
Option while pressing Return to copy the preferred colon trigger.

Searching covers the Unicode group and subgroup too, so `emoji smileys` or
`emoji cat-face` narrows to those sections without a separate browse mode.

Alfred learns from the stable ID attached to every emoji. Open the browser
without a query to see frequently and recently selected emoji rise in the
results. There is no separate favorites database to maintain.

The imported snippet collection handles expansion in any application:

```text
:umbrella_rain:  ->  ☔
:bellhop:        ->  🛎️
:joy:            ->  😂
```

## Aliases

Alfred allows 1 keyword per snippet. The snippet collection therefore contains
1 record and 1 preferred trigger per emoji. The workflow browser searches every
accepted alias without adding duplicate snippet results.

Primary triggers normally use the English CLDR name. Reviewed exceptions live
in `data/preferred_aliases.json`. Generate `dist/alias-report.md` when reviewing
trigger choices:

```fish
just alias-report
```

Alias requests can be submitted with the repository issue form.

Run `emoji-install-aliases` to import the optional legacy aliases. Run
`emoji-refresh` after installing an updated workflow to reopen the current
preferred-trigger collection.

## Workflow settings

Open Alfred's workflow configuration to change:

- the browser keyword, which defaults to `emoji`
- the number of alternate aliases shown below each result, from 0 through 5

The workflow contains a pre-generated result file for each alias-count setting,
so changing this option adds no runtime dependency. Alfred caches the parsed
results for a day, so repeated searches avoid re-reading the catalog.

## Emoji data

`data/emoji.json` is the generated source of truth. It records:

- the Unicode Emoji version and data date
- the exact CLDR commit
- source URLs and SHA-256 hashes
- whether skin-tone variants are included
- names, aliases, keywords, groups, and subgroups

Refresh the catalog and both Alfred packages:

```fish
just update
```

The update command needs network access. Normal builds are offline.

## Skin tones

Skin-tone sequences are excluded by default because Alfred and macOS provide
native variant selection. Enable generated variants in `emoji-pack.toml`:

```toml
[emoji]
include_skin_tones = true
```

Then refresh the catalog:

```fish
just update
```

For a temporary override:

```fish
python3 scripts/update_emoji_data.py --include-skin-tones
just build
```

Use `--no-include-skin-tones` to force the default-tone catalog.

## Development

The generator uses Python 3.12 or newer and the standard library. Development
tools are locked with `uv`.

```fish
uv sync
just
```

The default `just` recipe lists the available commands.

| Recipe | Purpose |
|---|---|
| `just build` | Build all Alfred packages from vendored data |
| `just update` | Download current Unicode and CLDR data, then rebuild |
| `just test` | Run the test suite |
| `just check` | Check formatting, lint, types, and tests |
| `just alias-report` | Generate the alias review report |
| `just release` | Validate, tag, and publish a GitHub release |

The equivalent build command without `just` is:

```fish
python3 scripts/build.py
```

Generated packages are written to the ignored `dist/` directory:

```text
dist/Emoji Pack.alfredworkflow
dist/Emoji Pack.alfredsnippets
dist/Emoji Aliases.alfredsnippets
```

Release assets are generated from this directory and are not committed.

## Automation

CI runs the locked checks on Python 3.12 and 3.14, rebuilds all packages, tests
their ZIP structure, confirms a second build is byte-identical, and rejects
generated-file drift.

A scheduled workflow runs on the 1st day of each month. It updates Unicode and
CLDR data, rebuilds all packages, bumps the project minor version, and opens or
updates `automation/update-emoji-data` when tracked outputs change. Merging that
pull request leaves the repository ready for `just release`. Repository settings
must allow GitHub Actions to create pull requests.

Dependabot checks the Python development tools and pinned GitHub Actions each
month.

## Release

1. Set the version in `pyproject.toml`. The monthly data update already bumps
   the minor version, so a data-only release can skip this step.
2. Run `just check` and `just build`.
3. Commit and push the release state.
4. Authenticate with `gh auth login`.
5. Run `just release`.

The release command refuses a dirty worktree, an unpushed commit, an existing
tag, or an existing GitHub release. It publishes:

- `Emoji Pack.alfredworkflow`
- `Emoji Pack.alfredsnippets`
- `Emoji Aliases.alfredsnippets`
- `SHA256SUMS`
- `release.json`

Use `docs/release-checklist.md` for the Alfred 5 import and paste checks.

## Project history

This project was inspired by
[Joel Califa's original Alfred Emoji Pack](https://github.com/califa/alfred-emoji-pack).
The Python data pipeline, Alfred 5 workflow, package generator, tests, release
tooling, and maintenance automation were rewritten for the current project.
Legacy trigger names are retained where they remain clear and collision-free.

## License and data

Project code is available under the [ISC License](LICENSE).

Emoji data come from the
[Unicode emoji data files](https://www.unicode.org/Public/emoji/latest/) and
[Unicode CLDR](https://github.com/unicode-org/cldr). Unicode data use is subject
to the [Unicode Terms of Use](https://www.unicode.org/terms_of_use.html).
