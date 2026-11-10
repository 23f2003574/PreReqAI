"""Release checklist step 1: `backend/version.py` is the one version source for the API (OpenAPI info) and `--version`."""
import pytest
from fastapi.testclient import TestClient

from backend.cli import main
from backend.main import app
from backend.version import __version__

pytestmark = pytest.mark.prereqai


def test_openapi_info_version_is_the_version_module_value():
    assert TestClient(app).get("/openapi.json").json()["info"]["version"] == __version__


def test_cli_version_prints_the_same_value(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out
