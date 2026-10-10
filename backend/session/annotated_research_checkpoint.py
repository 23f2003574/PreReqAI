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
class AnnotatedResearchCheckpoint:
    """
    Read model combining a historical
    checkpoint with optional human
    annotation data.
    """

    checkpoint: (
        ResearchCheckpoint
    )

    annotation: (
        ResearchCheckpointAnnotation | None
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

            "checkpoint":
                self.checkpoint
                .to_dict(),

            "annotation": (

                self.annotation
                .to_dict()

                if self.annotation

                else None
            ),

            "label":
                self.label,

            "note":
                self.note,

            "pinned":
                self.pinned,
        }
