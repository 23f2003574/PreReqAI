import json
from datetime import datetime, timezone

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import TRANSFORMATION_TYPES, LLMCodeTransformationPlan


class InvalidTransformationRequestError(ValueError):
    """Raised when plan() is given a malformed request (bad transformation_type,
    empty/duplicate target_cells, or missing instructions)."""


class UnresolvableCellReferenceError(ValueError):
    """Raised when a target cell or proposed change references a cell that
    doesn't exist in the notebook -- at plan-build time or at validate() time."""


class MalformedTransformationResponseError(ValueError):
    """Raised when the LLM's transformation response isn't well-formed."""


class UnknownTransformationPlanError(KeyError):
    """Raised when looking up a plan_id that was never built."""


TRANSFORMATION_SYSTEM_PROMPT = (
    "You are a code transformation planning assistant. You are given one or "
    "more notebook cells (by index) and an instruction describing how they "
    "should be transformed. Propose a plan -- never rewrite anything "
    "directly, and never assume it has been applied. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"changes\": [...], \"rationale\": \"...\", \"confidence\": 0.0} "
    "where 'changes' is a non-empty list, one entry per affected cell, each "
    "an object with: 'cell_index' (must be one of the given target cell "
    "indices), 'description' (a short summary of what would change), and "
    "'proposed_source' (the full proposed replacement source for that cell "
    "-- a plan only, never applied). 'rationale' is a short overall "
    "justification string, and 'confidence' is a float between 0 and 1."
)


class LLMCodeTransformationService:
    """Plans notebook code transformations without ever mutating source.

    Reuses the same LLM orchestration pipeline (context, routing, budget,
    cache, retry, fallback, usage, cost, audit) and the Commit #1 notebook
    analysis used throughout: plan() only ever reads a notebook's analysis
    to check that requested/proposed cell references are real, it never
    writes to the analysis, a cell, or anything else upstream. The plan it
    produces is immutable and reviewable via validate()/preview(); applying
    a plan (if ever built) is deliberately out of scope here.
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
            task="code_transformation_planning", required_capabilities=["chat"]
        )
        self._plans = {}
        self._request_counter = 0
        self._plan_counter = 0

    @staticmethod
    def _validate_request(request: dict) -> tuple:
        if not isinstance(request, dict):
            raise InvalidTransformationRequestError("request must be a dict")

        transformation_type = request.get("transformation_type")
        if transformation_type not in TRANSFORMATION_TYPES:
            raise InvalidTransformationRequestError(
                f"transformation_type must be one of {sorted(TRANSFORMATION_TYPES)}, "
                f"got {transformation_type!r}"
            )

        target_cells = request.get("target_cells")
        if not isinstance(target_cells, list) or not target_cells:
            raise InvalidTransformationRequestError("target_cells must be a non-empty list")
        if any(not isinstance(i, int) or isinstance(i, bool) for i in target_cells):
            raise InvalidTransformationRequestError("target_cells must be a list of integer cell indices")
        if len(set(target_cells)) != len(target_cells):
            raise InvalidTransformationRequestError("target_cells must not contain duplicates")

        instructions = request.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            raise InvalidTransformationRequestError("instructions must be a non-empty string")

        return transformation_type, target_cells, instructions

    @staticmethod
    def _build_prompt(analysis, target_cells: list, transformation_type: str, instructions: str) -> str:
        cells_by_index = {cell.index: cell for cell in analysis.cells}
        payload = {
            "transformation_type": transformation_type,
            "instructions": instructions,
            "cells": [
                {"cell_index": i, "cell_type": cells_by_index[i].cell_type, "source": cells_by_index[i].source}
                for i in target_cells
            ],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, target_cell_set: set) -> tuple:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedTransformationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict):
            raise MalformedTransformationResponseError("LLM response must be a JSON object")

        raw_changes = parsed.get("changes")
        if not isinstance(raw_changes, list) or not raw_changes:
            raise MalformedTransformationResponseError("LLM response must include a non-empty 'changes' list")

        seen_cells = set()
        changes = []
        for change in raw_changes:
            if not isinstance(change, dict):
                raise MalformedTransformationResponseError("each change must be an object")
            for key in ("cell_index", "description", "proposed_source"):
                if key not in change:
                    raise MalformedTransformationResponseError(f"change missing required field {key!r}")

            cell_index = change["cell_index"]
            if not isinstance(cell_index, int) or isinstance(cell_index, bool):
                raise MalformedTransformationResponseError("change 'cell_index' must be an integer")
            if cell_index not in target_cell_set:
                raise UnresolvableCellReferenceError(
                    f"change references cell_index {cell_index}, which is not one of the target cells"
                )
            if cell_index in seen_cells:
                raise MalformedTransformationResponseError(f"duplicate change for cell_index {cell_index}")
            seen_cells.add(cell_index)

            description = change["description"]
            if not isinstance(description, str) or not description.strip():
                raise MalformedTransformationResponseError("change 'description' must be a non-empty string")

            proposed_source = change["proposed_source"]
            if not isinstance(proposed_source, str) or not proposed_source.strip():
                raise MalformedTransformationResponseError("change 'proposed_source' must be a non-empty string")

            changes.append(
                {"cell_index": cell_index, "description": description, "proposed_source": proposed_source}
            )

        rationale = parsed.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise MalformedTransformationResponseError("LLM response must include a non-empty 'rationale' string")

        confidence = parsed.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not (0.0 <= confidence <= 1.0)
        ):
            raise MalformedTransformationResponseError(
                "LLM response 'confidence' must be a number between 0 and 1"
            )

        return changes, rationale, float(confidence)

    def plan(self, notebook_id: str, request: dict) -> LLMCodeTransformationPlan:
        transformation_type, target_cells, instructions = self._validate_request(request)

        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        valid_cell_indices = {cell.index for cell in analysis.cells}
        missing = sorted(i for i in target_cells if i not in valid_cell_indices)
        if missing:
            raise UnresolvableCellReferenceError(
                f"target_cells reference cells that don't exist in notebook {notebook_id!r}: {missing}"
            )

        target_cell_set = set(target_cells)

        self._request_counter += 1
        request_id = f"code-transformation-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=TRANSFORMATION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(analysis, target_cells, transformation_type, instructions),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedTransformationResponseError(f"LLM request failed: {decision.reason}")

        changes, rationale, confidence = self._parse_response(response.content, target_cell_set)

        self._plan_counter += 1
        plan = LLMCodeTransformationPlan(
            plan_id=f"transformation-{notebook_id}-{self._plan_counter}",
            notebook_id=notebook_id,
            target_cells=tuple(target_cells),
            transformation_type=transformation_type,
            changes=tuple(changes),
            rationale=rationale,
            confidence=confidence,
            generated_at=datetime.now(timezone.utc),
        )
        self._plans[plan.plan_id] = plan
        return plan

    def _get(self, plan_id: str) -> LLMCodeTransformationPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise UnknownTransformationPlanError(plan_id)

    def get(self, plan_id: str) -> LLMCodeTransformationPlan:
        """The full stored plan -- lets downstream commits reuse target_cells/changes."""
        return self._get(plan_id)

    def validate(self, plan_id: str) -> bool:
        """Re-checks a plan's cell references against the notebook's current analysis.

        Purely deterministic (no LLM call): a plan built against an earlier
        analysis can go stale if the notebook has since been re-analyzed
        with different cells. This never mutates the plan or the analysis.
        """
        plan = self._get(plan_id)

        if plan.transformation_type not in TRANSFORMATION_TYPES:
            raise InvalidTransformationRequestError(
                f"plan {plan_id!r} has an invalid transformation_type: {plan.transformation_type!r}"
            )

        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        valid_cell_indices = {cell.index for cell in analysis.cells}

        missing_targets = sorted(i for i in plan.target_cells if i not in valid_cell_indices)
        if missing_targets:
            raise UnresolvableCellReferenceError(
                f"plan {plan_id!r} target_cells reference cells that no longer exist: {missing_targets}"
            )

        target_cell_set = set(plan.target_cells)
        for change in plan.changes:
            if change["cell_index"] not in target_cell_set:
                raise UnresolvableCellReferenceError(
                    f"plan {plan_id!r} has a change for cell {change['cell_index']} outside its target_cells"
                )
            if change["cell_index"] not in valid_cell_indices:
                raise UnresolvableCellReferenceError(
                    f"plan {plan_id!r} has a change referencing a cell that no longer exists: "
                    f"{change['cell_index']}"
                )

        return True

    def preview(self, plan_id: str) -> tuple:
        """A read-only, side-effect-free rendering of what applying this plan would change.

        Pairs each proposed change with the target cell's current source --
        it never writes to the notebook, the analysis, or the plan itself.
        """
        plan = self._get(plan_id)
        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        cells_by_index = {cell.index: cell for cell in analysis.cells}

        entries = []
        for change in plan.changes:
            cell = cells_by_index.get(change["cell_index"])
            if cell is None:
                raise UnresolvableCellReferenceError(
                    f"plan {plan_id!r} has a change referencing a cell that no longer exists: "
                    f"{change['cell_index']}"
                )
            entries.append(
                {
                    "cell_index": change["cell_index"],
                    "original_source": cell.source,
                    "proposed_source": change["proposed_source"],
                    "description": change["description"],
                }
            )
        return tuple(entries)
