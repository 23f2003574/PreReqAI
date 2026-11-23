"""Structured events for the server: request correlation, per-stage timings, cache hits and misses, PDF worker lifecycle and an error category for every failure.

Every event is one log record of the logger `prereqai.events`: its message is a JSON object (`event`, `request_id`, then the event's fields) and `record.fields` holds the same dict, so a test or a log
shipper can read it either way. A request gets an id from the client's `X-Request-ID` (kept only when it is 1 to 64 letters, digits, dots, dashes or underscores) or a new random one; it is returned in the
response's `X-Request-ID`, carried to the analysis stages, the cache and the PDF worker events through a context variable, and shared by every event of that request.

What is never logged: paper text or titles, file names and paths, learner or profile names, session ids, tokens and Authorization headers, query strings. `log_event` keeps only short strings, numbers and
booleans, and drops any field whose name suggests such content, so a careless call cannot leak it; a request is logged by its ROUTE ("/api/session/{session_id}"), never by the path it was sent."""
import contextvars
import json
import logging
import re
import secrets
from time import perf_counter

EVENT_LOGGER = "prereqai.events"
_log = logging.getLogger(EVENT_LOGGER)
_log.addHandler(logging.NullHandler())  # the command line has no handler for events and must not print them through logging's last-resort stderr handler; the server adds its own (backend/main.py)
request_id_var = contextvars.ContextVar("prereqai_request_id", default=None)
_VALID_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_FORBIDDEN = re.compile(r"authorization|token|secret|password|text|content|title|path|file|name|learner|profile|session_id|query|body|sentence|answer", re.IGNORECASE)
MAX_VALUE_CHARS = 200

ERROR_CATEGORIES = ("timeout", "input_limit", "resource_limit", "worker_failure", "invalid_input", "cancelled", "dependency", "internal")
_BY_CODE = {"timeout": "timeout", "too_many_pages": "input_limit", "page_too_large": "input_limit", "resource_exhausted": "resource_limit", "worker_failed": "worker_failure"}


def new_request_id():
    return secrets.token_hex(8)


def current_request_id():
    return request_id_var.get()


def clean_request_id(value):
    """The client's X-Request-ID when it is a plain short identifier, else None (a new one is made)."""
    return value if isinstance(value, str) and _VALID_ID.fullmatch(value) else None


def categorise(error):
    """One of ERROR_CATEGORIES for an exception, or for the code string of a PDF guard failure: timeout, input_limit (too many or too large pages), resource_limit (memory, output size), worker_failure (the
    isolated PDF worker crashed or could not read the file), invalid_input (a value the caller got wrong), cancelled, dependency (a missing package, an unreachable service), internal (anything else)."""
    if isinstance(error, str):
        return _BY_CODE.get(error, "internal")
    kind = getattr(error, "kind", None)  # a PDF guard failure names its kind
    if kind in _BY_CODE:
        return _BY_CODE[kind]
    name = type(error).__name__
    if name == "PipelineCancelled" or isinstance(error, (KeyboardInterrupt,)):
        return "cancelled"
    if isinstance(error, (TimeoutError,)):
        return "timeout"
    if isinstance(error, MemoryError):
        return "resource_limit"
    if isinstance(error, (ImportError, ConnectionError)):
        return "dependency"
    if isinstance(error, (ValueError, TypeError, KeyError)) and not name.startswith("Pipeline"):
        return "invalid_input"
    return "internal"


def _clean(fields):
    cleaned = {}
    for key, value in fields.items():
        if _FORBIDDEN.search(key) or value is None:
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            cleaned[key] = round(value, 3) if isinstance(value, float) else value
        elif isinstance(value, str):
            cleaned[key] = value[:MAX_VALUE_CHARS]
        elif isinstance(value, dict) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values()):
            cleaned[key] = {str(k)[:60]: round(v, 3) if isinstance(v, float) else v for k, v in list(value.items())[:40]}
    return cleaned


def log_event(event, level=logging.INFO, **fields):
    """Emit one structured event (see the module description); returns the dict that was logged."""
    record = {"event": event, "request_id": request_id_var.get(), **_clean(fields)}
    if _log.isEnabledFor(level):
        _log.log(level, json.dumps(record, sort_keys=True), extra={"fields": record})
    return record


class timed:
    """`with timed("stage", name="parse") as t:` logs one event with duration_ms and outcome ("ok", or "error" with the error_category) when the block ends; t.fields can be extended inside the block."""

    def __init__(self, event, **fields):
        self.event, self.fields, self.started = event, fields, None

    def __enter__(self):
        self.started = perf_counter()
        return self

    def __exit__(self, kind, error, _traceback):
        extra = {"outcome": "ok"} if error is None else {"outcome": "error", "error_category": categorise(error), "error_type": kind.__name__}
        log_event(self.event, duration_ms=(perf_counter() - self.started) * 1000, **self.fields, **extra)
        return False


class RequestIdMiddleware:
    """A pure ASGI middleware: sets the request id for the whole request, returns it in X-Request-ID and logs one `request` event (method, route, status, duration_ms)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        supplied = next((value.decode("latin-1") for key, value in scope["headers"] if key.lower() == b"x-request-id"), None)
        identifier = clean_request_id(supplied) or new_request_id()
        token = request_id_var.set(identifier)
        started, status = perf_counter(), [500]

        async def with_id(message):
            if message["type"] == "http.response.start":
                status[0] = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", identifier.encode())]
            await send(message)
        try:
            await self.app(scope, receive, with_id)
        finally:
            route = scope.get("route")
            log_event("request", method=scope["method"], route=getattr(route, "path", None) or "unmatched", status=status[0], duration_ms=(perf_counter() - started) * 1000)
            request_id_var.reset(token)
