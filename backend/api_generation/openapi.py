import json
import types
from pathlib import Path

from .models import LLMAPIGenerationResult

OPENAPI_FILENAME = "openapi.json"


def openapi_document(files: dict) -> dict:
    """FastAPI's app.openapi() for the generated `app/main.py` in `files`,
    taken from a throwaway module (see generated_openapi)."""
    module = types.ModuleType("generated_api_app")
    exec(compile(files["app/main.py"], "app/main.py", "exec"), module.__dict__)
    return module.app.openapi()


def format_openapi(document: dict) -> str:
    """The deterministic text form of an OpenAPI document (sorted keys)."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def openapi_text(files: dict) -> str:
    """The deterministic text form of the generated app's OpenAPI document."""
    return format_openapi(openapi_document(files))


def generated_openapi(result: LLMAPIGenerationResult) -> dict:
    """The OpenAPI document of the GENERATED application (never the host
    application's /openapi.json). It is FastAPI's own app.openapi(), derived
    from the generated routes and models: the generated module is executed
    in a throwaway module object and nothing is hand-built here."""
    return openapi_document(result.files)


def write_openapi_contract(result: LLMAPIGenerationResult, output_dir) -> Path:
    """Write generated_openapi(result) to <output_dir>/openapi.json with
    sorted keys, so repeated generation produces byte-identical output."""
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / OPENAPI_FILENAME
    target.write_text(openapi_text(result.files), encoding="utf-8")
    return target
