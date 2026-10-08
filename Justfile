# List available recipes by group
default:
    @just --list

# Build all Alfred packages in dist/ from vendored data
[group('build')]
build:
    python3 scripts/build.py

# Download configured Unicode data and rebuild all packages in dist/
[group('build')]
update:
    python3 scripts/update_emoji_data.py
    python3 scripts/build.py

# Run the test suite
[group('dev')]
test:
    uv run pytest

# Generate a Markdown report for trigger and alias review
[group('dev')]
alias-report:
    python3 scripts/alias_report.py

# Run formatting, linting, type checks, and tests
[group('dev')]
check:
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy .
    uv run pytest

# Tag the project and publish all Alfred packages on GitHub
[group('release')]
release: check build
    python3 scripts/release.py
