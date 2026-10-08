from __future__ import annotations

import json
from pathlib import Path

import pytest
from project_files import project_version
from release import (
    ARTIFACT_PATHS,
    release_arguments,
    remote_tag_commit,
    sha256_file,
    validate_release_state,
    write_release_files,
)


def test_project_version_reads_semantic_version(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nversion = "2.1.0"\n', encoding="utf-8")

    assert project_version(project) == "2.1.0"


def test_project_version_rejects_invalid_version(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nversion = "next"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="semantic project version"):
        project_version(project)


def test_release_state_requires_clean_pushed_commit(tmp_path: Path) -> None:
    artifact = tmp_path / "Emoji Pack.alfredsnippets"
    artifact.write_bytes(b"archive")

    with pytest.raises(ValueError, match="worktree is dirty"):
        validate_release_state(" M README.md", "abc", "abc", [artifact])

    with pytest.raises(ValueError, match="not pushed"):
        validate_release_state("", "abc", "def", [artifact])


def test_release_includes_all_generated_packages() -> None:
    assert [path.name for path in ARTIFACT_PATHS] == [
        "Emoji Pack.alfredworkflow",
        "Emoji Pack.alfredsnippets",
        "Emoji Aliases.alfredsnippets",
    ]


def test_release_state_requires_built_archive(tmp_path: Path) -> None:
    artifact = tmp_path / "Emoji Pack.alfredsnippets"

    with pytest.raises(ValueError, match="artifact is missing"):
        validate_release_state("", "abc", "abc", [artifact])


def test_release_arguments_upload_packages_and_verify_tag(tmp_path: Path) -> None:
    artifacts = [
        tmp_path / "Emoji Pack.alfredworkflow",
        tmp_path / "Emoji Pack.alfredsnippets",
    ]
    checksum = tmp_path / "SHA256SUMS"
    metadata = tmp_path / "release.json"
    notes = tmp_path / "release-notes.md"

    arguments = release_arguments("v2.0.0", artifacts, checksum, metadata, notes)

    assert arguments[:4] == ["gh", "release", "create", "v2.0.0"]
    assert all(str(artifact) in arguments for artifact in artifacts)
    assert str(checksum) in arguments
    assert str(metadata) in arguments
    assert "--generate-notes" in arguments
    assert arguments[arguments.index("--notes-file") + 1] == str(notes)
    assert "--verify-tag" in arguments


def test_remote_tag_commit_prefers_peeled_annotated_commit() -> None:
    output = """\
tag-object\trefs/tags/v2.0.0
commit-sha\trefs/tags/v2.0.0^{}
"""

    assert remote_tag_commit(output, "v2.0.0") == "commit-sha"
    assert remote_tag_commit("", "v2.0.0") is None


def test_release_files_include_checksums_and_catalog_metadata(tmp_path: Path) -> None:
    workflow = tmp_path / "Emoji Pack.alfredworkflow"
    workflow.write_bytes(b"workflow")
    snippets = tmp_path / "Emoji Pack.alfredsnippets"
    snippets.write_bytes(b"snippets")
    artifacts = [workflow, snippets]
    catalog = tmp_path / "emoji.json"
    catalog.write_text(
        json.dumps(
            {
                "unicode_emoji_version": "18.0",
                "emoji_count": 1923,
                "skin_tone_variants_included": False,
                "cldr_ref": "abc123",
                "source_sha256": {"emoji_test": "source-hash"},
            }
        ),
        encoding="utf-8",
    )

    checksum, metadata, notes = write_release_files(
        tmp_path,
        "2.0.0",
        catalog,
        artifacts,
    )

    expected_checksums = "".join(
        f"{sha256_file(artifact)}  {artifact.name}\n" for artifact in artifacts
    )
    assert checksum.read_text(encoding="utf-8") == expected_checksums
    release_metadata = json.loads(metadata.read_text(encoding="utf-8"))
    assert release_metadata["artifacts"] == [
        {"name": artifact.name, "sha256": sha256_file(artifact)} for artifact in artifacts
    ]
    assert release_metadata["emoji_count"] == 1923
    assert "Unicode Emoji 18.0" in notes.read_text(encoding="utf-8")
