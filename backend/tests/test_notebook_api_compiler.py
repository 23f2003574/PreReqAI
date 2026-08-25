import ast

import pytest

from backend.compilation_execution import CompilerError, NotebookAPICompiler
from backend.notebook_analysis.models import LLMNotebookAnalysis, NotebookCell


class FakeNotebookAnalysisService:
    """A minimal stand-in exposing only what NotebookAPICompiler calls."""

    def __init__(self, analyses_by_notebook: dict):
        self._analyses_by_notebook = analyses_by_notebook

    def get_by_notebook(self, notebook_id: str) -> LLMNotebookAnalysis:
        try:
            return self._analyses_by_notebook[notebook_id]
        except KeyError:
            from backend.notebook_analysis import UnknownAnalysisError

            raise UnknownAnalysisError(notebook_id)


def make_analysis(notebook_id: str, cell_sources: list) -> LLMNotebookAnalysis:
    cells = [
        NotebookCell(index=i, cell_type="code", source=source) for i, source in enumerate(cell_sources)
    ]
    return LLMNotebookAnalysis(
        analysis_id=f"analysis-{notebook_id}",
        notebook_id=notebook_id,
        cells=cells,
        imports=[],
        functions=[],
        dependencies=[],
        generated_at=None,
    )


def add_candidate(candidate_id="cand-1"):
    return {
        "candidate_id": candidate_id,
        "function_name": "add",
        "endpoint": {"candidate_id": candidate_id, "method": "POST", "path": "/add"},
        "input_schema": {"types": {"a": "int", "b": "int"}, "required": ["a", "b"], "defaults": {}},
        "output_schema": {"types": {"sum": "int"}, "nullable": []},
    }


def build_compiler(analyses: dict, tmp_path):
    service = FakeNotebookAnalysisService(analyses)
    return NotebookAPICompiler(service, output_dir=str(tmp_path))


def test_compile_writes_a_valid_router_file(tmp_path):
    analysis = make_analysis("nb-1", ["def add(a: int, b: int) -> dict:\n    return {'sum': a + b}\n"])
    compiler = build_compiler({"nb-1": analysis}, tmp_path)

    result = compiler.compile({"notebook_id": "nb-1", "plan_id": "plan-1", "candidates": [add_candidate()]})

    assert result.status == "SUCCEEDED"
    assert result.output["endpoint_count"] == 1
    file_path = result.output["file_path"]

    with open(file_path) as f:
        content = f.read()

    ast.parse(content)
    assert "def add(a: int, b: int) -> dict:" in content
    assert "class AddRequest(BaseModel):" in content
    assert "class AddResponse(BaseModel):" in content
    assert '@router.post("/add", response_model=AddResponse)' in content
    assert "def add_endpoint(payload: AddRequest) -> AddResponse:" in content
    assert "result = add(**payload.dict())" in content


def test_compile_marks_optional_fields_without_default(tmp_path):
    analysis = make_analysis(
        "nb-2", ["def greet(name: str) -> dict:\n    return {'message': 'hi ' + name, 'shout': None}\n"]
    )
    candidate = {
        "candidate_id": "cand-2",
        "function_name": "greet",
        "endpoint": {"candidate_id": "cand-2", "method": "GET", "path": "/greet"},
        "input_schema": {
            "types": {"name": "str", "loud": "bool"},
            "required": ["name"],
            "defaults": {"loud": False},
        },
        "output_schema": {"types": {"message": "str", "shout": "str"}, "nullable": ["shout"]},
    }
    compiler = build_compiler({"nb-2": analysis}, tmp_path)

    result = compiler.compile({"notebook_id": "nb-2", "plan_id": "plan-2", "candidates": [candidate]})

    with open(result.output["file_path"]) as f:
        content = f.read()

    assert "name: str" in content
    assert "loud: bool = False" in content
    assert "shout: Optional[str] = None" in content


def test_compile_combines_multiple_candidates_into_one_file(tmp_path):
    analysis = make_analysis(
        "nb-3",
        [
            "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}\n",
            "def sub(a: int, b: int) -> dict:\n    return {'diff': a - b}\n",
        ],
    )
    sub_candidate = {
        "candidate_id": "cand-4",
        "function_name": "sub",
        "endpoint": {"candidate_id": "cand-4", "method": "POST", "path": "/sub"},
        "input_schema": {"types": {"a": "int", "b": "int"}, "required": ["a", "b"], "defaults": {}},
        "output_schema": {"types": {"diff": "int"}, "nullable": []},
    }
    compiler = build_compiler({"nb-3": analysis}, tmp_path)

    result = compiler.compile(
        {"notebook_id": "nb-3", "plan_id": "plan-3", "candidates": [add_candidate(), sub_candidate]}
    )

    assert result.output["endpoint_count"] == 2
    with open(result.output["file_path"]) as f:
        content = f.read()

    ast.parse(content)
    assert "def add_endpoint" in content
    assert "def sub_endpoint" in content


def test_compile_raises_when_function_source_is_missing(tmp_path):
    analysis = make_analysis("nb-4", ["x = 1\n"])
    compiler = build_compiler({"nb-4": analysis}, tmp_path)

    with pytest.raises(CompilerError):
        compiler.compile({"notebook_id": "nb-4", "plan_id": "plan-4", "candidates": [add_candidate()]})


def test_compile_raises_when_candidate_has_no_endpoint(tmp_path):
    analysis = make_analysis("nb-5", ["def add(a: int, b: int) -> dict:\n    return {'sum': a + b}\n"])
    candidate = add_candidate()
    candidate["endpoint"] = None
    compiler = build_compiler({"nb-5": analysis}, tmp_path)

    with pytest.raises(CompilerError):
        compiler.compile({"notebook_id": "nb-5", "plan_id": "plan-5", "candidates": [candidate]})


def test_compile_raises_for_unsupported_type(tmp_path):
    analysis = make_analysis("nb-6", ["def add(a, b) -> dict:\n    return {'sum': a + b}\n"])
    candidate = add_candidate()
    candidate["input_schema"]["types"]["a"] = "complex"
    compiler = build_compiler({"nb-6": analysis}, tmp_path)

    with pytest.raises(CompilerError):
        compiler.compile({"notebook_id": "nb-6", "plan_id": "plan-6", "candidates": [candidate]})


def test_compile_raises_when_notebook_analysis_is_unknown(tmp_path):
    compiler = build_compiler({}, tmp_path)

    with pytest.raises(CompilerError):
        compiler.compile({"notebook_id": "missing-nb", "plan_id": "plan-7", "candidates": [add_candidate()]})


def test_compile_raises_for_empty_candidates(tmp_path):
    analysis = make_analysis("nb-8", ["def add(a: int, b: int) -> dict:\n    return {'sum': a + b}\n"])
    compiler = build_compiler({"nb-8": analysis}, tmp_path)

    with pytest.raises(CompilerError):
        compiler.compile({"notebook_id": "nb-8", "plan_id": "plan-8", "candidates": []})
