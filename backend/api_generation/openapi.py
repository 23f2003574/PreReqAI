import json
import types
from pathlib import Path

from .models import LLMAPIGenerationResult

OPENAPI_FILENAME = "openapi.json"


def generated_openapi(result: LLMAPIGenerationResult) -> dict:
    """The OpenAPI document of the GENERATED application (never the host
    application's /openapi.json). It is FastAPI's own app.openapi(), derived
    from the generated routes and models: the generated module is executed
    in a throwaway module object and nothing is hand-built here."""
    module = types.ModuleType("generated_api_app")
    exec(compile(result.files["app/main.py"], "app/main.py", "exec"), module.__dict__)
    return module.app.openapi()


def write_openapi_contract(result: LLMAPIGenerationResult, output_dir) -> Path:
    """Write generated_openapi(result) to <output_dir>/openapi.json with
    sorted keys, so repeated generation produces byte-identical output."""
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / OPENAPI_FILENAME
    target.write_text(json.dumps(generated_openapi(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
