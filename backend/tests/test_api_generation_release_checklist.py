import json

import pytest

import backend.api_generation.workflow as workflow
from backend.api_generation import APIGenerator, FastAPIApplicationGenerator, run_release_checklist
from test_api_generation_boundary import _draft, _env


class Variant(APIGenerator):
    def __init__(self, change):
        self.change = change

    def generate(self, draft):
        return self.change(dict(FastAPIApplicationGenerator().generate(draft)))


def _run(generator=None):
    env = _env()
    _, validated = _draft(env)
    return run_release_checklist(env["draft"], validated, generator)


def _failed(result):
    return {c["name"] for c in result.checks if c["status"] == "failed"}


def test_a_fully_passing_checklist_is_ready_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = _run()

    assert result.ready and result.failures == [] and len(result.checks) == 9
    assert {c["status"] for c in result.checks} == {"passed"} and "docker build" in result.warnings[0]
    assert list(tmp_path.iterdir()) == []
    assert json.loads(json.dumps(result.to_dict()))["ready"] is True


def test_a_missing_artifact_fails_the_relevant_checks():
    result = _run(Variant(lambda f: {k: v for k, v in f.items() if k != "README.md"}))

    assert not result.ready and "README references the actual artifacts" in _failed(result)
    assert any("MISSING_FILE README.md" in f for f in result.failures)


def test_an_invalid_manifest_fails_the_metadata_and_manifest_check():
    result = _run(Variant(lambda f: {**f, "prereqai-manifest.json": "{}"}))

    assert not result.ready and "metadata and manifest are present and consistent" in _failed(result)
    assert "generated artifacts pass validation" in _failed(result)


def test_a_broken_generated_application_fails_the_import_check():
    result = _run(Variant(lambda f: {**f, "app/main.py": "def broken(:\n"}))

    assert not result.ready and "generated application can be imported" in _failed(result)
    assert any("SYNTAX_ERROR" in f for f in result.failures)


def test_failed_validation_is_reported_without_a_traceback():
    result = _run(Variant(lambda f: {**f, "requirements.txt": "fastapi\n"}))

    assert not result.ready and _failed(result) == {"generated artifacts pass validation"}
    assert all("Traceback" not in f for f in result.failures)


def test_a_dry_run_that_disagrees_with_generation_is_a_failure(monkeypatch):
    real = workflow.plan_write

    def lying(result, output_dir):
        root, targets, old = real(result, output_dir)
        return root, {k: v for k, v in targets.items() if k != "Dockerfile"}, old

    monkeypatch.setattr(workflow, "plan_write", lying)

    result = _run()

    assert not result.ready and _failed(result) == {"dry run does not mutate output"}


def test_a_generator_that_raises_is_a_failed_check_not_a_crash():
    class Exploding(APIGenerator):
        def generate(self, draft):
            raise RuntimeError("boom")

    result = _run(Exploding())

    assert not result.ready and any("GENERATION_ERROR" in f and "boom" in f for f in result.failures)
    assert pytest.approx(len(result.checks)) == 9
