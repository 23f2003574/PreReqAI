"""Optional bearer-token authentication of the HTTP API.

PreReqAI's server is built for the learner's own computer (see backend/security.py), where anything that can reach it can list, read and delete sessions and profiles. A deployment that must be
reachable by others sets PREREQAI_API_TOKEN: every path under /api/ then needs `Authorization: Bearer <token>`. A request without the header gets 401 (with WWW-Authenticate), a request with a
wrong token or another scheme gets 403, and the token is compared in constant time. Not protected: /health (a liveness probe), the page itself at / (it holds no data and asks the learner for the
token), and the interactive documentation. With no token set nothing changes, so local use needs no setup; the server then logs a warning when it is asked to listen on a non-loopback address
(`--host 0.0.0.0` or UVICORN_HOST), because that exposes every session unauthenticated. The token is never logged, echoed in a response or placed in an error message."""
import contextlib
import hashlib
import hmac
import json
import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # no POSIX file locks: count within this process only
    fcntl = None

TOKEN_ENV = "PREREQAI_API_TOKEN"
PROTECTED_PREFIX = "/api/"
LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
_log = logging.getLogger("prereqai.security")

MAX_FAILURES_ENV, WINDOW_ENV = "PREREQAI_AUTH_MAX_FAILURES", "PREREQAI_AUTH_LOCKOUT_SECONDS"
DEFAULT_MAX_FAILURES, DEFAULT_WINDOW, MAX_CLIENTS = 10, 60.0, 1024
DIR_ENV = "PREREQAI_AUTH_DIR"  # where the failure counters shared by the worker processes are kept (default: a per-user prereqai-auth-* folder of the temporary directory)
_failures = {}  # the counters of this process, used only when the shared file cannot be: key -> (failures in the current window, when the window started)
_failures_lock = threading.Lock()
_clock = time.time  # wall-clock seconds: the window must mean the same in every process (replaced in tests)


def _number(name, default, whole=False):
    try:
        value = float((os.environ.get(name) or "").strip())
    except ValueError:
        return default
    return int(value) if whole and value >= 1 else (value if value > 0 and not whole else default)


PROXY_ENV = "PREREQAI_TRUSTED_PROXY"


def _event(name, **fields):
    """A structured event (backend/observability.py) so wrong-token traffic can be counted and alerted on; it never carries the token, the address or the header."""
    from backend.observability import log_event

    log_event(name, **fields)


def client_address(scope):
    """The address wrong tokens are counted against. Normally the connection's peer. Behind one reverse proxy every connection comes from the proxy, so one attacker would lock out every learner: with PREREQAI_TRUSTED_PROXY=1
    the LAST entry of X-Forwarded-For (the one the trusted proxy itself appended, which a client cannot forge) is used instead, falling back to the peer when the header is absent or empty. Leave it unset when the server is reachable directly: the header is then client-written."""
    peer = (scope.get("client") or ("unknown",))[0]
    if (os.environ.get(PROXY_ENV) or "").strip().lower() not in ("1", "true", "yes", "on"):
        return peer
    forwarded = next((value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"x-forwarded-for"), "")
    last = forwarded.split(",")[-1].strip()
    return last[:64] if last else peer


def misconfiguration():
    """Warnings for throttle settings that are set but unusable (the defaults then apply silently, which would hide a typo from whoever tightened them): a list, empty when all is well."""
    found = []
    for name, whole, default in ((MAX_FAILURES_ENV, True, DEFAULT_MAX_FAILURES), (WINDOW_ENV, False, DEFAULT_WINDOW)):
        value = (os.environ.get(name) or "").strip()
        if value and _number(name, None, whole) is None:
            found.append(f"{name}={value!r} is not a positive {'whole number' if whole else 'number of seconds'}, so the default {default:g} applies.")
    return found


def _key(client):
    """The key a client address is counted under: a hash, so the shared file never holds an address."""
    return hashlib.sha256(str(client).encode("utf-8", "replace")).hexdigest()[:24]


def _store_file():
    configured = (os.environ.get(DIR_ENV) or "").strip()
    owner = os.getuid() if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    folder = Path(configured) if configured else Path(tempfile.gettempdir()) / f"prereqai-auth-{owner}"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder / "auth-failures.json"


@contextlib.contextmanager
def _state(window):
    """The failure counters {key: [failures in the window, when it started]} for one read-modify-write, shared by every server worker process on this computer through a small file held under an exclusive
    operating-system lock (so concurrent failures are counted exactly once each, whichever worker sees them). Records whose window has ended are dropped on every use and at most MAX_CLIENTS are kept (the oldest go
    first), so the file stays small. Without file locks (Windows) or when the folder cannot be used the counters of this process are used instead (`_failures`). The file holds hashed addresses, never a token."""
    with _failures_lock:
        handle = None
        if fcntl is not None:
            try:
                handle = os.fdopen(os.open(_store_file(), os.O_RDWR | os.O_CREAT, 0o600), "r+b")
                fcntl.flock(handle, fcntl.LOCK_EX)
            except OSError:
                handle = None
        try:
            if handle is None:
                data = _failures
            else:
                try:
                    loaded = json.loads(handle.read() or b"{}")
                except ValueError:
                    loaded = {}
                data = {k: (v[0], v[1]) for k, v in loaded.items() if isinstance(k, str) and isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)} if isinstance(loaded, dict) else {}
            now = _clock()
            for stale in [k for k, (_, started) in data.items() if now - started >= window]:
                del data[stale]
            yield data
            while len(data) > MAX_CLIENTS:
                del data[min(data, key=lambda k: data[k][1])]
            if handle is not None:
                handle.seek(0)
                handle.truncate(0)
                handle.write(json.dumps({k: list(v) for k, v in data.items()}).encode())
                handle.flush()
        finally:
            if handle is not None:
                handle.close()  # closing releases the lock


def retry_after(client):
    """Seconds (at least 1) until `client` may try again when it has failed PREREQAI_AUTH_MAX_FAILURES (default 10) times within PREREQAI_AUTH_LOCKOUT_SECONDS (default 60); 0 when it may try now.
    The counters are shared by every server worker process on this computer (see `_state`), so `--workers N` does not multiply the limit; they hold at most MAX_CLIENTS addresses (expired ones go first, then the oldest)."""
    window, limit = _number(WINDOW_ENV, DEFAULT_WINDOW), _number(MAX_FAILURES_ENV, DEFAULT_MAX_FAILURES, whole=True)
    with _state(window) as data:
        held = data.get(_key(client))
        if held is None:
            return 0
        count, started = held
        return max(1, int(window - (_clock() - started) + 0.999)) if count >= limit else 0


def record_failure(client):
    window = _number(WINDOW_ENV, DEFAULT_WINDOW)
    now = _clock()
    with _state(window) as data:
        held = data.get(_key(client))
        data[_key(client)] = (1, now) if held is None else (held[0] + 1, held[1])


def record_success(client):
    with _state(_number(WINDOW_ENV, DEFAULT_WINDOW)) as data:
        data.pop(_key(client), None)


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
            _event("auth_throttled", level=logging.WARNING, retry_after_seconds=wait)
            return await self._refuse(send, 429, "Too many invalid access tokens from this address; wait before trying again.", wait)
        authorization = next((value.decode("latin-1") for key, value in scope["headers"] if key.lower() == b"authorization"), "")
        refusal = check(authorization, token)
        if refusal is None:
            record_success(client)
            return await self.app(scope, receive, send)
        status, message = refusal
        _event("auth_refused", level=logging.WARNING, status=status, credential_sent=bool(authorization))
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
