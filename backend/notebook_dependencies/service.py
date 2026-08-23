import json
from datetime import datetime, timezone

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import DEPENDENCY_TYPES, LLMNotebookDependency

_NODE_PREFIXES = ("cell", "import", "function", "data", "model")


class MalformedDependencyResponseError(ValueError):
    """Raised when the LLM's dependency response is not a well-formed edge list."""


class CyclicDependencyError(ValueError):
    """Raised when the proposed edges would make a notebook's execution order invalid."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are a static analysis assistant. Given a notebook's structured analysis "
    "(cells, imports, functions), identify the dependency relationships between "
    "them and respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"edges\": [...]}. Each edge is an object with: "
    "'source' (a node id), 'target' (a node id that depends on source), "
    "'dependency_type' (one of IMPORT, FUNCTION, DATA, MODEL), and "
    "'confidence' (a number between 0.0 and 1.0). Node ids must be one of: "
    "'cell:<index>', 'import:<index>', 'function:<name>', 'data:<label>', "
    "'model:<label>', referencing the cells/imports/functions given below or, "
    "for data/model, a short label for the artifact."
)


class LLMNotebookDependencyService:
    """Builds a per-notebook dependency graph from a Commit #1 notebook analysis.

    Reuses Commit #1's LLMNotebookAnalysisService for the cells/imports/functions
    that ground node ids, and the same LLM orchestration pipeline (context,
    routing, budget, cache, retry, fallback, usage, cost, audit) used there --
    this service adds no provider-specific behavior, it only asks the LLM for
    edges and rejects anything that isn't a well-formed, acyclic, grounded graph.
    """

    def __init__(
        self,
        notebook_analysis_service: LLMNotebookAnalysisService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._notebook_analysis_service = notebook_analysis_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="notebook_dependency_analysis", required_capabilities=["chat"]
        )
        self._edges_by_notebook = {}
        self._request_counter = 0
        self._dependency_counter = 0

    @staticmethod
    def _qualify(notebook_id: str, local_id: str) -> str:
        return f"{notebook_id}::{local_id}"

    @staticmethod
    def _validate_node(local_id, analysis) -> None:
        if not isinstance(local_id, str) or ":" not in local_id:
            raise MalformedDependencyResponseError(f"node id {local_id!r} is not a valid node reference")

        prefix, _, rest = local_id.partition(":")
        if prefix not in _NODE_PREFIXES or not rest:
            raise MalformedDependencyResponseError(f"node id {local_id!r} is not a valid node reference")

        if prefix == "cell":
            valid_indices = {cell.index for cell in analysis.cells}
            if not rest.isdigit() or int(rest) not in valid_indices:
                raise MalformedDependencyResponseError(f"node id {local_id!r} does not exist: no such cell")
        elif prefix == "import":
            if not rest.isdigit() or not (0 <= int(rest) < len(analysis.imports)):
                raise MalformedDependencyResponseError(f"node id {local_id!r} does not exist: no such import")
        elif prefix == "function":
            names = {fn["name"] for fn in analysis.functions}
            if rest not in names:
                raise MalformedDependencyResponseError(f"node id {local_id!r} does not exist: no such function")
        # "data" and "model" nodes are artifacts the LLM discovers rather than
        # ones pre-declared in the analysis, so any non-empty label is accepted.

    @staticmethod
    def _build_prompt(analysis) -> str:
        payload = {
            "notebook_id": analysis.notebook_id,
            "cells": [
                {"index": cell.index, "cell_type": cell.cell_type, "source": cell.source}
                for cell in analysis.cells
            ],
            "imports": list(analysis.imports),
            "functions": list(analysis.functions),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedDependencyResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("edges"), list):
            raise MalformedDependencyResponseError("LLM response must be a JSON object with an 'edges' list")

        edges = parsed["edges"]
        for edge in edges:
            if not isinstance(edge, dict):
                raise MalformedDependencyResponseError("each edge must be an object")

            for key in ("source", "target", "dependency_type", "confidence"):
                if key not in edge:
                    raise MalformedDependencyResponseError(f"edge missing required field {key!r}")

            if not isinstance(edge["source"], str) or not isinstance(edge["target"], str):
                raise MalformedDependencyResponseError("edge 'source'/'target' must be strings")

            if edge["dependency_type"] not in DEPENDENCY_TYPES:
                raise MalformedDependencyResponseError(
                    f"edge dependency_type {edge['dependency_type']!r} must be one of {sorted(DEPENDENCY_TYPES)}"
                )

            confidence = edge["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedDependencyResponseError("edge 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedDependencyResponseError("edge 'confidence' must be between 0.0 and 1.0")

        return edges

    @staticmethod
    def _check_acyclic(existing: list, new_edges: list, notebook_id: str) -> None:
        adjacency = {}
        for dep in existing:
            adjacency.setdefault(dep.source, set()).add(dep.target)
        for edge in new_edges:
            source = LLMNotebookDependencyService._qualify(notebook_id, edge["source"])
            target = LLMNotebookDependencyService._qualify(notebook_id, edge["target"])
            adjacency.setdefault(source, set()).add(target)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adjacency}

        def visit(node, path):
            color[node] = GRAY
            for neighbor in adjacency.get(node, ()):
                if color.get(neighbor, WHITE) == GRAY:
                    cycle = " -> ".join(path + [neighbor])
                    raise CyclicDependencyError(
                        f"cyclic dependency detected in notebook {notebook_id!r}: {cycle}"
                    )
                if color.get(neighbor, WHITE) == WHITE:
                    visit(neighbor, path + [neighbor])
            color[node] = BLACK

        for node in list(adjacency):
            if color[node] == WHITE:
                visit(node, [node])

    def analyze(self, analysis_id: str) -> list:
        analysis = self._notebook_analysis_service.get(analysis_id)
        notebook_id = analysis.notebook_id

        self._request_counter += 1
        request_id = f"notebook-dependency-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(analysis), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedDependencyResponseError(f"LLM request failed: {decision.reason}")

        raw_edges = self._parse_response(response.content)
        for edge in raw_edges:
            self._validate_node(edge["source"], analysis)
            self._validate_node(edge["target"], analysis)

        existing = self._edges_by_notebook.get(notebook_id, [])
        self._check_acyclic(existing, raw_edges, notebook_id)

        created = []
        for edge in raw_edges:
            self._dependency_counter += 1
            dependency = LLMNotebookDependency(
                dependency_id=f"dependency-{notebook_id}-{self._dependency_counter}",
                notebook_id=notebook_id,
                source=self._qualify(notebook_id, edge["source"]),
                target=self._qualify(notebook_id, edge["target"]),
                dependency_type=edge["dependency_type"],
                confidence=float(edge["confidence"]),
            )
            created.append(dependency)

        self._edges_by_notebook.setdefault(notebook_id, []).extend(created)
        return created

    def dependencies(self, notebook_id: str) -> list:
        return list(self._edges_by_notebook.get(notebook_id, []))

    def upstream(self, node_id: str) -> list:
        """Direct predecessors: edges where node_id is the target."""
        return [
            dep
            for deps in self._edges_by_notebook.values()
            for dep in deps
            if dep.target == node_id
        ]

    def downstream(self, node_id: str) -> list:
        """Direct successors: edges where node_id is the source."""
        return [
            dep
            for deps in self._edges_by_notebook.values()
            for dep in deps
            if dep.source == node_id
        ]
