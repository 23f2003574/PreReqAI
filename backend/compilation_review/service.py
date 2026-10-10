import json
from datetime import datetime, timezone

from backend.compilation_plan import (
    EndpointCandidateError,
    LLMCompilationPlanningService,
    MalformedPlanError,
    MissingSchemaError,
    UnresolvableDependencyError,
)
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import APPROVED, REJECTED, LLMCompilationReview

_STRUCTURED_INPUT_TYPES = {"dict", "list", "tuple"}


class MalformedReviewResponseError(ValueError):
    """Raised when the LLM's review response isn't well-formed."""


class UnknownReviewTargetError(ValueError):
    """Raised when a review finding cites a target that doesn't exist in the plan."""


class UnknownReviewError(KeyError):
    """Raised when findings()/approved() is called before review() for a plan_id."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API design reviewer performing a final check before a "
    "compiler runs. You are given a compilation plan: its candidates, their "
    "schemas, its endpoints, and its dependencies. Look for contradictions, "
    "assumptions the plan doesn't actually support, and unsafe API "
    "decisions (anything a compiler should not silently proceed with). "
    "Respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"findings\": [...]}. 'findings' may be an "
    "empty list if the plan looks sound. Each finding is an object with: "
    "'category' (a short label for the issue), 'target' (the exact id of "
    "the plan element it concerns -- a candidate_id, a 'route:<METHOD> "
    "<path>' string, or a dependency_id -- taken only from the ids listed "
    "in 'valid_targets'), 'message' (why this is a problem), and 'blocking' "
    "(true if the compiler must not proceed until this is fixed, false if "
    "it's advisory). Never cite a target that isn't in 'valid_targets'. "
    "This is a read-only review -- never propose editing the notebook, "
    "candidate, or schema directly, only flag concerns about the plan."
)


def _route_target(endpoint: dict) -> str:
    return f"route:{endpoint['method']} {endpoint['path']}"


class LLMCompilationReviewService:
    """Reviews a Commit #11 LLMCompilationPlan before it reaches a compiler.

    Reuses LLMCompilationPlanningService.validate() for the deterministic
    parts of "validate candidates, schemas, dependencies, and endpoints" --
    any failure there becomes a blocking finding instead of a raised
    exception. Route conflicts and GET-endpoints-with-structured-required-
    input are also checked deterministically. The LLM (same orchestration
    pipeline used throughout) is only asked for semantic issues --
    contradictions, unsupported assumptions, unsafe decisions -- and every
    finding it proposes must cite a real element of the plan. This service
    never writes to the plan or anything upstream of it.
    """

    def __init__(
        self,
        plan_service: LLMCompilationPlanningService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._plan_service = plan_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="compilation_review", required_capabilities=["chat"]
        )
        self._reviews_by_plan = {}
        self._request_counter = 0
        self._review_counter = 0

    @staticmethod
    def _blocking_finding(category: str, target: str, message: str) -> dict:
        return {"category": category, "target": target, "message": message, "blocking": True}

    def _deterministic_findings(self, plan) -> list:
        findings = []

        try:
            self._plan_service.validate(plan.plan_id)
        except MissingSchemaError as exc:
            findings.append(self._blocking_finding("MISSING_SCHEMA", plan.plan_id, str(exc)))
        except UnresolvableDependencyError as exc:
            findings.append(self._blocking_finding("UNRESOLVED_DEPENDENCY", plan.plan_id, str(exc)))
        except EndpointCandidateError as exc:
            findings.append(self._blocking_finding("INVALID_ENDPOINT", plan.plan_id, str(exc)))
        except MalformedPlanError as exc:
            findings.append(self._blocking_finding("INCOMPLETE_PLAN", plan.plan_id, str(exc)))

        routes = {}
        for endpoint in plan.endpoints:
            routes.setdefault((endpoint["method"], endpoint["path"]), set()).add(endpoint["candidate_id"])
        for (method, path), candidate_ids in routes.items():
            if len(candidate_ids) > 1:
                findings.append(
                    self._blocking_finding(
                        "CONFLICTING_ROUTE",
                        f"route:{method} {path}",
                        f"multiple candidates share {method} {path}: {sorted(candidate_ids)}",
                    )
                )

        for endpoint in plan.endpoints:
            if endpoint["method"] != "GET":
                continue
            input_schema = plan.schemas[endpoint["candidate_id"]]["input"]
            structured_required = [
                field for field in input_schema.required if input_schema.types[field] in _STRUCTURED_INPUT_TYPES
            ]
            if structured_required:
                findings.append(
                    self._blocking_finding(
                        "SCHEMA_CONFLICT",
                        endpoint["candidate_id"],
                        f"GET {endpoint['path']} has required structured-type input fields that cannot "
                        f"be expressed as query parameters: {structured_required}",
                    )
                )

        return findings

    @staticmethod
    def _build_prompt(plan, valid_targets: set) -> str:
        payload = {
            "candidates": [
                {"candidate_id": c.candidate_id, "function_name": c.function_name}
                for c in plan.candidates
            ],
            "schemas": {
                candidate_id: {
                    "input": {"types": s["input"].types, "required": s["input"].required},
                    "output": {"types": s["output"].types, "nullable": s["output"].nullable},
                }
                for candidate_id, s in plan.schemas.items()
            },
            "endpoints": list(plan.endpoints),
            "dependencies": [
                {"dependency_id": d.dependency_id, "source": d.source, "target": d.target, "type": d.dependency_type}
                for d in plan.dependencies
            ],
            "valid_targets": sorted(valid_targets),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_targets: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedReviewResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedReviewResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedReviewResponseError("each finding must be an object")

            for key in ("category", "target", "message", "blocking"):
                if key not in finding:
                    raise MalformedReviewResponseError(f"finding missing required field {key!r}")

            if not isinstance(finding["category"], str) or not finding["category"].strip():
                raise MalformedReviewResponseError("finding 'category' must be a non-empty string")
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedReviewResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["blocking"], bool):
                raise MalformedReviewResponseError("finding 'blocking' must be a boolean")
            if not isinstance(finding["target"], str) or finding["target"] not in valid_targets:
                raise UnknownReviewTargetError(
                    f"finding target {finding.get('target')!r} is not part of this plan"
                )

        return findings

    def review(self, plan_id: str) -> LLMCompilationReview:
        plan = self._plan_service.get(plan_id)

        findings = self._deterministic_findings(plan)

        valid_targets = {candidate.candidate_id for candidate in plan.candidates}
        valid_targets |= {_route_target(endpoint) for endpoint in plan.endpoints}
        valid_targets |= {dep.dependency_id for dep in plan.dependencies}
        valid_targets.add(plan.plan_id)

        self._request_counter += 1
        request_id = f"compilation-review-{plan_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(plan, valid_targets), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedReviewResponseError(f"LLM request failed: {decision.reason}")

        findings.extend(self._parse_response(response.content, valid_targets))

        status = REJECTED if any(finding["blocking"] for finding in findings) else APPROVED

        self._review_counter += 1
        review = LLMCompilationReview(
            review_id=f"review-{plan_id}-{self._review_counter}",
            plan_id=plan_id,
            status=status,
            findings=findings,
            reviewed_at=datetime.now(timezone.utc),
        )
        self._reviews_by_plan[plan_id] = review
        return review

    def _get(self, plan_id: str) -> LLMCompilationReview:
        try:
            return self._reviews_by_plan[plan_id]
        except KeyError:
            raise UnknownReviewError(plan_id)

    def findings(self, plan_id: str) -> list:
        return list(self._get(plan_id).findings)

    def approved(self, plan_id: str) -> bool:
        return self._get(plan_id).status == APPROVED
