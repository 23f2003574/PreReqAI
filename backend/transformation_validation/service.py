import ast
import json
from datetime import datetime, timezone

from backend.code_transformation import (
    InvalidTransformationRequestError,
    LLMCodeTransformationService,
    UnresolvableCellReferenceError,
)
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import LLMTransformationValidation


class MalformedValidationResponseError(ValueError):
    """Raised when the LLM's validation response isn't well-formed."""


class UnknownValidationTargetError(ValueError):
    """Raised when a validation finding cites a target that doesn't exist in the plan."""


class UnknownValidationError(KeyError):
    """Raised when findings()/blocking() is called before validate() for a plan_id."""


VALIDATION_SYSTEM_PROMPT = (
    "You are a code transformation validator performing a final check before "
    "a proposed transformation may be applied to notebook source. You are "
    "given a transformation plan: its transformation type, rationale, and "
    "each proposed change. Look for anything that should not be silently "
    "accepted -- behavior changes not justified by the plan's own "
    "rationale, or changes that look unsafe for their stated "
    "transformation_type. Respond with ONLY a single JSON object -- no "
    "prose, no markdown fencing -- of the form {\"findings\": [...]}. "
    "'findings' may be an empty list if the plan looks sound. Each finding "
    "is an object with: 'category' (a short label for the issue), 'target' "
    "(the exact cell_index, as a string, it concerns -- taken only from the "
    "ids listed in 'valid_targets'), 'message' (why this is a problem), and "
    "'blocking' (true if the change must not be applied until this is "
    "fixed, false if advisory). Never cite a target that isn't in "
    "'valid_targets'. This is a read-only check -- never propose editing "
    "the notebook or the plan directly, only flag concerns."
)


def _blocking(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": True}


class LLMTransformationValidationService:
    """Validates a Commit #1 LLMCodeTransformationPlan before it may ever be applied.

    Reuses LLMCodeTransformationService.validate() for the deterministic
    "do target_cells/changes still reference real cells" check -- any
    failure there becomes a blocking finding instead of a raised exception.
    Syntax validity of each proposed_source, symbol collisions with the
    rest of the notebook, and conflicts between the plan's own changes are
    also checked deterministically via `ast`. The LLM (same orchestration
    pipeline used throughout) is only asked for semantic issues; every
    finding it proposes must cite a real target cell. This service never
    writes to the plan, the notebook analysis, or anything upstream --
    validate() only ever reads them, and never touches a compiler.
    """

    def __init__(
        self,
        transformation_service: LLMCodeTransformationService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._transformation_service = transformation_service
        self._notebook_analysis_service = notebook_analysis_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="transformation_validation", required_capabilities=["chat"]
        )
        self._validations = {}
        self._request_counter = 0
        self._validation_counter = 0

    @staticmethod
    def _top_level_function_names(source: str) -> set:
        tree = ast.parse(source)
        return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    def _deterministic_findings(self, plan) -> list:
        findings = []

        try:
            self._transformation_service.validate(plan.plan_id)
        except UnresolvableCellReferenceError as exc:
            findings.append(_blocking("UNKNOWN_CELL", plan.plan_id, str(exc)))
        except InvalidTransformationRequestError as exc:
            findings.append(_blocking("INVALID_TRANSFORMATION_TYPE", plan.plan_id, str(exc)))

        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        target_cell_set = set(plan.target_cells)
        outside_functions = {
            fn["name"] for fn in analysis.functions if fn.get("cell_index") not in target_cell_set
        }

        change_symbols = {}
        for change in plan.changes:
            target = str(change["cell_index"])
            try:
                change_symbols[change["cell_index"]] = self._top_level_function_names(change["proposed_source"])
            except SyntaxError as exc:
                findings.append(_blocking("SYNTAX_ERROR", target, f"proposed_source does not parse: {exc}"))

        for cell_index, symbols in change_symbols.items():
            collisions = symbols & outside_functions
            if collisions:
                findings.append(
                    _blocking(
                        "SYMBOL_CONFLICT",
                        str(cell_index),
                        f"proposed_source defines {sorted(collisions)}, which already exists "
                        "elsewhere in the notebook",
                    )
                )

        owner_of_symbol = {}
        for cell_index, symbols in change_symbols.items():
            for symbol in symbols:
                if symbol in owner_of_symbol and owner_of_symbol[symbol] != cell_index:
                    findings.append(
                        _blocking(
                            "CONFLICTING_TRANSFORMATION",
                            str(cell_index),
                            f"cells {owner_of_symbol[symbol]} and {cell_index} both define {symbol!r} "
                            "within the same plan",
                        )
                    )
                else:
                    owner_of_symbol[symbol] = cell_index

        return findings

    @staticmethod
    def _build_prompt(plan, valid_targets: set) -> str:
        payload = {
            "transformation_type": plan.transformation_type,
            "rationale": plan.rationale,
            "confidence": plan.confidence,
            "changes": [dict(change) for change in plan.changes],
            "valid_targets": sorted(valid_targets),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_targets: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedValidationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedValidationResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedValidationResponseError("each finding must be an object")

            for key in ("category", "target", "message", "blocking"):
                if key not in finding:
                    raise MalformedValidationResponseError(f"finding missing required field {key!r}")

            if not isinstance(finding["category"], str) or not finding["category"].strip():
                raise MalformedValidationResponseError("finding 'category' must be a non-empty string")
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedValidationResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["blocking"], bool):
                raise MalformedValidationResponseError("finding 'blocking' must be a boolean")
            if not isinstance(finding["target"], str) or finding["target"] not in valid_targets:
                raise UnknownValidationTargetError(
                    f"finding target {finding.get('target')!r} is not part of this plan"
                )

        return findings

    def validate(self, plan_id: str) -> LLMTransformationValidation:
        plan = self._transformation_service.get(plan_id)

        findings = self._deterministic_findings(plan)

        valid_targets = {str(cell_index) for cell_index in plan.target_cells}
        valid_targets.add(plan.plan_id)

        self._request_counter += 1
        request_id = f"transformation-validation-{plan_id}-{self._request_counter}"

        self._context_service.create(request_id, system=VALIDATION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(plan, valid_targets), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedValidationResponseError(f"LLM request failed: {decision.reason}")

        findings.extend(self._parse_response(response.content, valid_targets))

        valid = not any(finding["blocking"] for finding in findings)

        self._validation_counter += 1
        validation = LLMTransformationValidation(
            validation_id=f"validation-{plan_id}-{self._validation_counter}",
            plan_id=plan_id,
            valid=valid,
            findings=findings,
            checked_at=datetime.now(timezone.utc),
        )
        self._validations[plan_id] = validation
        return validation

    def _get(self, plan_id: str) -> LLMTransformationValidation:
        try:
            return self._validations[plan_id]
        except KeyError:
            raise UnknownValidationError(plan_id)

    def findings(self, plan_id: str) -> list:
        return list(self._get(plan_id).findings)

    def blocking(self, plan_id: str) -> bool:
        return any(finding["blocking"] for finding in self._get(plan_id).findings)
