"""Guards the redundant-work fix: the generated app used to be imported and its
OpenAPI document built three times per generation (generator, validator, and
the validator's file comparison); it is now twice (generator, independent
validation). Output must be unchanged."""
import json

from fastapi import FastAPI

from backend.api_generation import generate_application
from test_api_generation_boundary import _draft, _env


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


def test_generation_builds_the_openapi_document_only_twice_and_output_is_unchanged(tmp_path, monkeypatch):
    env = _env()
    _, validated = _draft(env)
    calls = {"n": 0}
    real = FastAPI.openapi

    def counting(self):
        calls["n"] += 1
        return real(self)

    monkeypatch.setattr(FastAPI, "openapi", counting)
    generate_application(env["draft"], validated, tmp_path / "a")
    first_run_calls = calls["n"]
    generate_application(env["draft"], validated, tmp_path / "b")

    assert first_run_calls == 2 and calls["n"] == 4
    assert _tree(tmp_path / "a") == _tree(tmp_path / "b")  # still deterministic
    document = json.loads((tmp_path / "a" / "openapi.json").read_text())
    assert list(document["paths"]) == ["/add"] and (tmp_path / "a" / "openapi.json").read_text().endswith("}\n")
