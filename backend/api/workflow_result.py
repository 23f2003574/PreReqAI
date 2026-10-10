"""The public result envelope of PreReqAI's workflow endpoints, so API, CLI and
UI callers read success, stage, output, warnings and failure the same way.

Success: {"status": "success", "feature", "stage", "warnings": [], ...output keys}
Failure: HTTP error status with {"status": "failure", "stage", "detail", "error": {"type", "message"},
         "hint", "warnings": []}

`detail` keeps FastAPI's usual error text, so existing clients that read it are
unaffected; the lower-level pipeline return types are not changed.
"""

from fastapi.responses import JSONResponse

SUCCESS = "success"
FAILURE = "failure"
LIMIT_EXCEEDED = "limit_exceeded"  # a resource limit stopped the run: not an ordinary failure
TIMEOUT = "timeout"  # an operation exceeded its own time limit (e.g. a download): not an ordinary failure
CANCELLED = "cancelled"  # a stopped run: distinct from a failure, same envelope keys


TERMINAL_STATUSES = (SUCCESS, FAILURE, CANCELLED, LIMIT_EXCEEDED, TIMEOUT)
REQUIRED_REPORT_KEYS = ("paper", "concepts", "prerequisites", "missing_prerequisites", "learning_plan", "readiness", "statistics")


# The HTTP status of each terminal status, so every non-success result is an HTTP error.
HTTP_STATUS = {SUCCESS: 200, FAILURE: 400, CANCELLED: 409, LIMIT_EXCEEDED: 413, TIMEOUT: 504}


def json_violations(value, path: str = "result") -> list:
    """Where `value` is not plain JSON (dicts with string keys, lists, strings,
    finite numbers, booleans, None). The public result must be plain JSON so the
    API and the CLI print the very same thing, with no adapter of their own
    converting (or stringifying) values on the way out."""
    if isinstance(value, dict):
        problems = [f"{path} has a non-string key {key!r}" for key in value if not isinstance(key, str)]
        for key, item in value.items():
            problems += json_violations(item, f"{path}.{key}")
        return problems
    if isinstance(value, list):
        return [problem for index, item in enumerate(value) for problem in json_violations(item, f"{path}[{index}]")]
    if isinstance(value, float) and value != value or value in (float("inf"), float("-inf")):
        return [f"{path} is not a finite number"]
    if value is None or isinstance(value, (str, bool, int, float)):
        return []
    return [f"{path} is a {type(value).__name__}, not plain JSON"]


def terminal_violations(outcome) -> list:
    """What makes `outcome` an invalid terminal workflow result (empty when it
    is valid). Success must carry a complete output of its own and no error;
    every other terminal status must carry no output, only the error envelope.
    Warnings never change the status. The whole result must be plain JSON
    (see json_violations)."""
    if not isinstance(outcome, dict) or outcome.get("status") not in TERMINAL_STATUSES:
        return [f"status {outcome.get('status')!r} is not a terminal status" if isinstance(outcome, dict) else "result is not a dict"]
    problems = json_violations(outcome)[:5]
    if not isinstance(outcome.get("warnings"), list):
        problems.append("warnings must be a list")
    output_keys = [key for key in ("session_id", "report", "timings") if key in outcome]
    if outcome["status"] == SUCCESS:
        if sorted(output_keys) != ["report", "session_id", "timings"]:
            problems.append("a success must carry session_id, report and timings")
        if "error" in outcome:
            problems.append("a success must not carry an error")
        report = outcome.get("report")
        if not isinstance(report, dict) or any(key not in report for key in REQUIRED_REPORT_KEYS):
            problems.append("a success must carry a complete report")
    else:
        if output_keys:
            problems.append(f"a {outcome['status']} result must not carry {output_keys}")
        if "error" not in outcome or "stage" not in outcome:
            problems.append("a non-success result must carry stage and error")
    return problems


def success_body(feature: str, stage: str, warnings=(), **output) -> dict:
    return {"status": SUCCESS, "feature": feature, "stage": stage, "warnings": list(warnings), **output}


def failure_body(stage: str, message: str, error=None, hint: str = None) -> dict:
    """A failure in the public envelope. `stage` is the stage that failed;
    `error` is the underlying exception, if there is one."""
    return {
        "status": FAILURE, "stage": stage, "detail": message,
        "error": {"type": type(error).__name__ if error is not None else None,
                  "message": str(error) if error is not None else message},
        "hint": hint, "warnings": [],
    }


def cancelled_body(stage: str, message: str, hint: str = None) -> dict:
    """The envelope of a run that was cancelled before it finished."""
    return {"status": CANCELLED, "stage": stage, "detail": message, "error": None, "hint": hint, "warnings": []}


def limit_exceeded_body(stage: str, message: str, hint: str = None) -> dict:
    """The envelope of a run stopped because it hit a configured resource limit."""
    return {
        "status": LIMIT_EXCEEDED, "stage": stage, "detail": message,
        "error": {"type": "AnalysisLimitExceeded", "message": message}, "hint": hint, "warnings": [],
    }


def timeout_body(stage: str, message: str, error=None, hint: str = None) -> dict:
    """The envelope of a run stopped because an operation timed out."""
    return {
        "status": TIMEOUT, "stage": stage, "detail": message,
        "error": {"type": type(error).__name__ if error is not None else "TimeoutError",
                  "message": str(error) if error is not None else message},
        "hint": hint, "warnings": [],
    }


def failure_response(status_code: int, stage: str, message: str, error=None, hint: str = None) -> JSONResponse:
    """failure_body() as an HTTP error response."""
    return JSONResponse(status_code=status_code, content=failure_body(stage, message, error, hint))
