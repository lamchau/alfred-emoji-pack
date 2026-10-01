from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_PATH = ROOT / "pyproject.toml"
CATALOG_PATH = ROOT / "data" / "emoji.json"
ARTIFACT_PATHS = [
    ROOT / "dist" / "Emoji Pack.alfredworkflow",
    ROOT / "dist" / "Emoji Pack.alfredsnippets",
    ROOT / "dist" / "Emoji Aliases.alfredsnippets",
]
SEMANTIC_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def project_version(project_path: Path) -> str:
    payload = tomllib.loads(project_path.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not SEMANTIC_VERSION.fullmatch(version):
        raise ValueError(f"{project_path} does not contain a semantic project version")
    return version


def command_output(arguments: list[str], root: Path) -> str:
    result = subprocess.run(
        arguments,
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def optional_command(arguments: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )


def validate_release_state(
    status: str,
    head_commit: str,
    upstream_commit: str,
    artifact_paths: list[Path],
) -> None:
    if status:
        raise ValueError("the worktree is dirty; commit the rebuilt archive before releasing")
    if head_commit != upstream_commit:
        raise ValueError("HEAD is not pushed to its upstream branch")
    missing_artifacts = [path for path in artifact_paths if not path.is_file()]
    if missing_artifacts:
        raise ValueError(f"release artifact is missing: {missing_artifacts[0]}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_release_files(
    output_directory: Path,
    version: str,
    catalog_path: Path,
    artifact_paths: list[Path],
) -> tuple[Path, Path, Path]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    artifacts = [
        {"name": artifact_path.name, "sha256": sha256_file(artifact_path)}
        for artifact_path in artifact_paths
    ]
    metadata = {
        "version": version,
        "artifacts": artifacts,
        "unicode_emoji_version": catalog["unicode_emoji_version"],
        "emoji_count": catalog["emoji_count"],
        "skin_tone_variants_included": catalog["skin_tone_variants_included"],
        "cldr_ref": catalog["cldr_ref"],
        "source_sha256": catalog["source_sha256"],
    }

    checksum_path = output_directory / "SHA256SUMS"
    checksum_path.write_text(
        "".join(f"{artifact['sha256']}  {artifact['name']}\n" for artifact in artifacts),
        encoding="utf-8",
    )
    metadata_path = output_directory / "release.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    notes_path = output_directory / "release-notes.md"
    skin_tones = "included" if metadata["skin_tone_variants_included"] else "omitted"
    notes_path.write_text(
        "\n".join(
            [
                f"Unicode Emoji {metadata['unicode_emoji_version']}",
                "",
                f"- Emoji: {metadata['emoji_count']}",
                f"- Skin-tone variants: {skin_tones}",
                f"- CLDR commit: `{metadata['cldr_ref']}`",
                *[
                    f"- {artifact['name']} SHA-256: `{artifact['sha256']}`"
                    for artifact in artifacts
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return checksum_path, metadata_path, notes_path


def release_arguments(
    tag: str,
    artifact_paths: list[Path],
    checksum_path: Path,
    metadata_path: Path,
    notes_path: Path,
) -> list[str]:
    return [
        "gh",
        "release",
        "create",
        tag,
        *(str(path) for path in artifact_paths),
        str(checksum_path),
        str(metadata_path),
        "--generate-notes",
        "--notes-file",
        str(notes_path),
        "--title",
        tag,
        "--verify-tag",
    ]


def remote_tag_commit(output: str, tag: str) -> str | None:
    references: dict[str, str] = {}
    for line in output.splitlines():
        if "\t" not in line:
            continue
        commit, reference = line.split("\t", maxsplit=1)
        references[reference] = commit
    peeled_reference = f"refs/tags/{tag}^{{}}"
    direct_reference = f"refs/tags/{tag}"
    return references.get(peeled_reference, references.get(direct_reference))


def ensure_tag(tag: str, head_commit: str, root: Path) -> None:
    tag_reference = f"refs/tags/{tag}^{{commit}}"
    local_tag = optional_command(["git", "rev-parse", "--verify", tag_reference], root)
    if local_tag.returncode == 0 and local_tag.stdout.strip() != head_commit:
        raise ValueError(f"{tag} already points to another commit")
    remote_tag_result = optional_command(
        [
            "git",
            "ls-remote",
            "--tags",
            "origin",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        root,
    )
    if remote_tag_result.returncode != 0:
        raise subprocess.CalledProcessError(
            remote_tag_result.returncode,
            remote_tag_result.args,
            stderr=remote_tag_result.stderr,
        )
    remote_commit = remote_tag_commit(remote_tag_result.stdout, tag)
    if remote_commit is not None and remote_commit != head_commit:
        raise ValueError(f"remote tag {tag} already points to another commit")

    if local_tag.returncode != 0 and remote_commit is None:
        subprocess.run(
            ["git", "tag", "--annotate", tag, "--message", tag],
            cwd=root,
            check=True,
        )
    if remote_commit is None:
        subprocess.run(["git", "push", "origin", f"refs/tags/{tag}"], cwd=root, check=True)


def run(
    root: Path,
    project_path: Path,
    catalog_path: Path,
    artifact_paths: list[Path],
) -> str:
    version = project_version(project_path)
    tag = f"v{version}"
    status = command_output(["git", "status", "--porcelain"], root)
    head_commit = command_output(["git", "rev-parse", "HEAD"], root)
    upstream_commit = command_output(["git", "rev-parse", "@{upstream}"], root)
    validate_release_state(status, head_commit, upstream_commit, artifact_paths)

    subprocess.run(
        ["gh", "auth", "status"],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(["gh", "repo", "view"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    existing_release = optional_command(["gh", "release", "view", tag], root)
    if existing_release.returncode == 0:
        raise ValueError(f"GitHub release {tag} already exists")

    ensure_tag(tag, head_commit, root)
    with tempfile.TemporaryDirectory(prefix="alfred-emoji-release-") as directory:
        checksum_path, metadata_path, notes_path = write_release_files(
            Path(directory),
            version,
            catalog_path,
            artifact_paths,
        )
        subprocess.run(
            release_arguments(
                tag,
                artifact_paths,
                checksum_path,
                metadata_path,
                notes_path,
            ),
            cwd=root,
            check=True,
        )
    return tag


def main() -> None:
    try:
        tag = run(ROOT, PROJECT_PATH, CATALOG_PATH, ARTIFACT_PATHS)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Published {tag} with {len(ARTIFACT_PATHS)} Alfred packages")


if __name__ == "__main__":
    main()
