"""The HTTP API and the CLI share the recovery-decision service wiring through
backend.recovery_decision_services, so serving the API never imports the CLI
(argparse, the api-generation commands and their whole stack). The builders
stay importable from backend.cli as the same objects."""
import subprocess
import sys
from pathlib import Path

import backend.cli as cli
import backend.recovery_decision_services as services

ROOT = Path(__file__).resolve().parents[2]


def test_importing_the_http_app_does_not_import_the_cli():
    probe = ("import sys, backend.main; "
             "print(sorted(m for m in ('backend.cli', 'backend.cli_api_generation', 'backend.api_generation') "
             "if m in sys.modules))")
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_the_builders_remain_importable_from_backend_cli_as_the_same_objects():
    for name in ("build_recovery_decision_facade", "build_recovery_decision_health_service",
                 "build_recovery_decision_readiness_service", "build_recovery_decision_health_and_readiness_services",
                 "_build_collaborators", "_build_health_stack"):
        assert getattr(cli, name) is getattr(services, name), name
