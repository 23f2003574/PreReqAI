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
import threading
import time

TOKEN_ENV = "PREREQAI_API_TOKEN"
PROTECTED_PREFIX = "/api/"
LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
_log = logging.getLogger("prereqai.security")

MAX_FAILURES_ENV, WINDOW_ENV = "PREREQAI_AUTH_MAX_FAILURES", "PREREQAI_AUTH_LOCKOUT_SECONDS"
DEFAULT_MAX_FAILURES, DEFAULT_WINDOW, MAX_CLIENTS = 10, 60.0, 1024
_failures = {}  # client address -> (failures in the current window, when the window started); bounded to MAX_CLIENTS entries
_failures_lock = threading.Lock()
_clock = time.monotonic  # replaced in tests


def _number(name, default, whole=False):
    try:
        value = float((os.environ.get(name) or "").strip())
    except ValueError:
        return default
    return int(value) if whole and value >= 1 else (value if value > 0 and not whole else default)


PROXY_ENV = "PREREQAI_TRUSTED_PROXY"


def client_address(scope):
    """The address wrong tokens are counted against. Normally the connection's peer. Behind one reverse proxy every connection comes from the proxy, so one attacker would lock out every learner: with PREREQAI_TRUSTED_PROXY=1
    the LAST entry of X-Forwarded-For (the one the trusted proxy itself appended, which a client cannot forge) is used instead, falling back to the peer when the header is absent or empty. Leave it unset when the server is reachable directly: the header is then client-written."""
    peer = (scope.get("client") or ("unknown",))[0]
    if (os.environ.get(PROXY_ENV) or "").strip().lower() not in ("1", "true", "yes", "on"):
        return peer
    forwarded = next((value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"x-forwarded-for"), "")
    last = forwarded.split(",")[-1].strip()
    return last[:64] if last else peer


def retry_after(client):
    """Seconds (at least 1) until `client` may try again when it has failed PREREQAI_AUTH_MAX_FAILURES (default 10) times within PREREQAI_AUTH_LOCKOUT_SECONDS (default 60); 0 when it may try now.
    The counters live in this process, so with several server workers each one counts for itself; they hold at most MAX_CLIENTS addresses (expired ones go first, then the oldest)."""
    window, limit = _number(WINDOW_ENV, DEFAULT_WINDOW), _number(MAX_FAILURES_ENV, DEFAULT_MAX_FAILURES, whole=True)
    with _failures_lock:
        held = _failures.get(client)
        if held is None:
            return 0
        count, started = held
        if _clock() - started >= window:
            del _failures[client]
            return 0
        return max(1, int(window - (_clock() - started) + 0.999)) if count >= limit else 0


def record_failure(client):
    window = _number(WINDOW_ENV, DEFAULT_WINDOW)
    now = _clock()
    with _failures_lock:
        held = _failures.get(client)
        if held is None or now - held[1] >= window:
            if len(_failures) >= MAX_CLIENTS:
                for stale in [key for key, (_, started) in _failures.items() if now - started >= window] or [next(iter(_failures))]:
                    del _failures[stale]
            _failures[client] = (1, now)
        else:
            _failures[client] = (held[0] + 1, held[1])


def record_success(client):
    with _failures_lock:
        _failures.pop(client, None)


NEXT_TOKEN_ENV = "PREREQAI_API_TOKEN_NEXT"


def configured_token():
    """The configured token, or None when the variable is unset or blank."""
    return (os.environ.get(TOKEN_ENV) or "").strip() or None


def configured_tokens():
    """Every token the server accepts: PREREQAI_API_TOKEN and, while a token is being rotated, PREREQAI_API_TOKEN_NEXT (blank ones are ignored). Rotation without downtime: set the new token as _NEXT and restart, move clients to it,
    then make it PREREQAI_API_TOKEN and drop _NEXT. An empty list means authentication is off."""
    return [value for value in ((os.environ.get(name) or "").strip() for name in (TOKEN_ENV, NEXT_TOKEN_ENV)) if value]


def check(authorization, token):
    """None when the Authorization header value carries the token; else (status, message): 401 without a Bearer credential, 403 for a wrong token or another scheme."""
    if not authorization:
        return 401, "This server requires an access token: send Authorization: Bearer <token>."
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        return 403, "The credential is not a bearer token."
    accepted = [token] if isinstance(token, str) else list(token)
    matches = [hmac.compare_digest(credential.strip().encode("utf-8"), candidate.encode("utf-8")) for candidate in accepted]  # every candidate is compared, so the time does not say which one was close
    if not any(matches):
        return 403, "The access token is not valid."
    return None


class ApiTokenMiddleware:
    """A pure ASGI middleware: when PREREQAI_API_TOKEN is set, requests under /api/ must present it (the variables are read per request, so it can be set or rotated without rebuilding the app)."""

    def __init__(self, app):
        self.app = app

    @staticmethod
    async def _refuse(send, status, message, wait):
        body = json.dumps({"status": "failure", "stage": "authentication", "detail": message, "hint": f"Try again in {wait} seconds."}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"retry-after", str(wait).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        token = configured_tokens() or None
        if scope["type"] != "http" or token is None or not scope["path"].startswith(PROTECTED_PREFIX) or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        client = client_address(scope)
        wait = retry_after(client)
        if wait:  # too many wrong tokens from this address: refuse without comparing anything
            _log.warning("API token attempts from one client are throttled (%d s left)", wait)
            return await self._refuse(send, 429, "Too many invalid access tokens from this address; wait before trying again.", wait)
        authorization = next((value.decode("latin-1") for key, value in scope["headers"] if key.lower() == b"authorization"), "")
        refusal = check(authorization, token)
        if refusal is None:
            record_success(client)
            return await self.app(scope, receive, send)
        status, message = refusal
        if authorization:  # a request that sent no credential at all is not a guess at the token
            record_failure(client)
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


def exposure_warning(host, token_set):  # token_set: whether any token is configured
    """A warning text when the server listens beyond this computer without a token, else None."""
    if token_set or not host or host.strip().lower() in LOOPBACK:
        return None
    return (f"PreReqAI is listening on {host} without {TOKEN_ENV}: anyone who can reach this address can list, read and delete sessions and profiles. "
            f"Set {TOKEN_ENV} to require a bearer token, or listen on 127.0.0.1.")


def warn_if_exposed(argv=None, environ=None):
    message = exposure_warning(bind_host(argv, environ), bool(configured_tokens()))
    if message:
        _log.warning(message)
    return message
