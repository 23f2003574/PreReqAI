import json

from backend.api_candidates import LLMAPICandidateService
from backend.code_quality import ERROR, SEVERITIES, LLMCodeQualityService
from backend.input_schema import LLMInputSchemaService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import LLMOutputSchemaService

from .models import CATEGORIES, LLMAPIRecommendation


class MalformedRecommendationError(ValueError):
    """Raised when the LLM's recommendation response isn't well-formed."""


class UnsupportedEvidenceError(ValueError):
    """Raised when a recommendation cites evidence that doesn't exist for this candidate."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API design reviewer. You are given a notebook function's "
    "cells, its inferred input/output schemas, its dependency edges, and "
    "its code-quality findings -- collectively 'available_evidence'. Each "
    "evidence item has an 'id'. Recommend API design improvements based "
    "only on this evidence. Respond with ONLY a single JSON object -- no "
    "prose, no markdown fencing -- of the form {\"recommendations\": [...]}. "
    "Each recommendation is an object with: 'category' (one of SCHEMA, "
    "ENDPOINT, PERFORMANCE, RELIABILITY), 'change' (the specific change to "
    "make), 'rationale' (why, referencing the evidence), 'confidence' (a "
    "number between 0.0 and 1.0), 'severity' (one of INFO, WARNING, ERROR), "
    "and 'evidence_refs' (a non-empty list of the exact 'id' values from "
    "available_evidence that this recommendation is grounded in). Never cite "
    "an id that isn't in available_evidence, and never suggest editing the "
    "notebook or candidate code directly -- only the API design around it."
)


class LLMAPIRecommendationService:
    """Recommends API design improvements for a candidate (Commit #3), grounded
    in everything already known about it.

    Reuses Commit #1's notebook analysis, Commit #4/#5's input/output
    schemas, Commit #8's code-quality findings (and Commit #2's dependency
    graph when available), plus the same LLM orchestration pipeline used
    throughout. Every recommendation must cite at least one real evidence id
    drawn from that assembled evidence -- anything else is rejected. This
    service is read-only: it never edits the notebook, the candidate, its
    schemas, or generates API code.
    """

    def __init__(
        self,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        quality_service: LLMCodeQualityService,
        orchestration_service,
        context_service,
        dependency_service=None,
        route_request: LLMRouteRequest = None,
    ):
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._quality_service = quality_service
        self._dependency_service = dependency_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_recommendation", required_capabilities=["chat"]
        )
        self._recommendations_by_candidate = {}
        self._request_counter = 0
        self._recommendation_counter = 0

    def _collect_evidence(self, candidate_id: str):
        candidate = self._api_candidate_service.get(candidate_id)
        analysis = self._notebook_analysis_service.get_by_notebook(candidate.notebook_id)
        input_schema = self._input_schema_service.get(candidate_id)
        output_schema = self._output_schema_service.get(candidate_id)
        quality_findings = self._quality_service.findings(candidate.notebook_id) if self._quality_service else []
        dependencies = (
            self._dependency_service.dependencies(candidate.notebook_id) if self._dependency_service else []
        )

        evidence = []
        for cell in analysis.cells:
            evidence.append(
                {"id": f"cell:{cell.index}", "kind": "cell", "cell_type": cell.cell_type, "source": cell.source}
            )
        evidence.append({"id": "schema:input", "kind": "input_schema", "types": input_schema.types,
                          "required": input_schema.required, "defaults": input_schema.defaults,
                          "constraints": input_schema.constraints})
        evidence.append({"id": "schema:output", "kind": "output_schema", "types": output_schema.types,
                          "nullable": output_schema.nullable, "structure": output_schema.structure})
        for dep in dependencies:
            evidence.append(
                {
                    "id": f"dependency:{dep.dependency_id}",
                    "kind": "dependency",
                    "source": dep.source,
                    "target": dep.target,
                    "dependency_type": dep.dependency_type,
                }
            )
        for finding in quality_findings:
            evidence.append(
                {
                    "id": f"quality:{finding.finding_id}",
                    "kind": "quality_finding",
                    "cell_id": finding.cell_id,
                    "category": finding.category,
                    "severity": finding.severity,
                    "message": finding.message,
                }
            )

        evidence_ids = {item["id"] for item in evidence}
        return candidate, evidence, evidence_ids

    @staticmethod
    def _build_prompt(candidate, evidence: list) -> str:
        payload = {
            "function_name": candidate.function_name,
            "rationale": candidate.rationale,
            "available_evidence": evidence,
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, evidence_ids: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedRecommendationError(f"LLM response is not valid JSON: {exc}")

        if (
            not isinstance(parsed, dict)
            or not isinstance(parsed.get("recommendations"), list)
            or not parsed["recommendations"]
        ):
            raise MalformedRecommendationError(
                "LLM response must be a JSON object with a non-empty 'recommendations' list"
            )

        recommendations = parsed["recommendations"]
        for rec in recommendations:
            if not isinstance(rec, dict):
                raise MalformedRecommendationError("each recommendation must be an object")

            for key in ("category", "change", "rationale", "confidence", "severity", "evidence_refs"):
                if key not in rec:
                    raise MalformedRecommendationError(f"recommendation missing required field {key!r}")

            if rec["category"] not in CATEGORIES:
                raise MalformedRecommendationError(
                    f"recommendation category {rec['category']!r} must be one of {sorted(CATEGORIES)}"
                )
            if rec["severity"] not in SEVERITIES:
                raise MalformedRecommendationError(
                    f"recommendation severity {rec['severity']!r} must be one of {sorted(SEVERITIES)}"
                )
            if not isinstance(rec["change"], str) or not rec["change"].strip():
                raise MalformedRecommendationError("recommendation 'change' must be a non-empty string")
            if not isinstance(rec["rationale"], str) or not rec["rationale"].strip():
                raise MalformedRecommendationError("recommendation 'rationale' must be a non-empty string")

            confidence = rec["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedRecommendationError("recommendation 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedRecommendationError("recommendation 'confidence' must be between 0.0 and 1.0")

            refs = rec["evidence_refs"]
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
                raise MalformedRecommendationError(
                    "recommendation 'evidence_refs' must be a non-empty list of strings"
                )
            unsupported = [ref for ref in refs if ref not in evidence_ids]
            if unsupported:
                raise UnsupportedEvidenceError(
                    f"recommendation cites evidence that doesn't exist: {sorted(unsupported)}"
                )

        return recommendations

    def analyze(self, candidate_id: str) -> list:
        candidate, evidence, evidence_ids = self._collect_evidence(candidate_id)

        self._request_counter += 1
        request_id = f"api-recommendation-{candidate_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(candidate, evidence), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedRecommendationError(f"LLM request failed: {decision.reason}")

        raw_recommendations = self._parse_response(response.content, evidence_ids)

        created = []
        for rec in raw_recommendations:
            self._recommendation_counter += 1
            created.append(
                LLMAPIRecommendation(
                    recommendation_id=f"recommendation-{candidate_id}-{self._recommendation_counter}",
                    candidate_id=candidate_id,
                    category=rec["category"],
                    change=rec["change"],
                    rationale=rec["rationale"],
                    confidence=float(rec["confidence"]),
                    severity=rec["severity"],
                )
            )

        self._recommendations_by_candidate.setdefault(candidate_id, []).extend(created)
        return created

    def recommendations(self, candidate_id: str) -> list:
        return list(self._recommendations_by_candidate.get(candidate_id, []))

    def critical(self, candidate_id: str) -> list:
        """Recommendations severe enough to block on: severity == ERROR."""
        return [rec for rec in self.recommendations(candidate_id) if rec.severity == ERROR]
