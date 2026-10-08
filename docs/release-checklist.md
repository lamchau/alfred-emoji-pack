# Release checklist

## Automated checks

1. Run `just check`.
2. Run `just build`.
3. Confirm all 3 generated packages exist under `dist/`.
4. Run `just alias-report` and review preferred overrides and shared search terms.

CI already runs `actionlint` and verifies that a second build is byte-identical,
so neither needs to be repeated by hand.

## Alfred 5 workflow

1. Open `Emoji Pack.alfredworkflow` and approve the import.
2. Run `emoji rain` and confirm the title is `☔ - :umbrella_rain:`.
3. Search for `hotel`, `service`, and `sound`.
4. Confirm result subtitles omit the primary alias and show at most 3
   alternatives, falling back to the emoji name when there is no alternative.
5. Press Return on a result and confirm Alfred pastes the emoji.
6. Confirm Command-Return copies the emoji without pasting.
7. Confirm Option-Return copies the preferred colon trigger.
8. Confirm `emoji smileys` narrows to that Unicode group and every row is a
   selectable emoji.
9. Change the keyword and alias count in workflow configuration.
10. Select several emoji repeatedly, reopen an empty search, and confirm Alfred learns the order.
11. Run `emoji-install` and confirm Alfred opens the bundled snippet collection.

## Alfred 5 snippets

1. Remove the previously imported Emoji Pack collection.
2. Approve the snippet import opened by `emoji-install`.
3. Confirm the collection icon appears.
4. Expand `:bell:`, `:bellhop:`, `:joy:`, `:+1:`, `:-1:`, and `:umbrella_rain:`.
5. Confirm each emoji appears once.
6. Run `emoji-refresh` and approve the preferred-trigger reimport.
7. Run `emoji-install-aliases` and approve the optional legacy collection.
8. Confirm a legacy alias expands and duplicate browser rows are expected.
9. Export the imported collection and inspect the ZIP if Alfred changes its export format.

The generated archive uses the flat JSON snippet layout already accepted by
Alfred, plus `icon.png`. Do not add collection metadata unless an Alfred 5
import or export test shows that it is required.

## Publication

1. Confirm the version in `pyproject.toml`. The monthly data update already
   bumps the minor version, so a data-only release needs no edit.
2. Rebuild all packages.
3. Push the release commit.
4. Run `just release`.
5. Download the release assets and verify `SHA256SUMS`.
6. Repeat both Alfred 5 checks using the downloaded packages.
