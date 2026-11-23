"""Optional bearer-token authentication of the HTTP API.

PreReqAI's server is built for the learner's own computer (see backend/security.py), where anything that can reach it can list, read and delete sessions and profiles. A deployment that must be
reachable by others sets PREREQAI_API_TOKEN: every path under /api/ then needs `Authorization: Bearer <token>`. A request without the header gets 401 (with WWW-Authenticate), a request with a
wrong token or another scheme gets 403, and the token is compared in constant time. Not protected: /health (a liveness probe), the page itself at / (it holds no data and asks the learner for the
token), and the interactive documentation. With no token set nothing changes, so local use needs no setup; the server then logs a warning when it is asked to listen on a non-loopback address
(`--host 0.0.0.0` or UVICORN_HOST), because that exposes every session unauthenticated. The token is never logged, echoed in a response or placed in an error message."""
import hmac
import json
import logging
import os
import sys

TOKEN_ENV = "PREREQAI_API_TOKEN"
PROTECTED_PREFIX = "/api/"
LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
_log = logging.getLogger("prereqai.security")


def configured_token():
    """The configured token, or None when the variable is unset or blank."""
    return (os.environ.get(TOKEN_ENV) or "").strip() or None


def check(authorization, token):
    """None when the Authorization header value carries the token; else (status, message): 401 without a Bearer credential, 403 for a wrong token or another scheme."""
    if not authorization:
        return 401, "This server requires an access token: send Authorization: Bearer <token>."
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        return 403, "The credential is not a bearer token."
    if not hmac.compare_digest(credential.strip().encode("utf-8"), token.encode("utf-8")):
        return 403, "The access token is not valid."
    return None


class ApiTokenMiddleware:
    """A pure ASGI middleware: when PREREQAI_API_TOKEN is set, requests under /api/ must present it (the variable is read per request, so it can be set or rotated without rebuilding the app)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = configured_token()
        if scope["type"] != "http" or token is None or not scope["path"].startswith(PROTECTED_PREFIX) or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        authorization = next((value.decode("latin-1") for key, value in scope["headers"] if key.lower() == b"authorization"), "")
        refusal = check(authorization, token)
        if refusal is None:
            return await self.app(scope, receive, send)
        status, message = refusal
        body = json.dumps({"status": "failure", "stage": "authentication", "detail": message, "hint": f"Set the {TOKEN_ENV} value of the server as a bearer token."}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def bind_host(argv=None, environ=None):
    """The address the server was asked to listen on (`--host X`, `--host=X`, or UVICORN_HOST), or None when it was not named (uvicorn then listens on 127.0.0.1)."""
    argv, environ = list(sys.argv if argv is None else argv), os.environ if environ is None else environ
    for position, argument in enumerate(argv):
        if argument == "--host" and position + 1 < len(argv):
            return argv[position + 1]
        if argument.startswith("--host="):
            return argument.split("=", 1)[1]
    return environ.get("UVICORN_HOST") or None


def exposure_warning(host, token_set):
    """A warning text when the server listens beyond this computer without a token, else None."""
    if token_set or not host or host.strip().lower() in LOOPBACK:
        return None
    return (f"PreReqAI is listening on {host} without {TOKEN_ENV}: anyone who can reach this address can list, read and delete sessions and profiles. "
            f"Set {TOKEN_ENV} to require a bearer token, or listen on 127.0.0.1.")


def warn_if_exposed(argv=None, environ=None):
    message = exposure_warning(bind_host(argv, environ), configured_token() is not None)
    if message:
        _log.warning(message)
    return message
