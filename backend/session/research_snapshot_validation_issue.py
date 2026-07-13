from dataclasses import (
    dataclass,
)


@dataclass
class ResearchSnapshotValidationIssue:
    """
    Describes one integrity problem found
    in a research snapshot.
    """

    code: str

    message: str

    path: (
        str | None
    ) = None

    def to_dict(self):

        return {

            "code":
                self.code,

            "message":
                self.message,

            "path":
                self.path,
        }
