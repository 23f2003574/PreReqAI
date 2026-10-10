import pytest

from backend.api_generation import UnknownGeneratedImportError, generate_requirements
from test_generated_application_entrypoint import _result


def _lines(text):
    return text.splitlines()


def test_manifest_lists_exactly_what_the_generated_app_imports():
    result, _ = _result()

    lines = _lines(result.files["requirements.txt"])

    assert [line.split(">")[0] for line in lines] == ["fastapi", "pydantic", "uvicorn"]
    assert "fastapi>=0.115.0" in lines  # the generated project's own floor (not read from the host repository)
    assert "pydantic>=2.0" in lines  # project pins no pydantic; floor follows the model_dump() API used
    assert "uvicorn>=0.32.0" in lines  # the ASGI server the Dockerfile starts the app with


def test_manifest_excludes_unrelated_project_dependencies():
    result, _ = _result()

    text = result.files["requirements.txt"].lower()

    for unrelated in ("pytest", "pymupdf", "pdfplumber", "requests", "httpx", "python-multipart"):
        assert unrelated not in text


def test_manifest_is_deterministic_sorted_and_free_of_duplicates():
    result, _ = _result()

    again = generate_requirements(result.files, also=("uvicorn",))

    assert again == result.files["requirements.txt"]
    lines = _lines(again)
    assert lines == sorted(set(lines)) and again.endswith("\n")


def test_stdlib_and_package_local_imports_are_not_listed():
    files = {"app/main.py": "import json\nfrom typing import Optional\nfrom app import x\nfrom fastapi import FastAPI\n"}
    named = {"loan_quote/main.py": "import json\nfrom loan_quote import x\nfrom fastapi import FastAPI\n"}

    assert generate_requirements(files) == "fastapi>=0.115.0\n"
    assert generate_requirements(named) == "fastapi>=0.115.0\n"  # any generated package, not just `app`


def test_a_third_party_import_with_no_known_distribution_is_an_error_not_a_guess():
    with pytest.raises(UnknownGeneratedImportError):
        generate_requirements({"app/main.py": "import numpy\n"})
