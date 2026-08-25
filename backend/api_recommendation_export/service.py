import json
import re

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService, UnknownRecommendationError
from backend.api_recommendation_orchestration import LLMAPIRecommendationDecision
from backend.input_schema import LLMInputSchemaService
from backend.output_schema import LLMOutputSchemaService

SUPPORTED_FORMATS = frozenset({"json"})


class UnsupportedFormatError(ValueError):
    """Raised when export() is called with a format other than one this
    project's existing serialization conventions actually support."""


class DecisionNotApprovedError(ValueError):
    """Raised when export() is called for a decision that isn't approved --
    a rejected decision can never be exported as an approved plan."""


class MalformedDecisionError(ValueError):
    """Raised when a decision references a recommendation or candidate that
    can no longer be resolved against the real pipeline state."""


class MalformedExportError(ValueError):
    """Raised when validate_export() is given a payload that isn't a
    well-formed export of an approved decision."""


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
)


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return "[REDACTED]"
    return text


def _redact_finding(finding: dict) -> dict:
    return {
        "source": finding["source"],
        "endpoint": finding["endpoint"],
        "category": finding["category"],
        "message": _redact(finding["message"]),
    }


class LLMAPIRecommendationExportService:
    """Exposes an approved Commit #13 decision as a stable, serializable
    artifact using this project's own JSON convention
    (backend.serialization.PaperSerializer's dataclasses.asdict() -> JSON
    approach, applied here to a decision instead of a Paper).

    Reuses LLMAPIExposureService, backend.api_candidates, and
    backend.input_schema/backend.output_schema purely for reads: export()
    never regenerates a recommendation or a schema, it only re-resolves the
    exact recommendation_ids the decision already recorded and reports
    what those services already have. Only an approved decision (Commit
    #13's own gate) can ever be exported, and every free-text message is
    passed through the same secret-redaction check used elsewhere in this
    codebase before it leaves this service. Nothing here mutates the
    decision, the recommendations, the schemas, or the compiler.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        api_candidate_service: LLMAPICandidateService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
    ):
        self._exposure_service = exposure_service
        self._api_candidate_service = api_candidate_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service

    def _export_recommendation(self, recommendation_id: str) -> dict:
        try:
            notebook_id = self._exposure_service.notebook_id_for(recommendation_id)
        except UnknownRecommendationError as exc:
            raise MalformedDecisionError(
                f"decision references unknown recommendation {recommendation_id!r}"
            ) from exc

        recommendation = next(
            (
                r
                for r in self._exposure_service.recommendations(notebook_id)
                if r.recommendation_id == recommendation_id
            ),
            None,
        )
        if recommendation is None:
            raise MalformedDecisionError(f"decision references unknown recommendation {recommendation_id!r}")

        candidate = next(
            (
                c
                for c in self._api_candidate_service.candidates(notebook_id)
                if c.function_name == recommendation.function_name
            ),
            None,
        )
        if candidate is None:
            raise MalformedDecisionError(
                f"recommendation {recommendation_id!r} has no registered API candidate"
            )

        input_schema = self._input_schema_service.get(candidate.candidate_id)
        output_schema = self._output_schema_service.get(candidate.candidate_id)

        return {
            "recommendation_id": recommendation.recommendation_id,
            "function_name": recommendation.function_name,
            "endpoint": f"{recommendation.method} {recommendation.endpoint_name}",
            "method": recommendation.method,
            "endpoint_name": recommendation.endpoint_name,
            "schema": {
                "input": {
                    "types": input_schema.types,
                    "required": input_schema.required,
                    "defaults": input_schema.defaults,
                },
                "output": {
                    "types": output_schema.types,
                    "nullable": output_schema.nullable,
                    "structure": output_schema.structure,
                },
            },
        }

    def export(self, decision: LLMAPIRecommendationDecision, format: str) -> str:
        if format not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"format {format!r} is not supported; must be one of {sorted(SUPPORTED_FORMATS)}"
            )

        if not decision.approved:
            raise DecisionNotApprovedError(
                f"decision {decision.decision_id!r} is not approved; only approved decisions can be exported"
            )

        payload = {
            "format": format,
            "notebook_id": decision.notebook_id,
            "decision_id": decision.decision_id,
            "approved": decision.approved,
            "recommendations": [self._export_recommendation(rid) for rid in decision.recommendations],
            "warnings": [_redact_finding(w) for w in decision.warnings],
            "blocking_findings": [_redact_finding(b) for b in decision.blocking_findings],
            "created_at": decision.created_at.isoformat(),
        }

        return json.dumps(payload, sort_keys=True, indent=2)

    def validate_export(self, payload: str) -> bool:
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise MalformedExportError(f"export payload is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise MalformedExportError("export payload must be a JSON object")

        for key in (
            "format",
            "notebook_id",
            "decision_id",
            "approved",
            "recommendations",
            "warnings",
            "blocking_findings",
            "created_at",
        ):
            if key not in parsed:
                raise MalformedExportError(f"export payload missing required field {key!r}")

        if parsed["format"] not in SUPPORTED_FORMATS:
            raise MalformedExportError(f"export payload 'format' must be one of {sorted(SUPPORTED_FORMATS)}")

        if parsed["approved"] is not True:
            raise MalformedExportError("export payload does not represent an approved decision")

        if not isinstance(parsed["recommendations"], list) or not parsed["recommendations"]:
            raise MalformedExportError("export payload must include at least one recommendation")

        for recommendation in parsed["recommendations"]:
            for key in ("recommendation_id", "function_name", "endpoint", "method", "endpoint_name", "schema"):
                if key not in recommendation:
                    raise MalformedExportError(f"exported recommendation missing required field {key!r}")
            schema = recommendation["schema"]
            if not isinstance(schema, dict) or "input" not in schema or "output" not in schema:
                raise MalformedExportError("exported recommendation 'schema' must include 'input' and 'output'")

        return True
