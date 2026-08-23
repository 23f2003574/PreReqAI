import json
from datetime import datetime, timezone

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import CELL_TYPES, CODE_CELL, MARKDOWN_CELL, LLMNotebookAnalysis, NotebookCell


class InvalidNotebookError(ValueError):
    """Raised when the notebook handed to analyze() is not well-formed."""


class MalformedAnalysisError(ValueError):
    """Raised when the LLM's response cannot be turned into a structured analysis."""


class UnknownAnalysisError(KeyError):
    """Raised when looking up an analysis_id that was never produced."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are a static analysis assistant. Analyze the given Jupyter notebook "
    "cells and respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- containing exactly these keys: "
    "'imports' (a list of import statement strings), "
    "'functions' (a list of objects, each with a 'name' string and a "
    "'cell_index' integer), and "
    "'dependencies' (a list of external package name strings)."
)


class LLMNotebookAnalysisService:
    """Produces a structured, deterministic understanding of a notebook via the LLM.

    Reuses Commit #12's LLMRequestOrchestrationService end to end (context,
    routing, budget, cache, retry, fallback, usage, cost, audit) -- this
    service adds no provider-specific behavior, it only: deterministically
    parses notebook cells (order + code/markdown separation), asks the LLM
    for imports/functions/dependencies as JSON, and rejects anything that
    isn't a well-formed structured response.
    """

    def __init__(self, orchestration_service, context_service, route_request: LLMRouteRequest = None):
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="notebook_analysis", required_capabilities=["chat"]
        )
        self._analyses = {}
        self._latest_by_notebook = {}
        self._request_counter = 0

    @staticmethod
    def _extract_cells(notebook: dict) -> list:
        if not isinstance(notebook, dict):
            raise InvalidNotebookError("notebook must be a dict")

        notebook_id = notebook.get("notebook_id")
        if not notebook_id or not isinstance(notebook_id, str):
            raise InvalidNotebookError("notebook.notebook_id is required")

        raw_cells = notebook.get("cells")
        if not isinstance(raw_cells, list) or not raw_cells:
            raise InvalidNotebookError("notebook.cells must be a non-empty list")

        cells = []
        for index, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, dict):
                raise InvalidNotebookError(f"cell at index {index} must be a dict")

            cell_type = raw_cell.get("cell_type")
            if cell_type not in CELL_TYPES:
                raise InvalidNotebookError(
                    f"cell at index {index} has invalid cell_type {cell_type!r}; "
                    f"expected one of {sorted(CELL_TYPES)}"
                )

            source = raw_cell.get("source")
            if not isinstance(source, str):
                raise InvalidNotebookError(f"cell at index {index} source must be a string")

            cells.append(NotebookCell(index=index, cell_type=cell_type, source=source))

        return cells

    @staticmethod
    def _build_prompt(notebook_id: str, cells: list) -> str:
        payload = {
            "notebook_id": notebook_id,
            "cells": [
                {"index": cell.index, "cell_type": cell.cell_type, "source": cell.source}
                for cell in cells
            ],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedAnalysisError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict):
            raise MalformedAnalysisError("LLM response must be a JSON object")

        for key in ("imports", "dependencies", "functions"):
            if key not in parsed or not isinstance(parsed[key], list):
                raise MalformedAnalysisError(f"LLM response missing list field {key!r}")

        for entry in parsed["imports"]:
            if not isinstance(entry, str):
                raise MalformedAnalysisError("each import must be a string")

        for entry in parsed["dependencies"]:
            if not isinstance(entry, str):
                raise MalformedAnalysisError("each dependency must be a string")

        for entry in parsed["functions"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry.get("name"):
                raise MalformedAnalysisError("each function entry must be an object with a 'name' string")
            if "cell_index" in entry and not isinstance(entry["cell_index"], int):
                raise MalformedAnalysisError("function 'cell_index', if present, must be an integer")

        return parsed

    def analyze(self, notebook: dict) -> LLMNotebookAnalysis:
        cells = self._extract_cells(notebook)
        notebook_id = notebook["notebook_id"]

        self._request_counter += 1
        request_id = f"notebook-analysis-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(notebook_id, cells), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedAnalysisError(f"LLM request failed: {decision.reason}")

        parsed = self._parse_response(response.content)

        analysis = LLMNotebookAnalysis(
            analysis_id=f"analysis-{notebook_id}-{self._request_counter}",
            notebook_id=notebook_id,
            cells=cells,
            imports=list(parsed["imports"]),
            functions=list(parsed["functions"]),
            dependencies=list(parsed["dependencies"]),
            generated_at=datetime.now(timezone.utc),
        )
        self._analyses[analysis.analysis_id] = analysis
        self._latest_by_notebook[notebook_id] = analysis.analysis_id
        return analysis

    def _get(self, analysis_id: str) -> LLMNotebookAnalysis:
        try:
            return self._analyses[analysis_id]
        except KeyError:
            raise UnknownAnalysisError(analysis_id)

    def get(self, analysis_id: str) -> LLMNotebookAnalysis:
        """The full stored analysis -- lets downstream commits reuse cells/imports/functions."""
        return self._get(analysis_id)

    def get_by_notebook(self, notebook_id: str) -> LLMNotebookAnalysis:
        """The most recently produced analysis for a notebook_id."""
        try:
            analysis_id = self._latest_by_notebook[notebook_id]
        except KeyError:
            raise UnknownAnalysisError(notebook_id)
        return self._analyses[analysis_id]

    def functions(self, analysis_id: str) -> list:
        return list(self._get(analysis_id).functions)

    def dependencies(self, analysis_id: str) -> list:
        return list(self._get(analysis_id).dependencies)

    def summary(self, analysis_id: str) -> dict:
        """A structured summary -- a dict of counts, never free-form prose."""
        analysis = self._get(analysis_id)
        code_cells = [c for c in analysis.cells if c.cell_type == CODE_CELL]
        markdown_cells = [c for c in analysis.cells if c.cell_type == MARKDOWN_CELL]

        return {
            "analysis_id": analysis.analysis_id,
            "notebook_id": analysis.notebook_id,
            "cell_count": len(analysis.cells),
            "code_cell_count": len(code_cells),
            "markdown_cell_count": len(markdown_cells),
            "import_count": len(analysis.imports),
            "function_count": len(analysis.functions),
            "dependency_count": len(analysis.dependencies),
            "generated_at": analysis.generated_at,
        }
