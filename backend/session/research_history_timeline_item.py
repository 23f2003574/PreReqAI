from dataclasses import (
    dataclass,
)

from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)


@dataclass
class ResearchHistoryTimelineItem:
    """
    Represents one frontend-ready
    research history timeline entry.
    """

    checkpoint: (
        ResearchCheckpoint
    )

    annotation: (
        ResearchCheckpointAnnotation | None
    ) = None

    @property
    def id(self):

        return self.checkpoint.id

    @property
    def session_id(self):

        return (
            self.checkpoint
            .session_id
        )

    @property
    def reason(self):

        return (
            self.checkpoint
            .reason
        )

    @property
    def created_at(self):

        return (
            self.checkpoint
            .created_at
        )

    @property
    def label(self):

        if self.annotation is None:

            return None

        return self.annotation.label

    @property
    def note(self):

        if self.annotation is None:

            return None

        return self.annotation.note

    @property
    def pinned(self):

        if self.annotation is None:

            return False

        return self.annotation.pinned

    def to_dict(self):

        return {

            "id":
                self.id,

            "session_id":
                self.session_id,

            "reason":
                self.reason.value,

            "created_at":
                self.created_at
                .isoformat(),

            "label":
                self.label,

            "note":
                self.note,

            "pinned":
                self.pinned,

            "checkpoint":
                self.checkpoint
                .to_dict(),

            "annotation": (

                self.annotation
                .to_dict()

                if self.annotation

                else None
            ),
        }
