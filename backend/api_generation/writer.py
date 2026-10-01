import json
import os
from pathlib import Path

from .models import LLMAPIGenerationResult

MARKER_FILENAME = ".prereqai-generated.json"
COMPLETE = "complete"
INCOMPLETE = "incomplete"


class UnsafeGeneratedPathError(ValueError):
    """Raised when a generated file path is absolute or escapes the output directory."""


class UnsafeOutputDirectoryError(ValueError):
    """Raised, before anything is written, when the output directory holds
    files at generated paths but carries no generation marker, so it cannot be
    identified as earlier generated output and must not be overwritten."""


def _atomic_write(target: Path, text: str):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, target)


def _read_marker(root: Path):
    marker = root / MARKER_FILENAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return set(data["files"]), data["status"]
    except (OSError, ValueError, KeyError, TypeError):
        raise UnsafeOutputDirectoryError(f"{MARKER_FILENAME} in {root} is unreadable; refusing to overwrite")


def write_generated_application(result: LLMAPIGenerationResult, output_dir) -> list:
    """Write result.files under output_dir and return the written relative
    paths in sorted order.

    Ownership is recorded in a marker file (MARKER_FILENAME) listing the
    generated files and whether the last run completed. Rules:
      * a new or empty directory is written freely;
      * a directory with a marker is earlier generated output: files the new
        result no longer contains are removed (stale), files are overwritten;
      * a directory without a marker is only written if none of the target
        paths already exist; otherwise UnsafeOutputDirectoryError is raised
        before anything is touched;
      * files that are not in the marker are never deleted, so unrelated user
        files survive every run.
    The marker is set to `incomplete` before the first file is written and to
    `complete` only after the last one, so an interrupted regeneration is
    detectable and never looks like a finished project. Each file is written
    to a temporary sibling and moved into place."""
    root = Path(output_dir).resolve()
    targets = {}
    for relative in sorted(result.files):
        target = (root / relative).resolve()
        if Path(relative).is_absolute() or root not in target.parents or relative == MARKER_FILENAME:
            raise UnsafeGeneratedPathError(relative)
        targets[relative] = target

    previous = _read_marker(root) if root.is_dir() else None
    if previous is None:
        collisions = sorted(r for r, t in targets.items() if t.exists())
        if collisions:
            raise UnsafeOutputDirectoryError(
                f"{root} already contains {collisions} but is not marked as generated output; refusing to overwrite"
            )
        old_files = set()
    else:
        old_files = previous[0]

    _atomic_write(root / MARKER_FILENAME, json.dumps({"status": INCOMPLETE, "files": sorted(old_files | set(targets))}))
    for relative, target in targets.items():
        _atomic_write(target, result.files[relative])
    for stale in sorted(old_files - set(targets)):
        path = (root / stale).resolve()
        if root in path.parents and path.is_file():
            path.unlink()
            try:
                path.parent.rmdir()  # only if now empty
            except OSError:
                pass
    _atomic_write(root / MARKER_FILENAME, json.dumps({"status": COMPLETE, "files": sorted(targets)}))
    return sorted(targets)


def generation_status(output_dir):
    """COMPLETE, INCOMPLETE, or None when output_dir has no generation marker."""
    marker = _read_marker(Path(output_dir).resolve())
    return None if marker is None else marker[1]
