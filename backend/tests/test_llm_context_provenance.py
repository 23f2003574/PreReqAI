import dataclasses

import pytest

from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_provenance import (
    InvalidSourceError,
    LLMContextProvenance,
    LLMContextProvenanceService,
    SecretProvenanceError,
    UnknownProvenanceError,
)
from backend.llm.context_retrieval import LLMContextRetrievalService
from backend.llm.context_version import LLMContextVersionService
from backend.llm.project_context import LLMProjectContextService, UnknownProjectContextError
from backend.session import InMemoryResearchArtifactStore, ResearchArtifact, ResearchArtifactType


def _services(**kwargs):
    context_service = LLMProjectContextService()
    provenance_service = LLMContextProvenanceService(context_service, **kwargs)
    return context_service, provenance_service


def test_provenance_attachment():
    context_service, provenance_service = _services()
    context = context_service.create("notebook-1", "fact", "the loss converges after 50 epochs")

    provenance = provenance_service.attach(
        context.context_id,
        {
            "source_type": "external",
            "source_id": "notebook-1#cell-7",
            "excerpt": "epoch 50: loss=0.021",
        },
    )

    assert isinstance(provenance, LLMContextProvenance)
    assert provenance.context_id == context.context_id
    assert provenance.source_type == "external"
    assert provenance.source_id == "notebook-1#cell-7"
    assert provenance.excerpt == "epoch 50: loss=0.021"
    assert provenance.provenance_id is not None
    assert provenance.created_at is not None

    assert provenance_service.get(context.context_id) == provenance
    assert provenance_service.sources(context.context_id) == [provenance]

    with pytest.raises(UnknownProjectContextError):
        provenance_service.attach("missing-context", {"source_type": "external", "source_id": "x", "excerpt": "y"})


def test_source_version_validation():
    context_service, provenance_service = _services()
    context = context_service.create("notebook-1", "fact", "some fact")

    with pytest.raises(InvalidSourceError):
        provenance_service.validate(
            LLMContextProvenance(
                context_id=context.context_id,
                source_type="not-a-real-type",
                source_id="x",
                excerpt="y",
            )
        )

    with pytest.raises(InvalidSourceError):
        provenance_service.validate(
            LLMContextProvenance(
                context_id=context.context_id,
                source_type="external",
                source_id="x",
                excerpt="y",
                source_version=0,
            )
        )

    with pytest.raises(InvalidSourceError):
        provenance_service.validate(
            LLMContextProvenance(
                context_id=context.context_id,
                source_type="external",
                source_id="",
                excerpt="y",
            )
        )

    # a well-formed, verifiable record passes
    assert provenance_service.validate(
        LLMContextProvenance(
            context_id=context.context_id,
            source_type="project_context",
            source_id=context.context_id,
            excerpt="self-referential summary source",
        )
    ) is True


def test_retrieval_preserves_provenance():
    context_service, provenance_service = _services()
    retrieval_service = LLMContextRetrievalService(context_service)

    context = context_service.create("notebook-1", "fact", "gradient descent minimizes loss")
    provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "paper.pdf#p3", "excerpt": "see section 3"},
    )

    [retrieved] = retrieval_service.retrieve("notebook-1", "gradient descent", limit=1)

    found = provenance_service.get(retrieved.context_id)
    assert found.source_id == "paper.pdf#p3"


def test_compaction_preserves_provenance():
    context_service, provenance_service = _services()
    compaction_service = LLMContextCompactionService()

    context = context_service.create(
        "notebook-1", "fact", "gradient descent minimizes the loss function. " * 40
    )
    provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "paper.pdf#p3", "excerpt": "see section 3"},
    )

    [compacted] = compaction_service.compact([context], token_budget=5)

    assert compacted.context_id == context.context_id
    assert compacted.content != context.content  # truncated, but same identity

    found = provenance_service.get(compacted.context_id)
    assert found.source_id == "paper.pdf#p3"


def test_invalid_source():
    context_service = LLMProjectContextService()
    version_service = LLMContextVersionService(context_service)
    artifact_store = InMemoryResearchArtifactStore()
    provenance_service = LLMContextProvenanceService(
        context_service, version_service=version_service, artifact_store=artifact_store
    )

    context = context_service.create("notebook-1", "fact", "some fact")

    # context_version pointing at a version that was never snapshotted
    with pytest.raises(InvalidSourceError):
        provenance_service.attach(
            context.context_id,
            {
                "source_type": "context_version",
                "source_id": context.context_id,
                "source_version": 7,
                "excerpt": "never snapshotted",
            },
        )

    # research_artifact pointing at an artifact that was never saved
    with pytest.raises(InvalidSourceError):
        provenance_service.attach(
            context.context_id,
            {
                "source_type": "research_artifact",
                "source_id": "artifact-does-not-exist",
                "excerpt": "missing artifact",
            },
        )

    # research_artifact pointing at the right artifact but the wrong version
    artifact = artifact_store.save(
        ResearchArtifact(
            session_id="session-1",
            object_id="paper-1",
            artifact_type=ResearchArtifactType.SUMMARY,
            content="a summary",
        )
    )
    with pytest.raises(InvalidSourceError):
        provenance_service.attach(
            context.context_id,
            {
                "source_type": "research_artifact",
                "source_id": artifact.id,
                "source_version": artifact.version + 1,
                "excerpt": "wrong version",
            },
        )

    # the correct artifact/version succeeds
    provenance = provenance_service.attach(
        context.context_id,
        {
            "source_type": "research_artifact",
            "source_id": artifact.id,
            "source_version": artifact.version,
            "excerpt": "a summary",
        },
    )
    assert provenance.source_id == artifact.id


def test_secret_exclusion():
    context_service, provenance_service = _services()
    context = context_service.create("notebook-1", "fact", "some fact")

    with pytest.raises(SecretProvenanceError):
        provenance_service.attach(
            context.context_id,
            {
                "source_type": "external",
                "source_id": "notebook-1#cell-7",
                "excerpt": "api_key=sk-abcdefghijklmnopqrstuvwxyz",
            },
        )

    with pytest.raises(SecretProvenanceError):
        provenance_service.attach(
            context.context_id,
            {
                "source_type": "external",
                "source_id": "sk-abcdefghijklmnopqrstuvwxyz",
                "excerpt": "a perfectly fine excerpt",
            },
        )


def test_immutable_and_append_only_provenance():
    context_service, provenance_service = _services()
    context = context_service.create("notebook-1", "fact", "some fact")

    first = provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "source-1", "excerpt": "first excerpt"},
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        first.excerpt = "mutated"

    second = provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "source-2", "excerpt": "second excerpt"},
    )

    # append-only: both records remain, in order, and get() reflects the latest
    assert provenance_service.sources(context.context_id) == [first, second]
    assert provenance_service.get(context.context_id) == second
    assert first.source_id == "source-1"  # unaffected by the later attach()

    with pytest.raises(UnknownProvenanceError):
        provenance_service.get("some-other-context")
