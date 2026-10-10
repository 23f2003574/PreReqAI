from datetime import datetime, timezone

import pytest

from backend.agent_strategy_conflict_resolution import (
    EVIDENCE,
    TASK_CONSTRAINT,
    UNRESOLVED,
    LLMAgentStrategyConflictResolver,
)
from backend.agent_strategy_library import ACTIVE, LLMAgentStrategy
from backend.agent_strategy_lifecycle import (
    DEPRECATED,
    TRUSTED,
    InMemoryLLMAgentStrategyLifecycleStore,
    LLMAgentStrategyLifecycleDecision,
)
from backend.agent_strategy_scoring import LLMAgentStrategyScore
from backend.agent_strategy_selection import LLMAgentStrategySelection

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _strategy(strategy_id, name=None, scope_id="notebook-1", strategy_data=None, status=ACTIVE, created_at=NOW):
    return LLMAgentStrategy(
        scope_id=scope_id, name=name or strategy_id, description=f"{strategy_id} description",
        strategy_data=strategy_data if strategy_data is not None else {}, source_memory_ids=["memory-1"],
        status=status, strategy_id=strategy_id, created_at=created_at, updated_at=created_at,
    )


def _score(strategy_id, score=0.8, confidence=0.8, evidence_count=3, succeeded=3, failed=0):
    return LLMAgentStrategyScore(
        strategy_id=strategy_id, score=score, confidence=confidence, evidence_count=evidence_count,
        succeeded_count=succeeded, failed_count=failed, reason="test evidence", scored_at=NOW,
    )


def _selection(strategy, effectiveness, relevance_score=0.9):
    combined = round(0.5 * relevance_score + 0.5 * effectiveness.score, 6)
    return LLMAgentStrategySelection(
        strategy=strategy, relevance_score=relevance_score, effectiveness=effectiveness,
        combined_score=combined, reason="test selection",
    )


def test_compatible_strategies():
    resolver = LLMAgentStrategyConflictResolver()
    a = _selection(_strategy("strategy-a"), _score("strategy-a"))
    b = _selection(_strategy("strategy-b"), _score("strategy-b"))

    assert resolver.detect_conflicts([a, b]) == []

    result = resolver.resolve_conflicts([a, b])
    assert result.selected == [a, b]
    assert result.conflicts == []


def test_direct_conflict_detected():
    resolver = LLMAgentStrategyConflictResolver()
    a = _selection(_strategy("strategy-a", strategy_data={"conflicts_with": ["strategy-b"]}), _score("strategy-a"))
    b = _selection(_strategy("strategy-b"), _score("strategy-b"))

    conflicts = resolver.detect_conflicts([a, b])

    assert len(conflicts) == 1
    assert conflicts[0].strategy_ids == ("strategy-a", "strategy-b")
    assert "conflicts_with" in conflicts[0].reason

    # a shared exclusive_group is also a declared conflict, independent of conflicts_with
    c = _selection(_strategy("strategy-c", strategy_data={"exclusive_group": "auth"}), _score("strategy-c"))
    d = _selection(_strategy("strategy-d", strategy_data={"exclusive_group": "auth"}), _score("strategy-d"))
    group_conflicts = resolver.detect_conflicts([c, d])
    assert len(group_conflicts) == 1
    assert group_conflicts[0].strategy_ids == ("strategy-c", "strategy-d")


def test_stronger_strategy_wins():
    resolver = LLMAgentStrategyConflictResolver()
    strong = _selection(
        _strategy("strategy-strong", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-strong", score=0.9, confidence=0.9),
    )
    weak = _selection(
        _strategy("strategy-weak", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-weak", score=0.3, confidence=0.9),
    )

    result = resolver.resolve_conflicts([strong, weak])

    assert [item.strategy.strategy_id for item in result.selected] == ["strategy-strong"]
    assert len(result.conflicts) == 1
    decision = result.conflicts[0]
    assert decision.resolution == EVIDENCE
    assert decision.winner_strategy_id == "strategy-strong"
    assert decision.loser_strategy_id == "strategy-weak"


def test_task_constraint_overrides_evidence():
    resolver = LLMAgentStrategyConflictResolver()
    required_but_weak = _selection(
        _strategy("strategy-required", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-required", score=0.2, confidence=0.9),
    )
    unrequired_but_strong = _selection(
        _strategy("strategy-unrequired", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-unrequired", score=0.95, confidence=0.95),
    )

    result = resolver.resolve_conflicts(
        [required_but_weak, unrequired_but_strong],
        context={"required_strategy_ids": ["strategy-required"]},
    )

    assert [item.strategy.strategy_id for item in result.selected] == ["strategy-required"]
    decision = result.conflicts[0]
    assert decision.resolution == TASK_CONSTRAINT
    assert decision.winner_strategy_id == "strategy-required"


def test_unresolved_conflict_keeps_both():
    resolver = LLMAgentStrategyConflictResolver()
    a = _selection(_strategy("strategy-a", strategy_data={"exclusive_group": "approach"}), _score("strategy-a"))
    b = _selection(_strategy("strategy-b", strategy_data={"exclusive_group": "approach"}), _score("strategy-b"))

    result = resolver.resolve_conflicts(
        [a, b], context={"required_strategy_ids": ["strategy-a", "strategy-b"]}
    )

    # neither is silently discarded -- both explicitly required, so
    # neither can be safely dropped
    assert {item.strategy.strategy_id for item in result.selected} == {"strategy-a", "strategy-b"}
    assert len(result.conflicts) == 1
    decision = result.conflicts[0]
    assert decision.resolution == UNRESOLVED
    assert decision.winner_strategy_id is None
    assert decision.loser_strategy_id is None


def test_trust_status_takes_precedence_over_raw_score():
    lifecycle_store = InMemoryLLMAgentStrategyLifecycleStore()
    trusted_strategy = _strategy("strategy-trusted", strategy_data={"exclusive_group": "approach"})
    lifecycle_store.save(
        LLMAgentStrategyLifecycleDecision(
            strategy_id="strategy-trusted", previous_status=ACTIVE, status=TRUSTED,
            reason="strong evidence", score=0.7, confidence=0.9, evidence_count=5,
            succeeded_count=5, failed_count=0, decided_at=NOW,
        )
    )
    resolver = LLMAgentStrategyConflictResolver(lifecycle_store=lifecycle_store)

    trusted = _selection(trusted_strategy, _score("strategy-trusted", score=0.6, confidence=0.9))
    merely_active_but_higher_score = _selection(
        _strategy("strategy-active", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-active", score=0.95, confidence=0.95),
    )

    result = resolver.resolve_conflicts([trusted, merely_active_but_higher_score])

    assert [item.strategy.strategy_id for item in result.selected] == ["strategy-trusted"]
    assert result.conflicts[0].reason == "stronger trust/status tier"


def test_deterministic_resolution():
    resolver = LLMAgentStrategyConflictResolver()
    a = _selection(
        _strategy("strategy-a", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-a", score=0.5, confidence=0.7),
    )
    b = _selection(
        _strategy("strategy-b", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-b", score=0.5, confidence=0.7),
    )

    first = resolver.resolve_conflicts([a, b])
    second = resolver.resolve_conflicts([a, b])

    assert [item.strategy.strategy_id for item in first.selected] == [
        item.strategy.strategy_id for item in second.selected
    ]
    assert first.conflicts[0].winner_strategy_id == second.conflicts[0].winner_strategy_id
    # fully evidence-tied: broken deterministically by strategy_id, not
    # left to input order or chance
    assert first.conflicts[0].winner_strategy_id == "strategy-a"
    assert "strategy_id" in first.conflicts[0].reason


def test_provenance_preserved():
    resolver = LLMAgentStrategyConflictResolver()
    strong = _selection(
        _strategy("strategy-strong", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-strong", score=0.9, confidence=0.9, evidence_count=4, succeeded=4, failed=0),
    )
    weak = _selection(
        _strategy("strategy-weak", strategy_data={"exclusive_group": "approach"}),
        _score("strategy-weak", score=0.1, confidence=0.9, evidence_count=4, succeeded=0, failed=4),
    )

    result = resolver.resolve_conflicts([strong, weak])

    survivor = result.selected[0]
    assert survivor.strategy.source_memory_ids == ["memory-1"]
    assert survivor.effectiveness.evidence_count == 4
    assert survivor.effectiveness.succeeded_count == 4

    decision = result.conflicts[0]
    assert decision.conflict.strategy_ids == ("strategy-strong", "strategy-weak")
    assert decision.conflict.reason
    assert decision.reason


def test_invalid_arguments():
    resolver = LLMAgentStrategyConflictResolver()

    with pytest.raises(ValueError):
        resolver.detect_conflicts("not-a-list")

    with pytest.raises(ValueError):
        resolver.resolve_conflicts("not-a-list")

    a = _selection(_strategy("strategy-a"), _score("strategy-a"))
    with pytest.raises(ValueError):
        resolver.resolve_conflicts([a], context="not-a-dict")
