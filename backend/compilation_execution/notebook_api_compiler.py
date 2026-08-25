import ast
import os
import re

from backend.notebook_analysis import LLMNotebookAnalysisService, UnknownAnalysisError

from .compiler import SUCCEEDED, Compiler, CompilerError, CompilerJobResult

_VALID_TYPES = frozenset({"int", "float", "str", "bool", "list", "dict", "tuple"})
_METHOD_DECORATORS = {"GET": "get", "POST": "post", "PUT": "put", "PATCH": "patch", "DELETE": "delete"}


def _pascal_case(name: str) -> str:
    parts = re.split(r"[^0-9a-zA-Z]+", name)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


class NotebookAPICompiler(Compiler):
    """The existing deterministic compiler that Commit #13's bridge was built to call.

    Never uses the LLM: it extracts each candidate function's own source
    verbatim from the Commit #1 analysis, then wraps it with a FastAPI route
    built purely from the plan's own endpoint assignment (Commit #11) and
    input/output schemas (Commits #4/#5). One router file per notebook_id is
    written to output_dir; a generated endpoint calls the embedded function
    with the request model's fields and returns its dict result as the
    response model.
    """

    def __init__(self, notebook_analysis_service: LLMNotebookAnalysisService, output_dir: str = "backend/generated"):
        self._notebook_analysis_service = notebook_analysis_service
        self._output_dir = output_dir
        self._job_counter = 0

    def compile(self, compiler_input: dict) -> CompilerJobResult:
        self._job_counter += 1
        job_id = f"compile-{compiler_input.get('plan_id', 'unknown')}-{self._job_counter}"

        notebook_id = compiler_input.get("notebook_id")
        candidates = compiler_input.get("candidates") or []
        if not notebook_id or not candidates:
            raise CompilerError("compiler input must include notebook_id and at least one candidate", job_id)

        try:
            analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        except UnknownAnalysisError as exc:
            raise CompilerError(f"no notebook analysis found for {notebook_id!r}", job_id) from exc

        sections = [self._compile_candidate(candidate, analysis, job_id) for candidate in candidates]

        content = self._render_file(notebook_id, sections)
        try:
            ast.parse(content)
        except SyntaxError as exc:
            raise CompilerError(f"generated code for {notebook_id!r} is not valid Python: {exc}", job_id) from exc

        file_path = self._write_file(notebook_id, content)

        return CompilerJobResult(
            job_id=job_id,
            status=SUCCEEDED,
            output={
                "notebook_id": notebook_id,
                "file_path": file_path,
                "endpoint_count": len(sections),
            },
        )

    @staticmethod
    def _find_function_source(analysis, function_name: str, job_id: str) -> str:
        for cell in analysis.cells:
            if cell.cell_type != "code":
                continue
            try:
                tree = ast.parse(cell.source)
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    source = ast.get_source_segment(cell.source, node)
                    if source:
                        return source
        raise CompilerError(f"function {function_name!r} not found in notebook source", job_id)

    @staticmethod
    def _check_types(fields: dict, job_id: str) -> None:
        for field, type_name in fields.items():
            if type_name not in _VALID_TYPES:
                raise CompilerError(f"field {field!r} has unsupported type {type_name!r}", job_id)

    def _compile_candidate(self, candidate: dict, analysis, job_id: str) -> str:
        function_name = candidate.get("function_name")
        if not function_name or not function_name.isidentifier():
            raise CompilerError(f"candidate has an invalid function_name: {function_name!r}", job_id)

        endpoint = candidate.get("endpoint") or {}
        method = endpoint.get("method")
        path = endpoint.get("path")
        if method not in _METHOD_DECORATORS or not path:
            raise CompilerError(
                f"candidate {candidate.get('candidate_id')!r} has no valid endpoint assignment", job_id
            )

        function_source = self._find_function_source(analysis, function_name, job_id)

        input_schema = candidate.get("input_schema") or {}
        output_schema = candidate.get("output_schema") or {}
        input_types = input_schema.get("types") or {}
        required = set(input_schema.get("required") or [])
        defaults = input_schema.get("defaults") or {}
        output_types = output_schema.get("types") or {}
        nullable = set(output_schema.get("nullable") or [])

        self._check_types(input_types, job_id)
        self._check_types(output_types, job_id)

        model_name = _pascal_case(function_name)
        request_name = f"{model_name}Request"
        response_name = f"{model_name}Response"

        request_lines = []
        for field, type_name in input_types.items():
            if field in required:
                request_lines.append(f"    {field}: {type_name}")
            elif field in defaults:
                request_lines.append(f"    {field}: {type_name} = {defaults[field]!r}")
            else:
                request_lines.append(f"    {field}: Optional[{type_name}] = None")
        if not request_lines:
            request_lines.append("    pass")

        response_lines = []
        for field, type_name in output_types.items():
            if field in nullable:
                response_lines.append(f"    {field}: Optional[{type_name}] = None")
            else:
                response_lines.append(f"    {field}: {type_name}")
        if not response_lines:
            response_lines.append("    pass")

        decorator_method = _METHOD_DECORATORS[method]

        return "\n".join(
            [
                f"# --- {function_name} ---",
                "",
                function_source,
                "",
                "",
                f"class {request_name}(BaseModel):",
                *request_lines,
                "",
                "",
                f"class {response_name}(BaseModel):",
                *response_lines,
                "",
                "",
                f'@router.{decorator_method}("{path}", response_model={response_name})',
                f"def {function_name}_endpoint(payload: {request_name}) -> {response_name}:",
                f"    result = {function_name}(**payload.dict())",
                f"    return {response_name}(**result)",
            ]
        )

    @staticmethod
    def _render_file(notebook_id: str, sections: list) -> str:
        header = (
            f'"""Generated FastAPI router for notebook {notebook_id!r}.\n\n'
            'Auto-generated by NotebookAPICompiler -- do not edit by hand.\n'
            '"""\n\n'
            "from typing import Optional\n\n"
            "from fastapi import APIRouter\n"
            "from pydantic import BaseModel\n\n"
            "router = APIRouter()\n\n\n"
        )
        return header + "\n\n\n".join(sections) + "\n"

    def _write_file(self, notebook_id: str, content: str) -> str:
        os.makedirs(self._output_dir, exist_ok=True)
        safe_name = re.sub(r"[^0-9a-zA-Z_]+", "_", notebook_id).strip("_") or "notebook"
        file_path = os.path.join(self._output_dir, f"{safe_name}_router.py")

        with open(file_path, "w") as f:
            f.write(content)

        return file_path
