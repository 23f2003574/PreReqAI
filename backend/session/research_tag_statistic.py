from dataclasses import (
    dataclass,
)


@dataclass
class ResearchTagStatistic:
    """
    Usage statistics for one research tag.
    """

    tag_id: str

    tag_name: str

    session_count: int

    def to_dict(self):

        return {

            "tag_id":
                self.tag_id,

            "tag_name":
                self.tag_name,

            "session_count":
                self.session_count,
        }
