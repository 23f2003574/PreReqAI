import json

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import CATEGORIES, ERROR, SEVERITIES, LLMCodeFinding


class MalformedFindingError(ValueError):
    """Raised when the LLM's findings response isn't well-formed or evidence doesn't exist."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are a static code review assistant. Analyze the given Jupyter "
    "notebook cells for correctness risks and maintainability issues. "
    "Respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"findings\": [...]}. Each finding is an object "
    "with: 'cell_id' (the exact 'cell:<index>' id of the cell the issue was "
    "found in), 'category' (one of BUG, RISK, SMELL, DEAD_CODE), 'severity' "
    "(one of INFO, WARNING, ERROR), 'message' (a short description of the "
    "issue), and 'confidence' (a number between 0.0 and 1.0). Only report "
    "issues you can point to a specific cell for -- never modify or repeat "
    "back the source code itself."
)


class LLMCodeQualityService:
    """Analyzes a notebook's cells for correctness/maintainability findings (Commit #1).

    Reuses Commit #1's LLMNotebookAnalysisService for the cells a finding
    must reference, and the same LLM orchestration pipeline used throughout
    -- this service never reads or writes notebook source beyond quoting it
    in the prompt, and rejects any finding that isn't well-formed or doesn't
    point at a real cell.
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
            task="code_quality_analysis", required_capabilities=["chat"]
        )
        self._findings_by_notebook = {}
        self._request_counter = 0
        self._finding_counter = 0

    @staticmethod
    def _build_prompt(analysis) -> str:
        payload = {
            "notebook_id": analysis.notebook_id,
            "cells": [
                {"cell_id": f"cell:{cell.index}", "cell_type": cell.cell_type, "source": cell.source}
                for cell in analysis.cells
            ],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_cell_ids: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedFindingError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedFindingError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedFindingError("each finding must be an object")

            for key in ("cell_id", "category", "severity", "message", "confidence"):
                if key not in finding:
                    raise MalformedFindingError(f"finding missing required field {key!r}")

            if finding["cell_id"] not in valid_cell_ids:
                raise MalformedFindingError(
                    f"finding references cell_id {finding['cell_id']!r}, which does not exist"
                )
            if finding["category"] not in CATEGORIES:
                raise MalformedFindingError(
                    f"finding category {finding['category']!r} must be one of {sorted(CATEGORIES)}"
                )
            if finding["severity"] not in SEVERITIES:
                raise MalformedFindingError(
                    f"finding severity {finding['severity']!r} must be one of {sorted(SEVERITIES)}"
                )
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedFindingError("finding 'message' must be a non-empty string")

            confidence = finding["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedFindingError("finding 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedFindingError("finding 'confidence' must be between 0.0 and 1.0")

        return findings

    def analyze(self, analysis_id: str) -> list:
        analysis = self._notebook_analysis_service.get(analysis_id)
        notebook_id = analysis.notebook_id
        valid_cell_ids = {f"cell:{cell.index}" for cell in analysis.cells}

        self._request_counter += 1
        request_id = f"code-quality-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(analysis), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedFindingError(f"LLM request failed: {decision.reason}")

        raw_findings = self._parse_response(response.content, valid_cell_ids)

        created = []
        for finding in raw_findings:
            self._finding_counter += 1
            created.append(
                LLMCodeFinding(
                    finding_id=f"finding-{notebook_id}-{self._finding_counter}",
                    notebook_id=notebook_id,
                    cell_id=finding["cell_id"],
                    category=finding["category"],
                    severity=finding["severity"],
                    message=finding["message"],
                    confidence=float(finding["confidence"]),
                )
            )

        self._findings_by_notebook.setdefault(notebook_id, []).extend(created)
        return created

    def findings(self, notebook_id: str) -> list:
        return list(self._findings_by_notebook.get(notebook_id, []))

    def critical(self, notebook_id: str) -> list:
        """Findings severe enough to block API compilation: severity == ERROR."""
        return [finding for finding in self.findings(notebook_id) if finding.severity == ERROR]
