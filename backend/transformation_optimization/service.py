import json

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_verification import LLMTransformationVerificationService, UnknownVerificationError

from .models import HIGH, LEVELS, LLMOptimizationRecommendation


class UnverifiedTransformationError(ValueError):
    """Raised when analyze() is called for an execution that hasn't been
    verified, or was verified with blocking findings."""


class MalformedRecommendationResponseError(ValueError):
    """Raised when the LLM's optimization response isn't well-formed."""


class UnknownRecommendationTargetError(ValueError):
    """Raised when a recommendation targets a cell that isn't part of this execution."""


class UnknownOptimizationAnalysisError(KeyError):
    """Raised when recommendations()/high_impact() is called before analyze() for an execution_id."""


OPTIMIZATION_SYSTEM_PROMPT = (
    "You are a performance optimization assistant reviewing already-verified, "
    "already-applied notebook code. You are given each changed cell's current "
    "source. Suggest measurable performance improvements only -- never "
    "propose a change that alters behavior, and never rewrite the source "
    "yourself. Respond with ONLY a single JSON object -- no prose, no "
    "markdown fencing -- of the form {\"recommendations\": [...]}. "
    "'recommendations' may be an empty list if no meaningful optimization "
    "exists. Each recommendation is an object with: 'target' (the exact "
    "cell_index, as a string, it concerns -- taken only from the ids listed "
    "in 'valid_targets'), 'optimization' (a short, specific description of "
    "the change), 'expected_impact' (an object with 'magnitude', one of "
    "LOW, MEDIUM, HIGH, and 'description', the concrete evidence or "
    "reasoning for the claimed improvement -- never leave this empty), "
    "'confidence' (a number between 0.0 and 1.0), and 'risk' (one of LOW, "
    "MEDIUM, HIGH -- how likely this change is to introduce a bug). Never "
    "cite a target that isn't in 'valid_targets'."
)


class LLMCodeOptimizationService:
    """Suggests, but never applies, performance optimizations for an
    already-verified transformation.

    Reuses LLMTransformationVerificationService.blocking() as the sole gate
    -- analyze() never runs for an execution that hasn't been verified, or
    that was verified with blocking findings. Every recommendation the LLM
    proposes must cite a real target cell and include non-empty
    expected_impact evidence; anything else is rejected. Like every
    generator/validator throughout this codebase, this service never
    executes or mutates notebook source -- it only ever proposes what a
    human or a later commit might choose to apply.
    """

    def __init__(
        self,
        verification_service: LLMTransformationVerificationService,
        execution_service: LLMTransformationExecutionService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._verification_service = verification_service
        self._execution_service = execution_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_optimization", required_capabilities=["chat"]
        )
        self._recommendations_by_execution = {}
        self._request_counter = 0
        self._recommendation_counter = 0

    @staticmethod
    def _build_prompt(execution, valid_targets: set) -> str:
        payload = {
            "cells": [
                {"cell_index": applied["cell_index"], "source": applied["applied_source"]}
                for applied in execution.applied_cells
            ],
            "valid_targets": sorted(valid_targets),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_targets: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedRecommendationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("recommendations"), list):
            raise MalformedRecommendationResponseError(
                "LLM response must be a JSON object with a 'recommendations' list"
            )

        recommendations = parsed["recommendations"]
        for rec in recommendations:
            if not isinstance(rec, dict):
                raise MalformedRecommendationResponseError("each recommendation must be an object")

            for key in ("target", "optimization", "expected_impact", "confidence", "risk"):
                if key not in rec:
                    raise MalformedRecommendationResponseError(f"recommendation missing required field {key!r}")

            if not isinstance(rec["target"], str) or rec["target"] not in valid_targets:
                raise UnknownRecommendationTargetError(
                    f"recommendation target {rec.get('target')!r} is not part of this execution"
                )
            if not isinstance(rec["optimization"], str) or not rec["optimization"].strip():
                raise MalformedRecommendationResponseError(
                    "recommendation 'optimization' must be a non-empty string"
                )

            impact = rec["expected_impact"]
            if not isinstance(impact, dict):
                raise MalformedRecommendationResponseError("recommendation 'expected_impact' must be an object")
            if impact.get("magnitude") not in LEVELS:
                raise MalformedRecommendationResponseError(
                    f"expected_impact 'magnitude' must be one of {sorted(LEVELS)}"
                )
            if not isinstance(impact.get("description"), str) or not impact["description"].strip():
                raise MalformedRecommendationResponseError(
                    "expected_impact 'description' must be non-empty evidence/rationale for the claimed improvement"
                )

            confidence = rec["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedRecommendationResponseError("recommendation 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedRecommendationResponseError(
                    "recommendation 'confidence' must be between 0.0 and 1.0"
                )

            if rec["risk"] not in LEVELS:
                raise MalformedRecommendationResponseError(f"recommendation 'risk' must be one of {sorted(LEVELS)}")

        return recommendations

    def analyze(self, execution_id: str) -> list:
        try:
            has_blocking = self._verification_service.blocking(execution_id)
        except UnknownVerificationError as exc:
            raise UnverifiedTransformationError(f"execution {execution_id!r} has not been verified") from exc

        if has_blocking:
            raise UnverifiedTransformationError(f"execution {execution_id!r} failed verification")

        execution = self._execution_service.get(execution_id)
        valid_targets = {str(applied["cell_index"]) for applied in execution.applied_cells}

        self._request_counter += 1
        request_id = f"code-optimization-{execution_id}-{self._request_counter}"

        self._context_service.create(request_id, system=OPTIMIZATION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(execution, valid_targets), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedRecommendationResponseError(f"LLM request failed: {decision.reason}")

        raw_recommendations = self._parse_response(response.content, valid_targets)

        created = []
        for rec in raw_recommendations:
            self._recommendation_counter += 1
            record = LLMOptimizationRecommendation(
                recommendation_id=f"optimization-{execution_id}-{self._recommendation_counter}",
                execution_id=execution_id,
                target=rec["target"],
                optimization=rec["optimization"],
                expected_impact=dict(rec["expected_impact"]),
                confidence=float(rec["confidence"]),
                risk=rec["risk"],
            )
            created.append(record)

        self._recommendations_by_execution[execution_id] = created
        return list(created)

    def _tracked(self, execution_id: str) -> list:
        try:
            return self._recommendations_by_execution[execution_id]
        except KeyError:
            raise UnknownOptimizationAnalysisError(execution_id)

    def recommendations(self, execution_id: str) -> list:
        return list(self._tracked(execution_id))

    def high_impact(self, execution_id: str) -> list:
        return [rec for rec in self._tracked(execution_id) if rec.expected_impact.get("magnitude") == HIGH]
