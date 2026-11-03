"""Real runtime (no TestClient, no mocks): the project PreReqAI generates is started exactly the way its Dockerfile CMD
starts it -- `sh -c` with HOST and PORT taken from the environment -- answers its documented example over a socket, and
stops cleanly on SIGTERM. The earlier smoke tests import the project in-process; none of them launches the server."""
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.prereqai

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "examples/api-generation/draft.json"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _post(port, body):
    request = urllib.request.Request(f"http://127.0.0.1:{port}/loan-quote", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers.get("X-Execution"), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("X-Execution"), json.loads(error.read())


def test_the_generated_project_starts_from_its_dockerfile_cmd_serves_its_example_and_stops_on_sigterm(tmp_path):
    project = tmp_path / "project"
    generated = subprocess.run([sys.executable, "-m", "backend.cli", "api-generation", "generate", "--draft", str(DRAFT),
                                "--output-dir", str(project)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert generated.returncode == 0, generated.stderr

    cmd = json.loads(re.search(r"^CMD (\[.*\])$", (project / "Dockerfile").read_text(), re.MULTILINE).group(1))
    assert cmd[:2] == ["sh", "-c"]
    port = _free_port()
    # the container has uvicorn on PATH; here that is this interpreter's own environment
    env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port),
           "PATH": os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")}
    server = subprocess.Popen(cmd, cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=1).read()
                break
            except Exception:
                assert server.poll() is None, server.stdout.read()
                time.sleep(0.2)
        else:
            raise AssertionError("the generated server did not start")

        documented = json.loads(DRAFT.read_text())["examples"][0]
        status, marker, body = _post(port, documented["input"])
        assert (status, marker, body) == (200, "documented-example", documented["output"])
        assert _post(port, {**documented["input"], "amount": 12001})[0] == 501  # no notebook logic: an honest 501
        assert _post(port, {"amount": 1})[0] == 422  # a malformed request is rejected, not a crash
    finally:
        server.send_signal(signal.SIGTERM)
        try:
            output, _ = server.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
            output, _ = server.communicate()
            raise AssertionError("the generated server ignored SIGTERM")

    # uvicorn finishes its graceful shutdown and then re-raises the signal, so a clean stop ends with 0 or -SIGTERM
    assert "Application shutdown complete" in output and server.returncode in (0, -signal.SIGTERM)
