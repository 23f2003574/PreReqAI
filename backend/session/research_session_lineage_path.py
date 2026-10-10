from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchSessionLineagePath:
    """
    Represents an ordered path through
    a research session lineage.
    """

    session_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    @property
    def length(self):

        return len(
            self.session_ids
        )

    @property
    def edge_count(self):

        return max(

            0,

            self.length - 1,
        )

    @property
    def start_session_id(self):

        if not self.session_ids:

            return None

        return self.session_ids[0]

    @property
    def end_session_id(self):

        if not self.session_ids:

            return None

        return self.session_ids[-1]

    def to_dict(self):

        return {

            "session_ids":
                list(
                    self.session_ids
                ),

            "length":
                self.length,

            "edge_count":
                self.edge_count,

            "start_session_id":
                self.start_session_id,

            "end_session_id":
                self.end_session_id,
        }
