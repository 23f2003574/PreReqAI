from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachment as Attachment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAttachmentService as AttachmentService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    attachment_service = AttachmentService(session_service)
    return pipeline_service, session_service, attachment_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    return session_service.start(pipeline_id, owner=owner)


def _attachment(attachment_id, session_id, name="report.pdf", type="report", location="s3://bucket/report.pdf"):
    return Attachment(
        attachment_id=attachment_id,
        session_id=session_id,
        name=name,
        type=type,
        location=location,
        created_at=datetime.now(timezone.utc),
    )


class TestWorkspaceSessionAttachmentService:
    def test_attach_artifact(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        result = attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))

        assert isinstance(result, Result)
        assert result.attachment_id == "attachment-1"
        assert result.attached is True

    def test_retrieve_artifact(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id, name="build.log", type="log"))

        fetched = attachment_service.get("attachment-1")

        assert isinstance(fetched, Attachment)
        assert fetched.name == "build.log"
        assert fetched.type == "log"

    def test_list_attachments(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))
        attachment_service.attach(session.session_id, _attachment("attachment-2", session.session_id, type="export"))

        listed = attachment_service.list(session.session_id)

        assert [attachment.attachment_id for attachment in listed] == ["attachment-1", "attachment-2"]

    def test_detach_artifact(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))
        attachment_service.attach(session.session_id, _attachment("attachment-2", session.session_id))

        attachment_service.detach("attachment-1")

        listed = attachment_service.list(session.session_id)
        assert [attachment.attachment_id for attachment in listed] == ["attachment-2"]

        # detached attachments remain auditable
        assert attachment_service.get("attachment-1").attachment_id == "attachment-1"
        assert attachment_service.exists("attachment-1") is True

        # detaching an already-detached attachment is not an error
        attachment_service.detach("attachment-1")

    def test_duplicate_rejection(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))

        with pytest.raises(Error):
            attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))

    def test_attachment_existence_lookup(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        assert attachment_service.exists("attachment-1") is False

        attachment_service.attach(session.session_id, _attachment("attachment-1", session.session_id))

        assert attachment_service.exists("attachment-1") is True

    def test_invalid_attachment_type_rejection(self):
        with pytest.raises(Error):
            _attachment("attachment-1", "session-1", type="binary")

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, attachment_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            attachment_service.attach("   ", _attachment("attachment-1", session.session_id))

        with pytest.raises(Error):
            attachment_service.attach("unknown-session", _attachment("attachment-1", "unknown-session"))

        with pytest.raises(Error):
            attachment_service.attach(session.session_id, _attachment("attachment-1", "different-session"))

        with pytest.raises(Error):
            attachment_service.attach(session.session_id, "not-an-attachment")

        with pytest.raises(Error):
            attachment_service.get("   ")

        with pytest.raises(Error):
            attachment_service.get("unknown-attachment")

        with pytest.raises(Error):
            attachment_service.list("unknown-session")

        with pytest.raises(Error):
            attachment_service.detach("unknown-attachment")

        with pytest.raises(Error):
            attachment_service.exists("   ")
