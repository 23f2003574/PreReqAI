import json

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import OPERATIONS, READY, REJECTED, REPLACE, LLMCodePatchPlan

PATCH_PLAN_SYSTEM_PROMPT = (
    "You are a code-patch planning assistant. You are given one "
    "already-validated fix suggestion (change/rationale/risk) and the "
    "single generated-code review finding it addresses. Convert the "
    "suggestion into a precise, unambiguous patch plan for that one "
    "location -- never apply it, only describe it, and never touch "
    "anything else. Respond with ONLY a single JSON object -- no prose, no "
    "markdown fencing -- of the form {\"operations\": [...], "
    "\"rationale\": \"...\"}. 'operations' must be a non-empty list, each "
    "an object with: 'op' (REPLACE or REMOVE), 'location' (must be exactly "
    "the one location given -- never a different or invented path), and "
    "'value' (the proposed replacement for REPLACE; omit or use null for "
    "REMOVE). Propose exactly one operation unless more than one is truly "
    "necessary for this single location -- never propose two operations "
    "that conflict for the same location. 'rationale' is a short summary "
    "of why these operations satisfy the suggestion. This is a plan only "
    "-- it is never applied."
)


class MalformedPatchPlanResponseError(ValueError):
    """Raised when the LLM's patch-plan response isn't well-formed."""


class UnsupportedPatchTargetError(ValueError):
    """Raised when a proposed operation targets a location other than the suggestion's own."""


class UnvalidatedSuggestionError(ValueError):
    """Raised when plan() is called for a suggestion that isn't currently validated."""


class UnknownPatchPlanError(KeyError):
    """Raised when validate()/preview() is called for a plan_id that was never produced."""


class LLMCodePatchService:
    """Converts one validated Commit #2 LLMCodeFixSuggestion into a precise patch plan.

    Reuses Commit #2's LLMCodeFixSuggestionService.validate()/get() as the
    sole gate and source of what may be planned -- plan() never plans
    against a suggestion that isn't currently validated, and Commit #1's
    LLMGeneratedCodeReviewService.findings() for the one finding the
    suggestion addresses. The LLM (same orchestration pipeline used
    throughout) is only asked to express that one already-approved change
    as REPLACE/REMOVE operations against that single already-grounded
    location -- never a different or invented one -- so unrelated generated
    code can never be touched. Two operations that conflict on the same
    location make the plan ambiguous: it is still recorded, but with
    status REJECTED rather than READY. plan()/validate()/preview() never
    apply anything and never mutate the suggestion, the review, the
    compiler output, or anything upstream of it.
    """

    def __init__(
        self,
        review_service: LLMGeneratedCodeReviewService,
        fix_service: LLMCodeFixSuggestionService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._review_service = review_service
        self._fix_service = fix_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_patch_planning", required_capabilities=["chat"]
        )
        self._plans = {}
        self._request_counter = 0
        self._plan_counter = 0

    @staticmethod
    def _build_prompt(suggestion, finding: dict, location: str) -> str:
        payload = {
            "suggestion": {
                "target": suggestion.target,
                "change": suggestion.change,
                "rationale": suggestion.rationale,
                "risk": suggestion.risk,
            },
            "finding": finding,
            "valid_locations": [location],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, location: str):
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedPatchPlanResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("operations"), list) or not parsed["operations"]:
            raise MalformedPatchPlanResponseError(
                "LLM response must be a JSON object with a non-empty 'operations' list"
            )

        operations = parsed["operations"]
        locations_seen = []
        for operation in operations:
            if not isinstance(operation, dict):
                raise MalformedPatchPlanResponseError("each operation must be an object")
            for key in ("op", "location"):
                if key not in operation:
                    raise MalformedPatchPlanResponseError(f"operation missing required field {key!r}")
            if operation["op"] not in OPERATIONS:
                raise MalformedPatchPlanResponseError(f"operation 'op' must be one of {sorted(OPERATIONS)}")
            if operation["op"] == REPLACE and "value" not in operation:
                raise MalformedPatchPlanResponseError("REPLACE operation missing required field 'value'")
            if not isinstance(operation["location"], str) or operation["location"] != location:
                raise UnsupportedPatchTargetError(
                    f"operation location {operation.get('location')!r} does not target the suggestion's "
                    f"own generated-code location {location!r}"
                )
            locations_seen.append(operation["location"])

        if not isinstance(parsed.get("rationale"), str) or not parsed["rationale"].strip():
            raise MalformedPatchPlanResponseError("LLM response missing a non-empty 'rationale'")

        ambiguous = len(locations_seen) != len(set(locations_seen))

        clean = [
            {"op": operation["op"], "location": operation["location"], "value": operation.get("value")}
            for operation in operations
        ]
        return clean, parsed["rationale"], ambiguous

    def plan(self, suggestion_id: str) -> LLMCodePatchPlan:
        if not self._fix_service.validate(suggestion_id):
            raise UnvalidatedSuggestionError(f"suggestion {suggestion_id!r} is not currently validated")

        suggestion = self._fix_service.get(suggestion_id)
        review_findings = self._review_service.findings(suggestion.review_id)
        finding = next((f for f in review_findings if f["location"] == suggestion.target), None)
        if finding is None:
            raise UnvalidatedSuggestionError(
                f"suggestion {suggestion_id!r} no longer maps to a real finding of its review"
            )

        self._request_counter += 1
        request_id = f"code-patch-plan-{suggestion_id}-{self._request_counter}"

        self._context_service.create(request_id, system=PATCH_PLAN_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user", content=self._build_prompt(suggestion, finding, suggestion.target), priority=1
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedPatchPlanResponseError(f"LLM request failed: {decision.reason}")

        operations, rationale, ambiguous = self._parse_response(response.content, suggestion.target)

        self._plan_counter += 1
        plan = LLMCodePatchPlan(
            plan_id=f"patch-plan-{suggestion_id}-{self._plan_counter}",
            suggestion_id=suggestion_id,
            target=suggestion.target,
            operations=operations,
            rationale=rationale,
            status=REJECTED if ambiguous else READY,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def _get(self, plan_id: str) -> LLMCodePatchPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise UnknownPatchPlanError(plan_id)

    def validate(self, plan_id: str) -> bool:
        plan = self._get(plan_id)
        if plan.status != READY:
            return False
        if not self._fix_service.validate(plan.suggestion_id):
            return False

        suggestion = self._fix_service.get(plan.suggestion_id)
        return all(operation["location"] == suggestion.target for operation in plan.operations)

    def preview(self, plan_id: str) -> list:
        plan = self._get(plan_id)
        lines = []
        for operation in plan.operations:
            if operation["op"] == REPLACE:
                lines.append(f"REPLACE {operation['location']} -> {operation['value']!r}")
            else:
                lines.append(f"REMOVE {operation['location']}")
        return lines
