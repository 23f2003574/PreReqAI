import json
import re

from backend.agent_strategy_application import CONTEXT_KEY
from backend.agent_strategy_conflict_resolution import UNRESOLVED, LLMAgentStrategyConflictResolution
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.agent_strategy_selection import LLMAgentStrategySelection

from .in_memory_store import InMemoryLLMAgentStrategyDecisionStore
from .models import APPLIED, CONFLICT_RESOLVED, DECISION_TYPES, REJECTED, SELECTED, LLMAgentStrategyDecision
from .store import LLMAgentStrategyDecisionStore

# Same secret-detection convention kept locally by every other module in
# this series -- kept local here too rather than refactoring any of them.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _contains_secret(value) -> bool:
    if isinstance(value, str):
        return _looks_secret(value)
    if isinstance(value, dict):
        return any(_contains_secret(key) or _contains_secret(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item) for item in value)
    return False


class UnknownAgentStrategyDecisionError(KeyError):
    """Raised when get() is given a decision_id that was never recorded."""


class InvalidDecisionTypeError(ValueError):
    """Raised when decision_type is not one of DECISION_TYPES."""


class InvalidEvidenceError(ValueError):
    """Raised when evidence is not JSON-serializable."""


class SecretEvidenceError(ValueError):
    """Raised when evidence appears to carry a secret or credential."""


class LLMAgentStrategyDecisionAuditService:
    """Makes Commit #5/#6/#10's strategy-driven planning choices
    observable after the fact, as one append-only decision trail.

    Not a new audit framework: persistence is the exact save/get/
    list_for_-- split (an InMemoryLLMAgentStrategyDecisionStore by
    default, or the JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile every other module here uses) and
    secret-screening convention this whole series already established
    (Commit #3's outcome evidence, Commit #7's usage records). record()
    never takes strategy_id on faith: it reads Commit #1's own
    LLMAgentStrategyService.get(strategy_id), propagating
    UnknownAgentStrategyError unchanged rather than a wrapper, and never
    mutates what it reads.

    record_selection()/record_conflict_resolution()/record_application()
    are pure observers of what Commit #5/#6/#10 already computed: each
    takes that commit's own real result object (a list of Commit #5
    LLMAgentStrategySelection, a Commit #10 LLMAgentStrategyConflictResolution,
    or a Commit #6-applied context dict) and translates it into decision
    records using only the score/evidence/reason those commits already
    carry -- nothing here re-derives relevance, effectiveness, or
    conflict resolution a second way, and none of Commit #5/#6/#10's own
    code is called, wrapped, or modified by this service. Selection,
    application, and conflict-resolution behavior is entirely unchanged
    by whether or not a caller chooses to audit it.
    """

    def __init__(
        self,
        strategy_service: LLMAgentStrategyService,
        store: LLMAgentStrategyDecisionStore = None,
    ):
        self._strategy_service = strategy_service
        self.store = store if store is not None else InMemoryLLMAgentStrategyDecisionStore()

    def record(
        self,
        strategy_id: str,
        execution_or_task_id: str,
        decision_type: str,
        decision: str,
        reason: str,
        score: float = None,
        evidence=None,
    ) -> LLMAgentStrategyDecision:
        """Append one decision audit record for strategy_id.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
            ValueError: If execution_or_task_id/decision/reason is missing,
                or score is given and is not a number
            InvalidDecisionTypeError: If decision_type is not one of
                DECISION_TYPES
            InvalidEvidenceError, SecretEvidenceError: If evidence itself
                fails validation
        """
        self._strategy_service.get(strategy_id)

        if not execution_or_task_id or not isinstance(execution_or_task_id, str):
            raise ValueError("execution_or_task_id is required")
        if decision_type not in DECISION_TYPES:
            raise InvalidDecisionTypeError(
                f"decision_type {decision_type!r} is not one of {sorted(DECISION_TYPES)}"
            )
        if not decision or not isinstance(decision, str):
            raise ValueError("decision is required")
        if not reason or not isinstance(reason, str):
            raise ValueError("reason is required")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
            raise ValueError(f"score {score!r} must be a number when given")

        evidence = {} if evidence is None else evidence
        self._validate_evidence(evidence)

        record = LLMAgentStrategyDecision(
            strategy_id=strategy_id, execution_or_task_id=execution_or_task_id,
            decision_type=decision_type, decision=decision, reason=reason,
            score=score, evidence=evidence,
        )
        return self.store.save(record)

    def record_selection(self, execution_or_task_id: str, selected: list) -> list:
        """One SELECTED decision per Commit #5 LLMAgentStrategySelection,
        using that selection's own combined_score/relevance_score/
        effectiveness/reason verbatim."""
        records = []
        for selection in selected:
            if not isinstance(selection, LLMAgentStrategySelection):
                raise ValueError("selected must contain LLMAgentStrategySelection objects")
            records.append(
                self.record(
                    selection.strategy.strategy_id, execution_or_task_id, SELECTED, "included",
                    selection.reason,
                    score=selection.combined_score,
                    evidence={
                        "relevance_score": selection.relevance_score,
                        "effectiveness": {
                            "score": selection.effectiveness.score,
                            "confidence": selection.effectiveness.confidence,
                            "evidence_count": selection.effectiveness.evidence_count,
                        },
                    },
                )
            )
        return records

    def record_conflict_resolution(
        self, execution_or_task_id: str, resolution: LLMAgentStrategyConflictResolution
    ) -> list:
        """Two decisions per resolved Commit #10 conflict (a
        CONFLICT_RESOLVED "won" for the winner, a REJECTED "lost_conflict"
        for the loser), or one CONFLICT_RESOLVED "unresolved" decision per
        side of a conflict Commit #10 could not safely resolve -- a
        strategy dropped by conflict resolution is always explainable
        here by its own REJECTED record, never merely inferred from its
        absence."""
        if not isinstance(resolution, LLMAgentStrategyConflictResolution):
            raise ValueError("resolution must be an LLMAgentStrategyConflictResolution")

        records = []
        for outcome in resolution.conflicts:
            evidence = {"strategy_ids": list(outcome.conflict.strategy_ids), "conflict_reason": outcome.conflict.reason}

            if outcome.resolution == UNRESOLVED:
                for strategy_id in outcome.conflict.strategy_ids:
                    records.append(
                        self.record(
                            strategy_id, execution_or_task_id, CONFLICT_RESOLVED, "unresolved",
                            outcome.reason, evidence=evidence,
                        )
                    )
                continue

            records.append(
                self.record(
                    outcome.winner_strategy_id, execution_or_task_id, CONFLICT_RESOLVED, "won",
                    outcome.reason, evidence=evidence,
                )
            )
            records.append(
                self.record(
                    outcome.loser_strategy_id, execution_or_task_id, REJECTED, "lost_conflict",
                    outcome.reason, evidence=evidence,
                )
            )
        return records

    def record_application(self, execution_or_task_id: str, applied_context: dict) -> list:
        """One APPLIED decision per entry Commit #6's apply() added under
        its own CONTEXT_KEY -- using that entry's own combined_score/
        effectiveness/provenance/reason verbatim."""
        if not isinstance(applied_context, dict):
            raise ValueError("applied_context must be a dict")

        entries = applied_context.get(CONTEXT_KEY, [])
        records = []
        for entry in entries:
            records.append(
                self.record(
                    entry["strategy_id"], execution_or_task_id, APPLIED, "applied", entry["reason"],
                    score=entry["combined_score"],
                    evidence={"effectiveness": entry["effectiveness"], "provenance": entry["provenance"]},
                )
            )
        return records

    def get(self, decision_id: str) -> LLMAgentStrategyDecision:
        record = self.store.get(decision_id)
        if record is None:
            raise UnknownAgentStrategyDecisionError(decision_id)
        return record

    def list_for_strategy(self, strategy_id: str) -> list:
        """Every decision recorded for strategy_id, oldest first -- the
        complete history, never collapsed to a single latest verdict.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
        """
        self._strategy_service.get(strategy_id)
        return self.store.list_for_strategy(strategy_id)

    def list_for_execution(self, execution_or_task_id: str) -> list:
        """Every strategy decision recorded for execution_or_task_id,
        oldest first."""
        return self.store.list_for_execution(execution_or_task_id)

    @staticmethod
    def _validate_evidence(evidence):
        try:
            json.dumps(evidence)
        except (TypeError, ValueError) as error:
            raise InvalidEvidenceError("evidence must be JSON-serializable") from error

        if _contains_secret(evidence):
            raise SecretEvidenceError(
                "evidence appears to contain a secret or credential and cannot be stored"
            )
