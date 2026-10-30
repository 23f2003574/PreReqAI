"""The quickstart and the server import only packages that requirements.txt installs (CI installs requirements-dev.txt, which would hide a
runtime import of a dev-only package such as pytest or httpx until a user installs just the runtime requirements)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]

PROBE = r"""
import importlib.metadata as md, json, re, sys
roots = [re.split(r"[<>=!~\[; ]", line.split("#")[0].strip())[0] for line in open("requirements.txt") if line.split("#")[0].strip()]
seen, todo = set(), [r.lower().replace("_", "-") for r in roots]
while todo:
    name = todo.pop()
    if name in seen:
        continue
    seen.add(name)
    try:
        requires = md.requires(name) or []
    except md.PackageNotFoundError:
        continue
    todo += [re.split(r"[<>=!~\[; (]", r)[0].lower().replace("_", "-") for r in requires if "extra ==" not in r]
allowed = {top for dist, tops in md.packages_distributions().items() for top in [dist] for _ in [0]}
allowed = {module for module, dists in md.packages_distributions().items() if any(d.lower().replace("_", "-") in seen for d in dists)}
# optional imports (the LLM adapters' SDKs, anyio's sniffio) are not in requirements.txt: hide them, as in a runtime-only install
for optional in ("google", "google.generativeai", "openai", "sniffio"):
    sys.modules[optional] = None
import backend.cli, backend.main
loaded = {name.split(".")[0] for name, module in sys.modules.items() if module is not None and not name.startswith("_")}
pseudo = {"sitecustomize", "usercustomize", "cython_runtime", "swig_runtime_data5"}  # interpreter/host artefacts, not imports of ours
third_party = {m for m in loaded if m not in sys.stdlib_module_names and m != "backend" and m not in pseudo}
print(json.dumps(sorted(third_party - allowed)))
"""


def test_cli_and_server_import_only_packages_from_requirements_txt():
    run = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout.strip().splitlines()[-1]) == []


def test_the_probe_would_flag_a_dev_only_package():
    # sanity check of the probe itself: pytest is installed here but is not a runtime requirement
    code = PROBE.replace("\nimport backend.cli, backend.main\n", "\nimport backend.cli, backend.main, pytest\n")
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert "pytest" in json.loads(run.stdout.strip().splitlines()[-1])


def test_ci_also_runs_the_quickstart_with_only_the_runtime_requirements():
    workflow = (ROOT / ".github/workflows/prereqai.yml").read_text(encoding="utf-8")
    assert re.search(r'/pip" install -r requirements\.txt', workflow) and "-m venv" in workflow
