"""Regression fixture for examples/api-generation: the committed draft still
generates, through the real CLI, exactly the committed reference project, and
that project is healthy and serves its documented example."""
import json
import subprocess
import sys
from pathlib import Path

from backend.cli import EXIT_OK, main

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "api-generation"


def _tree(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_example_draft_regenerates_the_committed_reference_project(tmp_path, capsys):
    out = tmp_path / "project"

    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(out), "--json"]) == EXIT_OK
    result = json.loads(capsys.readouterr().out)
    assert result["endpoint"] == "POST /loan-quote"

    # If the generator's output changes on purpose, regenerate the reference
    # project (see examples/api-generation/README.md) in the same commit.
    assert _tree(out) == _tree(EXAMPLE / "generated")
    assert main(["api-generation", "check", str(EXAMPLE / "generated"), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "healthy"


def test_example_project_serves_its_typed_documented_endpoint(tmp_path):
    draft = json.loads((EXAMPLE / "draft.json").read_text())
    example = draft["examples"][0]
    probe = subprocess.run(
        [sys.executable, "-c",
         "import json, sys; from fastapi.testclient import TestClient; from app.main import app\n"
         "c = TestClient(app); body = json.loads(sys.argv[1])\n"
         "ok = c.post('/loan-quote', json=body)\n"
         "small = c.post('/loan-quote', json={**body, 'amount': 10})\n"
         "other = c.post('/loan-quote', json={**body, 'amount': 2000})\n"
         "print(json.dumps({'ok': [ok.status_code, ok.headers.get('x-execution'), ok.json()],"
         " 'small': small.status_code, 'other': other.status_code, 'openapi': c.get('/openapi.json').json()}))",
         json.dumps(example["input"])],
        cwd=EXAMPLE / "generated", capture_output=True, text=True,
    )
    assert probe.returncode == 0, probe.stderr
    seen = json.loads(probe.stdout)

    assert seen["ok"] == [200, "documented-example", example["output"]]
    assert seen["small"] == 422  # amount's documented minimum is enforced
    assert seen["other"] == 501  # no notebook logic is attached to the generated app
    assert seen["openapi"]["paths"] == json.loads((EXAMPLE / "generated" / "openapi.json").read_text())["paths"]
    schemas = seen["openapi"]["components"]["schemas"]
    assert set(schemas["PostLoanQuoteResponse"]["properties"]) == {"monthly_payment", "approved", "applicant_name"}
    assert schemas["PostLoanQuoteRequest"]["required"] == ["amount", "applicant"]


def test_example_notebook_computes_the_documented_example_output():
    notebook = json.loads((EXAMPLE / "loan_quote.ipynb").read_text())
    namespace = {}
    exec("".join(notebook["cells"][1]["source"]), namespace)
    example = json.loads((EXAMPLE / "draft.json").read_text())["examples"][0]

    assert namespace["loan_quote"](**example["input"]) == example["output"]
