"""Upgrade detection: a generated project is current, older-but-compatible
(upgradable: still healthy, with a non-blocking "regeneration may be
required" signal) or incompatible. Detection only -- nothing is rewritten.
Every contract is still at its first version, so the older-compatible state
is exercised by lowering OLDEST_COMPATIBLE, the one knob that defines it."""
import hashlib
import json
import shutil

import pytest

from backend.api_generation import (
    METADATA_FILENAME,
    PROJECT_MANIFEST_FILENAME,
    APIGenerator,
    FastAPIApplicationGenerator,
    check_generated_project,
    run_release_checklist,
)
from backend.api_generation import metadata as metadata_module
from backend.api_generation.metadata import version_compatibility
from backend.cli import EXIT_OK, main
from test_api_generation_boundary import _draft, _env
from test_generated_project_importability import EXAMPLE


@pytest.fixture
def project(tmp_path):
    copy = tmp_path / "project"
    shutil.copytree(EXAMPLE / "generated", copy)
    return copy


@pytest.fixture
def contract_v0_still_supported(monkeypatch):
    """Pretend contract_version 0 is an older contract this generator still reads."""
    monkeypatch.setitem(metadata_module.OLDEST_COMPATIBLE, "contract_version", 0)


def _set_contract(project, version):
    for file in (METADATA_FILENAME, PROJECT_MANIFEST_FILENAME):
        data = json.loads((project / file).read_text())
        data["contract_version"] = version
        (project / file).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _fingerprint(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def test_the_comparison_lives_in_the_version_rule(monkeypatch):
    data = {"contract_version": 0}
    assert version_compatibility({"contract_version": 1}, "contract_version", 1, "f") is None  # current
    assert version_compatibility(data, "contract_version", 1, "f")["relation"] == "older"  # below the range
    monkeypatch.setitem(metadata_module.OLDEST_COMPATIBLE, "contract_version", 0)
    assert version_compatibility(data, "contract_version", 1, "f")["relation"] == "upgradable"
    assert version_compatibility({"contract_version": 2}, "contract_version", 1, "f")["relation"] == "newer"


def test_current_project_has_no_upgrade_signal(project, capsys):
    health = check_generated_project(project)
    assert health.healthy and health.compatibility["status"] == "compatible"
    assert health.compatibility["remediation"] is None and health.compatibility["issues"] == []

    assert main(["api-generation", "check", str(project)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Compatibility: COMPATIBLE" in out and "fix:" not in out and "upgrad" not in out.lower()

    env = _env()
    _, validated = _draft(env)
    checklist = run_release_checklist(env["draft"], validated)
    assert checklist.ready and not any(w.startswith("compatibility") for w in checklist.warnings)


def test_older_compatible_project_is_healthy_flagged_and_untouched(project, capsys, contract_v0_still_supported):
    _set_contract(project, 0)
    before = _fingerprint(project)

    health = check_generated_project(project)
    diagnosis = health.compatibility

    assert health.healthy and health.findings == []  # compatible: nothing blocks it
    assert diagnosis["status"] == "upgradable"
    assert diagnosis["oldest_compatible"][METADATA_FILENAME] == {"contract_version": 0}
    assert {(i["file"], i["relation"]) for i in diagnosis["issues"]} == {
        (METADATA_FILENAME, "upgradable"), (PROJECT_MANIFEST_FILENAME, "upgradable")}
    assert "regeneration may be required" in diagnosis["remediation"]
    assert "Nothing was changed" in diagnosis["remediation"]

    assert main(["api-generation", "check", str(project)]) == EXIT_OK  # a signal, not a failure
    out = capsys.readouterr().out
    assert "Compatibility: UPGRADABLE" in out and "Regeneration recommended (informational" in out
    assert _fingerprint(project) == before  # detection never modifies the project


def test_older_compatible_generation_warns_but_does_not_block_a_release(contract_v0_still_supported):
    class OlderContract(APIGenerator):
        def generate(self, draft):
            files = FastAPIApplicationGenerator().generate(draft)
            for file in (METADATA_FILENAME, PROJECT_MANIFEST_FILENAME):
                data = json.loads(files[file])
                files[file] = json.dumps({**data, "contract_version": 0}, indent=2, sort_keys=True) + "\n"
            return files

    env = _env()
    _, validated = _draft(env)
    checklist = run_release_checklist(env["draft"], validated, OlderContract())

    assert checklist.compatibility["status"] == "upgradable"
    assert not any(f.startswith("compatibility") for f in checklist.failures)
    assert any(w.startswith("compatibility: This project uses an older but still compatible") for w in checklist.warnings)


def test_versions_outside_the_range_stay_incompatible(project, contract_v0_still_supported):
    _set_contract(project, -1)  # older than the oldest compatible version
    health = check_generated_project(project)
    assert health.status == "incompatible" and health.compatibility["status"] == "incompatible"
    assert {i["relation"] for i in health.compatibility["issues"]} == {"older"}

    _set_contract(project, 2)
    assert check_generated_project(project).compatibility["status"] == "incompatible"
