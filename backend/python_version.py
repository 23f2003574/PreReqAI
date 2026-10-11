"""Fail early, with a readable message, on a Python older than PreReqAI supports.

Imported first by the CLI and the HTTP app: on an older interpreter the package's own modules fail much later with an
unrelated-looking SyntaxError or TypeError (for example from `X | None` annotations).
"""

import sys

MINIMUM = (3, 10)


def check_python_version(version_info=None) -> None:
    """Raise SystemExit naming the running and the required version when the interpreter is too old."""

    version_info = tuple(version_info if version_info is not None else sys.version_info[:3])

    if version_info[:2] < MINIMUM:

        running = ".".join(str(part) for part in version_info)
        required = ".".join(str(part) for part in MINIMUM)

        raise SystemExit(
            f"PreReqAI needs Python {required} or newer, but this is Python {running}. "
            f"Create the virtual environment with a newer interpreter (python{required} -m venv .venv)."
        )
