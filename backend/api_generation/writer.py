import json
import os
from pathlib import Path

from .metadata import METADATA_FILENAME, InvalidProjectMetadataError, GeneratedProjectMetadata
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
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_marker(root: Path):
    marker = root / MARKER_FILENAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return set(data["files"]), data["status"]
    except (OSError, ValueError, KeyError, TypeError):
        raise UnsafeOutputDirectoryError(f"{MARKER_FILENAME} in {root} is unreadable; refusing to overwrite")


def _is_generated_project(root: Path) -> bool:
    """True when root holds a valid prereqai-project.json -- the project's own
    identity file proves it is generated output even if its marker is gone."""
    try:
        GeneratedProjectMetadata.parse((root / METADATA_FILENAME).read_text(encoding="utf-8"))
    except (OSError, InvalidProjectMetadataError):
        return False
    return True


def _clean_up_failed_attempt(root, root_existed, marker_existed, created_files, created_dirs, old_files):
    """Undo only what the failed attempt created: its new files, the new
    directories they needed and, for a first generation, the marker (and the
    output directory itself if it did not exist). Files that existed before
    are left alone. For a regeneration the marker stays INCOMPLETE and lists
    the files of the earlier run, so the half-updated project is never taken
    for a finished one. Idempotent: every removal tolerates absence."""
    for path in created_files:
        path.unlink(missing_ok=True)
    for directory in sorted(created_dirs, key=lambda d: len(d.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    marker = root / MARKER_FILENAME
    if marker_existed:
        try:
            _atomic_write(marker, json.dumps({"status": INCOMPLETE, "files": sorted(old_files)}))
        except OSError:
            pass
    else:
        marker.unlink(missing_ok=True)
        if not root_existed:
            try:
                root.rmdir()
            except OSError:
                pass


def preflight_output_dir(output_dir) -> Path:
    """Cheap, read-only checks of the generation target that need no
    generated files: it can be created or written (its nearest existing
    ancestor is a writable directory), it is not a file, and an existing
    generation marker is readable. Returns the resolved path. The overwrite
    rules that depend on which files would be written (collisions in an
    unmarked directory) are applied later by plan_write(). Touches nothing."""
    root = Path(output_dir).resolve()
    if root.exists() and not root.is_dir():
        raise UnsafeOutputDirectoryError(f"{root} exists and is not a directory")
    if root.is_dir():
        _read_marker(root)  # raises UnsafeOutputDirectoryError if the marker is unreadable
    anchor = root
    while not anchor.exists():
        anchor = anchor.parent
    if not anchor.is_dir():
        raise UnsafeOutputDirectoryError(f"cannot create {root}: {anchor} is not a directory")
    if not os.access(anchor, os.W_OK | os.X_OK):
        raise UnsafeOutputDirectoryError(f"cannot write to {root}: {anchor} is not writable")
    return root


def plan_write(result: LLMAPIGenerationResult, output_dir):
    """The read-only half of write_generated_application: resolve the output
    location and the target path of every file, and apply the overwrite rules.
    Returns (root, {relative path: absolute target}, files of the earlier
    generation run). Touches nothing; raises UnsafeGeneratedPathError or
    UnsafeOutputDirectoryError exactly as a real write would."""
    root = Path(output_dir).resolve()
    targets = {}
    for relative in sorted(result.files):
        target = (root / relative).resolve()
        if Path(relative).is_absolute() or root not in target.parents or relative == MARKER_FILENAME:
            raise UnsafeGeneratedPathError(relative)
        targets[relative] = target

    if root.exists() and not root.is_dir():
        raise UnsafeOutputDirectoryError(f"{root} exists and is not a directory")
    previous = _read_marker(root) if root.is_dir() else None
    if previous is None:
        collisions = sorted(r for r, t in targets.items() if t.exists())
        if collisions and not _is_generated_project(root):
            raise UnsafeOutputDirectoryError(
                f"{root} already contains {collisions} but is not marked as generated output; refusing to overwrite"
            )
        old_files = set()
    else:
        old_files = previous[0]

    return root, targets, old_files


def _remove_bytecode_cache(source: Path):
    """Remove the bytecode Python cached for a stale generated module
    (`__pycache__/<name>.*.pyc` beside it), and that `__pycache__` if it is
    then empty. Without this, importing a project once and regenerating it
    under another package left the old package directory behind, holding
    only caches of modules that no longer exist. Only caches of the removed
    file itself are touched, never other files."""
    if source.suffix != ".py":
        return
    cache = source.parent / "__pycache__"
    for compiled in cache.glob(f"{source.stem}.*.pyc"):
        compiled.unlink()
    try:
        cache.rmdir()  # only if now empty
    except OSError:
        pass


def write_generated_application(result: LLMAPIGenerationResult, output_dir) -> list:
    """Write result.files under output_dir and return the written relative
    paths in sorted order.

    Ownership is recorded in a marker file (MARKER_FILENAME) listing the
    generated files and whether the last run completed. Rules:
      * a new or empty directory is written freely;
      * a directory with a marker is earlier generated output: files the new
        result no longer contains are removed (stale), files are overwritten;
      * a directory without a marker is only written if none of the target
        paths already exist, or if it holds a valid prereqai-project.json
        (proof it is generated output; its files are overwritten but stale
        ones cannot be known); otherwise UnsafeOutputDirectoryError is raised
        before anything is touched;
      * files that are not in the marker are never deleted, so unrelated user
        files survive every run.
    The marker is set to `incomplete` before the first file is written and to
    `complete` only after the last one, so an interrupted regeneration is
    detectable and never looks like a finished project. If a write fails, the
    files and directories this attempt created are removed (a first generation
    leaves the directory as it found it); pre-existing files are untouched. Each file is written
    to a temporary sibling and moved into place."""
    root, targets, old_files = plan_write(result, output_dir)
    root_existed, marker_path = root.exists(), root / MARKER_FILENAME
    marker_existed = marker_path.exists()
    created_files, created_dirs = [], []
    try:
        _atomic_write(marker_path, json.dumps({"status": INCOMPLETE, "files": sorted(old_files | set(targets))}))
        for relative, target in targets.items():
            parent = target.parent
            while parent != root and not parent.exists():
                created_dirs.append(parent)
                parent = parent.parent
            existed = target.exists()
            _atomic_write(target, result.files[relative])
            if not existed:
                created_files.append(target)
        for stale in sorted(old_files - set(targets)):
            path = (root / stale).resolve()
            if root in path.parents and path.is_file():
                path.unlink()
                _remove_bytecode_cache(path)
                try:
                    path.parent.rmdir()  # only if now empty
                except OSError:
                    pass
        _atomic_write(marker_path, json.dumps({"status": COMPLETE, "files": sorted(targets)}))
    except BaseException as error:
        _clean_up_failed_attempt(root, root_existed, marker_existed, created_files, created_dirs, old_files)
        if isinstance(error, Exception):
            error.add_note(f"generation cleaned up {len(created_files)} file(s) created by this attempt")
        raise
    return sorted(targets)


def generation_status(output_dir):
    """COMPLETE, INCOMPLETE, or None when output_dir has no generation marker."""
    marker = _read_marker(Path(output_dir).resolve())
    return None if marker is None else marker[1]
