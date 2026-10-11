"""Acceptance: a real server process is stopped and started again; the learner's session and progress are still there."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

SAMPLE = "examples/prerequisites/sample-paper.pdf"


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(port, sessions):
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port), "--log-level", "warning"],
                            env={**os.environ, "PREREQAI_SESSION_DIR": str(sessions)})
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/docs", timeout=1)
            return proc
        except Exception:
            time.sleep(0.2)
    proc.kill()
    raise AssertionError("the server did not start")


def _call(port, path, method="GET", data=None, headers=None):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def _upload(port):
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="paper"; filename="p.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
            ).encode() + open(SAMPLE, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    return _call(port, "/api/prerequisites/analyze", "POST", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def test_session_and_progress_survive_a_real_server_restart(tmp_path):
    first_port = _port()
    server = _start(first_port, tmp_path / "sessions")
    try:
        status, body = _upload(first_port)
        sid = body["session_id"]
        assert status == 200 and _call(first_port, f"/api/prerequisites/sessions/{sid}/studied?concept=Probability", "POST")[0] == 200
    finally:
        server.terminate()
        server.wait(10)

    second_port = _port()
    server = _start(second_port, tmp_path / "sessions")
    try:
        status, session = _call(second_port, f"/api/session/{sid}")
        assert status == 200 and session["paper_title"] == body["report"]["paper"]["title"]
        question = json.dumps({"question": "What is attention?"}).encode()
        status, answer = _call(second_port, f"/api/session/{sid}/question", "POST", question, {"Content-Type": "application/json"})
        assert status == 200 and answer["responses"][0]["supporting_concepts"]
        status, again = _call(second_port, f"/api/prerequisites/sessions/{sid}/studied?concept=Neural%20Networks", "POST")
        assert status == 200 and again["readiness"]["completed_concepts"] == 2  # Probability survived the restart
    finally:
        server.terminate()
        server.wait(10)
