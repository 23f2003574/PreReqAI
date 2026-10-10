from copy import deepcopy

from ..context_freshness import FRESH, LLMContextFreshnessService
from ..context_provenance import UnknownProvenanceError
from ..context_version import UnknownContextVersionError
from ..project_context import UnknownProjectContextError
from .models import ACTIONABLE, UNRESOLVABLE, LLMContextRefreshPlan


class UnknownRefreshPlanError(KeyError):
    """Raised when get()/validate()/preview() names a plan_id that was never created."""


class NothingToRefreshError(ValueError):
    """Raised when plan() is asked to plan a refresh for a context that is FRESH."""


class InvalidRefreshPlanError(ValueError):
    """Raised when validate() finds a plan's referenced source no longer exists."""


class LLMContextRefreshService:
    """Proposes, but never performs, refreshes for stale/unknown context.

    Reuses Commit #9's LLMContextFreshnessService for both the freshness
    verdict and, when the source is verifiably STALE,
    refresh_candidates() -- which already only reports real, currently
    existing sources (Commit #2's recorded versions, or a
    backend.session artifact store), so a plan's refresh_actions can never
    reference something invented here. Reaches Commit #1's context service
    and Commit #6's provenance service the same way Commit #9 itself
    does: as attributes already held by freshness_service, not as
    separately wired collaborators.

    Nothing here writes to a store: plan() only reads Commits #1/#2/#6/#9,
    preview() only reads what plan() already recorded plus the context's
    current content, and validate() only re-reads the same sources to
    confirm a plan is still actionable. No context is ever overwritten.
    """

    def __init__(self, freshness_service: LLMContextFreshnessService):
        self.freshness_service = freshness_service
        self.context_service = freshness_service.context_service
        self.provenance_service = freshness_service.provenance_service
        self._plans: dict[str, LLMContextRefreshPlan] = {}

    def plan(self, context_id: str) -> LLMContextRefreshPlan:
        """Propose a refresh for context_id. Only a STALE or UNKNOWN context qualifies."""
        freshness = self.freshness_service.check(context_id)
        if freshness.status == FRESH:
            raise NothingToRefreshError(
                f"context {context_id!r} is fresh; there is nothing to refresh"
            )

        try:
            provenance = self.provenance_service.get(context_id)
        except UnknownProvenanceError:
            provenance = None

        stale_source = {
            "source_type": provenance.source_type if provenance else None,
            "source_id": provenance.source_id if provenance else None,
            "source_version": provenance.source_version if provenance else None,
            "status": freshness.status,
            "reason": freshness.reason,
        }

        # Only ever populated for a verifiably STALE source pointing at a
        # real artifact/version -- empty for UNKNOWN, so an unresolvable
        # plan never carries a fabricated action.
        refresh_actions = tuple(
            dict(action) for action in self.freshness_service.refresh_candidates(context_id)
        )

        plan = LLMContextRefreshPlan(
            context_id=context_id,
            stale_sources=(stale_source,),
            refresh_actions=refresh_actions,
            reason=freshness.reason,
            status=ACTIONABLE if refresh_actions else UNRESOLVABLE,
        )

        self._plans[plan.plan_id] = plan
        return self._copy(plan)

    def get(self, plan_id: str) -> LLMContextRefreshPlan:
        try:
            plan = self._plans[plan_id]
        except KeyError:
            raise UnknownRefreshPlanError(plan_id)
        return self._copy(plan)

    def validate(self, plan_id: str) -> bool:
        """Whether a previously created plan is still actionable right now. Raises if not."""
        plan = self.get(plan_id)

        current = self.freshness_service.check(plan.context_id)
        if current.status == FRESH:
            raise InvalidRefreshPlanError(
                f"context {plan.context_id!r} is now fresh; plan {plan_id!r} is out of date"
            )

        for action in plan.refresh_actions:
            self._verify_action_still_real(action)

        return True

    def preview(self, plan_id: str) -> list:
        """What each refresh_action would replace, without replacing anything."""
        plan = self.get(plan_id)
        context = self.context_service.get(plan.context_id)

        return [
            {
                "context_id": plan.context_id,
                "source_type": action["source_type"],
                "source_id": action["source_id"],
                "current_content": context.content,
                "proposed_content": action["current_content"],
                "current_version": action.get("current_version"),
            }
            for action in plan.refresh_actions
        ]

    def _verify_action_still_real(self, action: dict) -> None:
        source_type = action["source_type"]
        source_id = action["source_id"]

        if source_type == "context_version":
            version_service = self.provenance_service.version_service
            if version_service is None:
                raise InvalidRefreshPlanError(
                    "no version service is wired to verify this action"
                )
            try:
                version_service.get(source_id, action["current_version"])
            except UnknownContextVersionError:
                raise InvalidRefreshPlanError(
                    f"version {action['current_version']} of context {source_id!r} "
                    "no longer exists"
                )
            return

        if source_type == "research_artifact":
            artifact_store = self.provenance_service.artifact_store
            if artifact_store is None:
                raise InvalidRefreshPlanError(
                    "no artifact store is wired to verify this action"
                )
            artifact = artifact_store.get(source_id)
            if artifact is None:
                raise InvalidRefreshPlanError(
                    f"research artifact {source_id!r} no longer exists"
                )
            return

        if source_type == "project_context":
            try:
                self.context_service.get(source_id)
            except UnknownProjectContextError:
                raise InvalidRefreshPlanError(f"source context {source_id!r} no longer exists")
            return

    @staticmethod
    def _copy(plan: LLMContextRefreshPlan) -> LLMContextRefreshPlan:
        """A defensive copy: frozen fields cannot be reassigned, but
        stale_sources/refresh_actions hold plain dicts a caller could
        otherwise mutate in place."""
        return LLMContextRefreshPlan(
            context_id=plan.context_id,
            stale_sources=tuple(deepcopy(item) for item in plan.stale_sources),
            refresh_actions=tuple(deepcopy(item) for item in plan.refresh_actions),
            reason=plan.reason,
            status=plan.status,
            plan_id=plan.plan_id,
            created_at=plan.created_at,
        )
