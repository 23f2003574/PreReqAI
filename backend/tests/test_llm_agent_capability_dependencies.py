import pytest

from backend.agent_capability_dependencies import (
    CapabilityDependency,
    CyclicDependencyError,
    DuplicateDependencyError,
    InvalidDependencyError,
    JsonDependencyStore,
    LLMAgentCapabilityDependencyService,
    SelfDependencyError,
    UnknownDependencyError,
)
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry, UnknownCapabilityError


def _capability(capability_id, category="retrieval"):
    return LLMAgentCapability(
        capability_id=capability_id,
        name=capability_id,
        description=f"{capability_id} description",
        category=category,
    )


def _registry_with(*capability_ids):
    registry = LLMAgentCapabilityRegistry()
    for capability_id in capability_ids:
        registry.register(_capability(capability_id))
    return registry


def test_add_and_remove_dependency():
    registry = _registry_with("a", "b")
    service = LLMAgentCapabilityDependencyService(registry)

    edge = service.add_dependency("a", "b")
    assert isinstance(edge, CapabilityDependency)
    assert edge.capability_id == "a"
    assert edge.dependency_id == "b"
    assert service.get_dependencies("a") == ["b"]
    assert service.get_dependents("b") == ["a"]

    service.remove_dependency("a", "b")
    assert service.get_dependencies("a") == []
    assert service.get_dependents("b") == []

    with pytest.raises(UnknownDependencyError):
        service.remove_dependency("a", "b")


def test_direct_and_transitive_dependency_resolution():
    registry = _registry_with("a", "b", "c", "d")
    service = LLMAgentCapabilityDependencyService(registry)
    service.add_dependency("a", "b")
    service.add_dependency("b", "c")
    service.add_dependency("c", "d")

    assert service.get_dependencies("a") == ["b"]
    assert sorted(service.get_dependencies("a", transitive=True)) == ["b", "c", "d"]

    assert service.get_dependents("d") == ["c"]
    assert sorted(service.get_dependents("d", transitive=True)) == ["a", "b", "c"]


def test_missing_dependency_detection():
    registry = _registry_with("a")
    service = LLMAgentCapabilityDependencyService(registry)

    with pytest.raises(UnknownCapabilityError):
        service.add_dependency("a", "nonexistent")

    result = service.validate_dependencies(["a", "ghost"])
    assert result.valid is False
    assert "ghost" in result.missing_capabilities
    assert "ghost" in result.unresolved_dependencies


def test_self_dependency_rejected():
    registry = _registry_with("a")
    service = LLMAgentCapabilityDependencyService(registry)

    with pytest.raises(SelfDependencyError):
        service.add_dependency("a", "a")


def test_duplicate_dependency_rejected():
    registry = _registry_with("a", "b")
    service = LLMAgentCapabilityDependencyService(registry)
    service.add_dependency("a", "b")

    with pytest.raises(DuplicateDependencyError):
        service.add_dependency("a", "b")


def test_cycle_detection_at_add_time_and_in_validation():
    registry = _registry_with("a", "b", "c")
    service = LLMAgentCapabilityDependencyService(registry)
    service.add_dependency("a", "b")
    service.add_dependency("b", "c")

    with pytest.raises(CyclicDependencyError):
        service.add_dependency("c", "a")

    # a cycle introduced directly via the store (bypassing add_dependency)
    # is still caught by validate_dependencies()
    service.store.save(CapabilityDependency(capability_id="c", dependency_id="a"))

    result = service.validate_dependencies(["a"])
    assert result.valid is False
    assert set(result.cycles) == {"a", "b", "c"}
    assert "a" in result.unresolved_dependencies


def test_archived_dependency_detection():
    registry = _registry_with("a", "b")
    service = LLMAgentCapabilityDependencyService(registry)
    service.add_dependency("a", "b")
    registry.archive("b")

    result = service.validate_dependencies(["a"])
    assert result.valid is False
    assert "b" not in result.missing_capabilities
    assert "a" in result.unresolved_dependencies


def test_valid_dependency_graph_passes():
    registry = _registry_with("a", "b", "c")
    service = LLMAgentCapabilityDependencyService(registry)
    service.add_dependency("a", "b")
    service.add_dependency("b", "c")

    result = service.validate_dependencies(["a"])
    assert result.valid is True
    assert result.missing_capabilities == []
    assert result.cycles == []
    assert result.unresolved_dependencies == []


def test_no_unrelated_capability_state_is_mutated():
    registry = _registry_with("a", "b", "c")
    service = LLMAgentCapabilityDependencyService(registry)

    before = {c.capability_id: (c.status, c.version, c.updated_at) for c in registry.list()}
    service.add_dependency("a", "b")
    service.remove_dependency("a", "b")
    service.add_dependency("a", "c")
    service.validate_dependencies(["a", "b", "c"])

    after = {c.capability_id: (c.status, c.version, c.updated_at) for c in registry.list()}
    assert before == after


def test_validation_errors():
    registry = _registry_with("a")
    service = LLMAgentCapabilityDependencyService(registry)

    with pytest.raises(InvalidDependencyError):
        service.add_dependency("", "a")
    with pytest.raises(InvalidDependencyError):
        service.add_dependency("a", "")
    with pytest.raises(InvalidDependencyError):
        service.get_dependencies("")
    with pytest.raises(InvalidDependencyError):
        service.validate_dependencies("not-a-list")
    with pytest.raises(InvalidDependencyError):
        service.validate_dependencies([1, 2])


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "dependencies.json"
    registry = _registry_with("a", "b")

    service1 = LLMAgentCapabilityDependencyService(registry, store=JsonDependencyStore(path))
    service1.add_dependency("a", "b")

    service2 = LLMAgentCapabilityDependencyService(registry, store=JsonDependencyStore(path))
    assert service2.get_dependencies("a") == ["b"]
    assert service2.get_dependents("b") == ["a"]
