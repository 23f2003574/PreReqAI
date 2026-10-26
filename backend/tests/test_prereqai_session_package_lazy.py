"""`import backend.session` stays cheap: its ~2000 exported names are imported on first use, and every one still resolves."""
import subprocess
import sys

import backend.session as session


def test_importing_the_package_does_not_load_its_submodules():
    code = (
        "import sys, backend.session\n"
        "loaded = [m for m in sys.modules if m.startswith('backend.session.')]\n"
        "assert len(loaded) < 20, len(loaded)\n"
        "assert backend.session.session_manager is not None\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_every_exported_name_resolves_to_its_object():
    for name in session._EXPORTS:
        assert getattr(session, name) is not None, name
    assert session.ResearchWorkspaceConsumerProjectionDiagnosticsStatus is session.ResearchWorkspaceConsumerProjectionDiagnosticStatus
    assert "TutorMode" in dir(session)


def test_unknown_names_still_raise_attribute_error():
    try:
        session.NoSuchThing
    except AttributeError:
        return
    raise AssertionError("expected AttributeError")
