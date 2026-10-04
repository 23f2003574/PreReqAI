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


def success_body(feature: str, stage: str, warnings=(), **output) -> dict:
    return {"status": SUCCESS, "feature": feature, "stage": stage, "warnings": list(warnings), **output}


def failure_response(status_code: int, stage: str, message: str, error=None, hint: str = None) -> JSONResponse:
    """A failure in the public envelope. `stage` is the stage that failed;
    `error` is the underlying exception, if there is one."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": FAILURE, "stage": stage, "detail": message,
            "error": {"type": type(error).__name__ if error is not None else None, "message": str(error) if error is not None else message},
            "hint": hint, "warnings": [],
        },
    )
