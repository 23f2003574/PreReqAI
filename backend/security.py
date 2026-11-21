"""Protection of the local server against requests a web page the user happens to visit can make to it.

PreReqAI's server is meant to run on the learner's own computer, without accounts, so anything that can reach it with the learner's browser could read or change their sessions and
profile. Three things stop that:
* Host validation (DNS rebinding): a page on attacker.example whose DNS name is pointed at 127.0.0.1 sends `Host: attacker.example`. Only localhost, 127.0.0.1 and [::1] are served by default;
  other names must be listed, comma separated, in PREREQAI_TRUSTED_HOSTS (a name, or name:port). X-Forwarded-Host and similar headers are never trusted: the Host header the server received is what counts.
* Origin validation (cross-site requests): a state-changing request (POST, PUT, PATCH, DELETE) that carries an Origin must come from the page's own origin, or from one of PREREQAI_CORS_ORIGINS. Without
  an Origin it is allowed unless the browser marks it `Sec-Fetch-Site: cross-site`: command-line clients (curl, the CLI, tests) send neither header, and every browser sends at least one of them.
* Content-type validation: a state-changing request with a body must declare application/json, multipart/form-data or application/x-www-form-urlencoded, never the text/plain a cross-site page can
  send without a preflight; the profile import must be application/json.
Responses carry X-Content-Type-Options, X-Frame-Options, Referrer-Policy and a Content-Security-Policy (the page's script runs only with the per-response nonce), except the interactive API
documentation under /docs and /redoc, which loads its own scripts."""
import os
import secrets

TRUSTED_ENV = "PREREQAI_TRUSTED_HOSTS"
DEFAULT_HOSTS = ("localhost", "127.0.0.1", "[::1]")
TEST_ENV = "PREREQAI_ALLOW_TESTSERVER"  # set to 1 only by the test suite: "testserver" is the name Starlette's test client sends, and is not a production host
STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}
BODY_TYPES = ("application/json", "multipart/form-data", "application/x-www-form-urlencoded")
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def trusted_hosts():
    extra = {item.strip().lower() for item in os.environ.get(TRUSTED_ENV, "").split(",") if item.strip()}
    return {*DEFAULT_HOSTS, *extra, *(({"testserver"}) if os.environ.get(TEST_ENV) == "1" else ())}


def host_allowed(host_header):
    """Whether a Host header names this machine (or a configured trusted host); the port may be anything for the default names."""
    host = (host_header or "").strip().lower()
    if not host or "," in host or " " in host:
        return False
    if host.startswith("["):  # [::1] or [::1]:8000
        name = host.split("]")[0] + "]"
    else:
        name = host.split(":")[0]
    allowed = trusted_hosts()
    return host in allowed or name in allowed


def allowed_origins():
    return {origin.strip().rstrip("/").lower() for origin in os.environ.get("PREREQAI_CORS_ORIGINS", "").split(",") if origin.strip()}


def origin_allowed(origin, host_header, scheme):
    """Whether a request from `origin` is the page's own (same scheme, host and port as the Host header) or a configured origin."""
    origin = origin.strip().rstrip("/").lower()
    return origin in allowed_origins() or origin in {f"http://{(host_header or '').lower()}", f"https://{(host_header or '').lower()}"}


def _headers(scope):
    return {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope["headers"]}


def _csp(nonce):
    return ("default-src 'none'; script-src 'nonce-%s'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'" % nonce)


class LocalSecurityMiddleware:
    """A pure ASGI middleware (it does not buffer or wrap request bodies)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers, path, method = _headers(scope), scope["path"], scope["method"]
        refusal = self._refusal(headers, method, path, scope.get("scheme", "http"))
        nonce = secrets.token_urlsafe(16)
        scope.setdefault("state", {})["csp_nonce"] = nonce
        if refusal:
            status, message = refusal
            body = ('{"status": "failure", "stage": "request", "detail": "%s", "hint": "%s"}' % (message, "See PREREQAI_TRUSTED_HOSTS and PREREQAI_CORS_ORIGINS in the README.")).encode()
            await self._send_response(send, status, body, path, nonce)
            return
        async def with_headers(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), *self._security_headers(path, nonce)]}
            await send(message)

        await self.app(scope, receive, with_headers)

    @staticmethod
    def _refusal(headers, method, path, scheme):
        host = headers.get("host", "")
        if not host_allowed(host):
            return 403, "This server only answers requests addressed to localhost or a host listed in PREREQAI_TRUSTED_HOSTS."
        if method in STATE_CHANGING:
            origin, fetch_site = headers.get("origin"), headers.get("sec-fetch-site")
            if origin is not None and origin != "null" and not origin_allowed(origin, host, scheme):
                return 403, "A request from another website cannot change data here."
            if origin == "null" or (origin is None and fetch_site == "cross-site"):
                return 403, "A cross-site request cannot change data here."
            length = headers.get("content-length", "0")
            has_body = (length.isdigit() and int(length) > 0) or "transfer-encoding" in headers
            kind = headers.get("content-type", "").split(";")[0].strip().lower()
            if has_body and kind not in BODY_TYPES:
                return 415, "The request body must be application/json, multipart/form-data or application/x-www-form-urlencoded."
            if path.startswith("/api/profiles/") and path.endswith("/import") and kind != "application/json":
                return 415, "A profile import must be sent as application/json."
        return None

    @staticmethod
    def _security_headers(path, nonce):
        found = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer")]
        if not path.startswith(DOC_PATHS):
            found.append((b"content-security-policy", _csp(nonce).encode()))
        return found

    async def _send_response(self, send, status, body, path, nonce):
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *self._security_headers(path, nonce)]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
