# Release checklist

## Automated checks

1. Run `just check`.
2. Run `just build`.
3. Confirm both generated packages exist under `dist/`.
4. Run `actionlint .github/workflows/*.yml`.
5. Run `just alias-report` and review preferred overrides and shared search terms.

## Alfred 5 workflow

1. Open `Emoji Pack.alfredworkflow` and approve the import.
2. Run `emoji rain` and confirm the title is `☔ - :umbrella_rain:`.
3. Search for `hotel`, `service`, and `sound`.
4. Confirm result subtitles omit the primary alias and show at most 3 alternatives.
5. Press Return on a result and confirm Alfred pastes the emoji.
6. Run `emoji-install` and confirm Alfred opens the bundled snippet collection.

## Alfred 5 snippets

1. Remove the previously imported Emoji Pack collection.
2. Approve the snippet import opened by `emoji-install`.
3. Confirm the collection icon appears.
4. Expand `:bell:`, `:bellhop:`, `:joy:`, `:+1:`, `:-1:`, and `:umbrella_rain:`.
5. Confirm each emoji appears once.
6. Export the imported collection and inspect the ZIP if Alfred changes its export format.

The generated archive uses the flat JSON snippet layout already accepted by
Alfred, plus `icon.png`. Do not add collection metadata unless an Alfred 5
import or export test shows that it is required.

## Publication

1. Set the version in `pyproject.toml`.
2. Rebuild and commit both packages.
3. Push the release commit.
4. Run `just release`.
5. Download the release assets and verify `SHA256SUMS`.
6. Repeat both Alfred 5 checks using the downloaded packages.
