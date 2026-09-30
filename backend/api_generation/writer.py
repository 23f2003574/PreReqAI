import os
from pathlib import Path

from .models import LLMAPIGenerationResult

_OWNED_PACKAGE = "app"


class UnsafeGeneratedPathError(ValueError):
    """Raised when a generated file path is absolute or escapes the output directory."""


def write_generated_application(result: LLMAPIGenerationResult, output_dir) -> list:
    """Write result.files under output_dir and return the written relative
    paths in sorted order. Each file is written to a temporary sibling and
    moved into place (the same write convention the session serializers use),
    so a failed write never leaves a half-written module. The `app/` package
    is owned by the generator: stale *.py files in it that this result no
    longer contains are removed, so regenerating never accumulates leftovers.
    Everything outside `app/` is left untouched."""
    root = Path(output_dir).resolve()
    targets = {}
    for relative in sorted(result.files):
        target = (root / relative).resolve()
        if Path(relative).is_absolute() or root not in target.parents:
            raise UnsafeGeneratedPathError(relative)
        targets[relative] = target

    for relative, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(result.files[relative], encoding="utf-8")
        os.replace(temporary, target)

    package = root / _OWNED_PACKAGE
    if package.is_dir():
        for stale in sorted(package.rglob("*.py")):
            if stale.relative_to(root).as_posix() not in targets:
                stale.unlink()
    return sorted(targets)
