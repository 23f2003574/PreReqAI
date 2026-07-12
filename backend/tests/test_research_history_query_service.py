from datetime import (
    datetime,
    timedelta,
)

from backend.session import (

    InMemoryResearchCheckpointAnnotationStore,

    InMemoryResearchCheckpointStore,

    ResearchCheckpoint,

    ResearchCheckpointAnnotation,

    ResearchCheckpointReason,

    ResearchHistoryQuery,

    ResearchHistoryQueryService,
)


def create_history_service():

    checkpoint_store = (

        InMemoryResearchCheckpointStore()
    )

    annotation_store = (

        InMemoryResearchCheckpointAnnotationStore()
    )

    service = (

        ResearchHistoryQueryService(

            checkpoint_store=(
                checkpoint_store
            ),

            annotation_store=(
                annotation_store
            ),
        )
    )

    return (

        service,

        checkpoint_store,

        annotation_store,
    )


def test_filters_history_by_checkpoint_reason():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    workflow = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    artifact = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .ARTIFACT_CREATED
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        workflow
    )

    checkpoint_store.save(
        artifact
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            reasons={

                ResearchCheckpointReason
                .ARTIFACT_CREATED
            }
        ),
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == artifact.id
    )


def test_filters_history_by_pinned_status():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    first = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    second = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        first
    )

    checkpoint_store.save(
        second
    )

    annotation_store.save(

        ResearchCheckpointAnnotation(

            checkpoint_id=(
                second.id
            ),

            session_id=(
                "session-1"
            ),

            pinned=True,
        )
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            pinned=True
        ),
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == second.id
    )


def test_searches_checkpoint_annotations():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    checkpoint = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        checkpoint
    )

    annotation_store.save(

        ResearchCheckpointAnnotation(

            checkpoint_id=(
                checkpoint.id
            ),

            session_id=(
                "session-1"
            ),

            label=(

                "Best methodology state"
            ),

            note=(

                "Stable graph context"
            ),
        )
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            search="METHODOLOGY"
        ),
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == checkpoint.id
    )


def test_filters_recovery_related_events():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    normal = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    recovery = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .CHECKPOINT_RESTORED
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        normal
    )

    checkpoint_store.save(
        recovery
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            recovery_only=True
        ),
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == recovery.id
    )


def test_history_query_never_returns_other_sessions():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    first = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    second = ResearchCheckpoint(

        session_id="session-2",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=(
            datetime.utcnow()
        ),
    )

    checkpoint_store.save(
        first
    )

    checkpoint_store.save(
        second
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(),
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "session-1"
    )


def test_sorts_history_newest_first():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    now = datetime.utcnow()

    older = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=now,

        created_at=(

            now

            - timedelta(
                hours=1
            )
        ),
    )

    newer = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=now,

        created_at=now,
    )

    checkpoint_store.save(
        older
    )

    checkpoint_store.save(
        newer
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            sort_order="newest"
        ),
    )

    assert (

        page.items[0].id

        == newer.id
    )


def test_sorts_history_oldest_first():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    now = datetime.utcnow()

    older = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=now,

        created_at=(

            now

            - timedelta(
                hours=1
            )
        ),
    )

    newer = ResearchCheckpoint(

        session_id="session-1",

        reason=(

            ResearchCheckpointReason
            .MANUAL
        ),

        snapshot_updated_at=now,

        created_at=now,
    )

    checkpoint_store.save(
        older
    )

    checkpoint_store.save(
        newer
    )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            sort_order="oldest"
        ),
    )

    assert (

        page.items[0].id

        == older.id
    )


def test_paginates_research_history():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    for _ in range(5):

        checkpoint_store.save(

            ResearchCheckpoint(

                session_id=(
                    "session-1"
                ),

                reason=(

                    ResearchCheckpointReason
                    .MANUAL
                ),

                snapshot_updated_at=(
                    datetime.utcnow()
                ),
            )
        )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            offset=0,

            limit=2,
        ),
    )

    assert page.total == 5

    assert page.returned == 2

    assert page.has_more is True

    assert page.next_offset == 2


def test_final_history_page_has_no_next_offset():

    (
        service,
        checkpoint_store,
        annotation_store,
    ) = create_history_service()

    for _ in range(3):

        checkpoint_store.save(

            ResearchCheckpoint(

                session_id=(
                    "session-1"
                ),

                reason=(

                    ResearchCheckpointReason
                    .MANUAL
                ),

                snapshot_updated_at=(
                    datetime.utcnow()
                ),
            )
        )

    page = service.query(

        "session-1",

        ResearchHistoryQuery(

            offset=2,

            limit=2,
        ),
    )

    assert page.total == 3

    assert page.returned == 1

    assert page.has_more is False

    assert page.next_offset is None
