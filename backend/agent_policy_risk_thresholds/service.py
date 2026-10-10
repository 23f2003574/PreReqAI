from backend.agent_policy_risk_assessment import LEVELS
from backend.agent_policy_risk_classification import RiskClassification

from .in_memory_store import InMemoryRiskThresholdsStore
from .models import InvalidRiskThresholdsError, RiskAction, RiskThresholds, resolve_action
from .store import RiskThresholdsStore


class InvalidRiskClassificationError(ValueError):
    """Raised when evaluate() is given something other than a Commit #2
    RiskClassification."""


class LLMAgentPolicyRiskThresholdService:
    """Configures, per scope, when a Commit #2 RiskClassification should
    result in normal execution, review, or an outright deny -- and
    evaluates classifications against that configuration.

    Not a new configuration framework: persistence follows the exact
    save/get split backend.agent_policy_engine.LLMAgentPolicyStore
    already established (an InMemoryRiskThresholdsStore by default, or a
    JSON-file-backed store built on the same backend.storage.
    AtomicJsonFile), scope-isolated the same way every store in this
    series already is -- get()/set() for one scope_id never reads or
    writes another's.

    get() never invents a threshold config a caller never set: a scope
    that has not called set() gets RiskThresholds' own module-level
    DEFAULT_REVIEW_AT/DEFAULT_DENY_AT (HIGH/CRITICAL) computed fresh on
    every call, never silently persisted -- only an explicit set() ever
    writes to the store. set() accepts either a RiskThresholds or a
    plain {"review_at": ..., "deny_at": ...} mapping; either way this
    service builds the canonical RiskThresholds(scope_id=scope_id, ...)
    itself (ignoring any scope_id the input happened to carry) so a
    threshold can never be persisted under a scope other than the one
    it was set() for, and RiskThresholds' own __post_init__ is what
    enforces threshold ordering (see Rules: "Validate threshold
    ordering") -- this service never duplicates that check.

    evaluate() never mutates the classification it is given (see Rules:
    "Do not mutate the risk classification") and never re-runs Commit
    #1/#2's own risk computation -- it only compares
    classification.risk_level's ordinal position in Commit #1's own
    LEVELS against the resolved RiskThresholds. Because LEVEL_CRITICAL
    is always the top of LEVELS, this structurally guarantees an
    explicit policy denial (which Commit #1 always scores as CRITICAL)
    resolves to DENY under any valid threshold configuration -- see
    RiskThresholds' own docstring for why (Rules: "Explicit policy
    denial remains authoritative").
    """

    def __init__(self, store: RiskThresholdsStore = None):
        self.store = store if store is not None else InMemoryRiskThresholdsStore()

    def get(self, scope_id: str) -> RiskThresholds:
        """The current RiskThresholds for scope_id -- whatever was last
        set() for it, or the default (HIGH -> REVIEW, CRITICAL -> DENY)
        when nothing has been set.

        Raises:
            InvalidRiskThresholdsError: If scope_id is missing
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskThresholdsError("scope_id is required and must be a non-empty string")

        stored = self.store.get(scope_id)
        return stored if stored is not None else RiskThresholds(scope_id=scope_id)

    def set(self, scope_id: str, thresholds) -> RiskThresholds:
        """Configure scope_id's thresholds.

        thresholds may be a RiskThresholds or a plain
        {"review_at": ..., "deny_at": ...} mapping (either or both keys
        omitted falls back to RiskThresholds' own defaults for that
        key).

        Raises:
            InvalidRiskThresholdsError: If scope_id is missing, or the
                resulting review_at/deny_at pair fails validation
                (unknown level, or deny_at ordered below review_at)
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskThresholdsError("scope_id is required and must be a non-empty string")

        if isinstance(thresholds, RiskThresholds):
            review_at, deny_at = thresholds.review_at, thresholds.deny_at
        elif isinstance(thresholds, dict):
            defaults = RiskThresholds(scope_id=scope_id)
            review_at = thresholds.get("review_at", defaults.review_at)
            deny_at = thresholds.get("deny_at", defaults.deny_at)
        else:
            raise InvalidRiskThresholdsError(
                f"thresholds must be a RiskThresholds or dict, got {type(thresholds).__name__}"
            )

        resolved = RiskThresholds(scope_id=scope_id, review_at=review_at, deny_at=deny_at)
        return self.store.save(resolved)

    def evaluate(self, scope_id: str, classification: RiskClassification) -> RiskAction:
        """Resolve scope_id's thresholds and evaluate classification
        against them.

        Raises:
            InvalidRiskThresholdsError: If scope_id is missing
            InvalidRiskClassificationError: If classification is not a
                RiskClassification, or its risk_level is not one of
                Commit #1's own LEVELS
        """
        if not isinstance(classification, RiskClassification):
            raise InvalidRiskClassificationError(
                f"classification must be a RiskClassification, got {type(classification).__name__}"
            )
        if classification.risk_level not in LEVELS:
            raise InvalidRiskClassificationError(
                f"classification.risk_level {classification.risk_level!r} is not one of {LEVELS}"
            )

        thresholds = self.get(scope_id)
        action = resolve_action(classification.risk_level, thresholds.review_at, thresholds.deny_at)
        reason = (
            f"risk level {classification.risk_level!r} resolves to {action!r} against "
            f"review_at={thresholds.review_at!r}/deny_at={thresholds.deny_at!r} for scope {scope_id!r}"
        )

        return RiskAction(
            action=action,
            scope_id=scope_id,
            risk_level=classification.risk_level,
            reason=reason,
            provenance={"classification": classification, "thresholds": thresholds},
        )
