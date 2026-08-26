import ast
import json
from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_planning import REJECTED, REPLACE, LLMCodePatchService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import LLMCodePatchValidation

PATCH_VALIDATION_SYSTEM_PROMPT = (
    "You are a code patch validator performing a final check before a "
    "Commit #3 patch plan may be applied to generated API output. You are "
    "given the plan's target, its operations, and its rationale. Look for "
    "anything that should not be silently accepted -- an operation whose "
    "value is inconsistent with its own rationale, or a proposed value "
    "that would violate a reasonable project or compiler constraint (wrong "
    "type, structurally incompatible with what the compiler produced, "
    "etc). Respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"findings\": [...]}. 'findings' may be an "
    "empty list if the plan looks sound. Each finding is an object with: "
    "'category' (a short label for the issue), 'target' (the exact "
    "location or plan id it concerns -- taken only from the ids listed in "
    "'valid_targets'), 'message' (why this is a problem), and 'blocking' "
    "(true if the patch must not be applied until this is fixed, false if "
    "advisory). Never cite a target that isn't in 'valid_targets'. This is "
    "a read-only check -- never propose editing the generated output, the "
    "plan, or the compiler, and never assume the patch has been applied."
)


class MalformedPatchValidationResponseError(ValueError):
    """Raised when the LLM's patch-validation response isn't well-formed."""


class UnknownPatchValidationTargetError(ValueError):
    """Raised when a validation finding cites a target that doesn't exist in the plan."""


class UnknownPatchValidationError(KeyError):
    """Raised when findings()/blocking() is called before validate() for a plan_id."""


def _blocking(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": True}


def _stale_target_findings(fix_service: LLMCodeFixSuggestionService, patch_service: LLMCodePatchService, plan) -> list:
    if not fix_service.validate(plan.suggestion_id):
        return [
            _blocking(
                "STALE_TARGET",
                plan.target,
                "the fix suggestion behind this plan no longer matches the current generated-code review",
            )
        ]
    if not patch_service.validate(plan.plan_id):
        return [
            _blocking(
                "STALE_TARGET",
                plan.target,
                "this plan's operations no longer match the generated output they were planned against",
            )
        ]
    return []


def _conflicting_operations_findings(plan) -> list:
    if plan.status == REJECTED:
        return [
            _blocking(
                "CONFLICTING_OPERATIONS",
                plan.target,
                "this plan's own operations conflict with each other on the same location",
            )
        ]
    return []


def _leaf_key(location: str) -> str:
    return location.rsplit(".", 1)[-1].rsplit("[", 1)[0]


def _syntax_findings(plan) -> list:
    findings = []
    for operation in plan.operations:
        if operation["op"] != REPLACE or _leaf_key(operation["location"]) != "source":
            continue
        value = operation["value"]
        if not isinstance(value, str):
            continue
        try:
            ast.parse(value)
        except SyntaxError as exc:
            findings.append(
                _blocking(
                    "SYNTAX_ERROR", operation["location"], f"proposed value does not parse as valid Python: {exc}"
                )
            )
    return findings


class LLMCodePatchValidationService:
    """Validates a Commit #3 LLMCodePatchPlan against the actual generated
    output it targets, before that plan may ever be applied.

    Reuses Commit #2's LLMCodeFixSuggestionService.validate() and Commit
    #3's own LLMCodePatchService.validate() as the sole "does this still
    match the generated output" check -- this service never re-derives or
    re-implements that grounding logic, it only asks the existing
    validators and turns a False answer into a blocking finding. Commit
    #3's own ambiguity detection (status == REJECTED) becomes a blocking
    CONFLICTING_OPERATIONS finding the same way. Syntax validity of any
    REPLACE operation's proposed source is checked deterministically via
    `ast`, the same convention backend.transformation_validation already
    uses -- never a second parser or compiler. The LLM (same orchestration
    pipeline used throughout) is only asked for remaining project/compiler
    constraint issues, and every finding it proposes must cite a real
    target of the plan. validate() never mutates the plan, the suggestion,
    the review, the generated output, or anything upstream of it.
    """

    def __init__(
        self,
        fix_service: LLMCodeFixSuggestionService,
        patch_service: LLMCodePatchService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._fix_service = fix_service
        self._patch_service = patch_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_patch_validation", required_capabilities=["chat"]
        )
        self._validations = {}
        self._request_counter = 0
        self._validation_counter = 0

    @staticmethod
    def _build_prompt(plan, valid_targets: set) -> str:
        payload = {
            "target": plan.target,
            "operations": list(plan.operations),
            "rationale": plan.rationale,
            "valid_targets": sorted(valid_targets),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_targets: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedPatchValidationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedPatchValidationResponseError(
                "LLM response must be a JSON object with a 'findings' list"
            )

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedPatchValidationResponseError("each finding must be an object")

            for key in ("category", "target", "message", "blocking"):
                if key not in finding:
                    raise MalformedPatchValidationResponseError(f"finding missing required field {key!r}")

            if not isinstance(finding["category"], str) or not finding["category"].strip():
                raise MalformedPatchValidationResponseError("finding 'category' must be a non-empty string")
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedPatchValidationResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["blocking"], bool):
                raise MalformedPatchValidationResponseError("finding 'blocking' must be a boolean")
            if not isinstance(finding["target"], str) or finding["target"] not in valid_targets:
                raise UnknownPatchValidationTargetError(
                    f"finding target {finding.get('target')!r} is not part of this plan"
                )

        return findings

    def validate(self, plan_id: str) -> LLMCodePatchValidation:
        plan = self._patch_service.get(plan_id)

        findings = []
        findings.extend(_stale_target_findings(self._fix_service, self._patch_service, plan))
        findings.extend(_conflicting_operations_findings(plan))
        findings.extend(_syntax_findings(plan))

        valid_targets = {operation["location"] for operation in plan.operations}
        valid_targets.add(plan.target)
        valid_targets.add(plan.plan_id)

        self._request_counter += 1
        request_id = f"patch-validation-{plan_id}-{self._request_counter}"

        self._context_service.create(request_id, system=PATCH_VALIDATION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(plan, valid_targets), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedPatchValidationResponseError(f"LLM request failed: {decision.reason}")

        findings.extend(self._parse_response(response.content, valid_targets))

        valid = not any(finding["blocking"] for finding in findings)

        self._validation_counter += 1
        validation = LLMCodePatchValidation(
            validation_id=f"patch-validation-{plan_id}-{self._validation_counter}",
            plan_id=plan_id,
            valid=valid,
            findings=findings,
            checked_at=datetime.now(timezone.utc),
        )
        self._validations[plan_id] = validation
        return validation

    def _get(self, plan_id: str) -> LLMCodePatchValidation:
        try:
            return self._validations[plan_id]
        except KeyError:
            raise UnknownPatchValidationError(plan_id)

    def findings(self, plan_id: str) -> list:
        return list(self._get(plan_id).findings)

    def blocking(self, plan_id: str) -> bool:
        return any(finding["blocking"] for finding in self._get(plan_id).findings)
