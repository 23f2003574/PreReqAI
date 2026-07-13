from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_session_tag_assignment import (
    ResearchSessionTagAssignment,
)

from .research_tag import (
    ResearchTag,
)

from .research_tag_store import (
    ResearchTagStore,
)


def _default_data():

    return {

        "tags": {},

        "assignments": [],
    }


class JsonResearchTagStore(
    ResearchTagStore,
):
    """
    Persists research tags and
    session-tag assignments to JSON.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=(
                _default_data
            ),
        )

    def save_tag(

        self,

        tag,

    ):

        data = self.file.read()

        data["tags"][
            tag.id
        ] = tag.to_dict()

        self.file.write(
            data
        )

    def get_tag(

        self,

        tag_id,

    ):

        data = self.file.read()

        raw = (

            data["tags"].get(
                tag_id
            )
        )

        if raw is None:

            return None

        return ResearchTag.from_dict(
            raw
        )

    def get_tag_by_name(

        self,

        name,

    ):

        data = self.file.read()

        for raw in (

            data["tags"].values()
        ):

            if raw["name"] == name:

                return (

                    ResearchTag
                    .from_dict(

                        raw
                    )
                )

        return None

    def list_tags(self):

        data = self.file.read()

        return [

            ResearchTag.from_dict(
                raw
            )

            for raw

            in data["tags"].values()
        ]

    def assign(

        self,

        assignment,

    ):

        data = self.file.read()

        exists = any(

            (

                entry["session_id"]

                == assignment.session_id
            )

            and (

                entry["tag_id"]

                == assignment.tag_id
            )

            for entry

            in data["assignments"]
        )

        if exists:

            return False

        data["assignments"].append(

            assignment.to_dict()
        )

        self.file.write(
            data
        )

        return True

    def unassign(

        self,

        session_id,

        tag_id,

    ):

        data = self.file.read()

        remaining = [

            entry

            for entry

            in data["assignments"]

            if not (

                entry["session_id"]

                == session_id

                and entry["tag_id"]

                == tag_id
            )
        ]

        if (

            len(remaining)

            == len(
                data["assignments"]
            )
        ):

            return False

        data["assignments"] = (
            remaining
        )

        self.file.write(
            data
        )

        return True

    def list_for_session(

        self,

        session_id,

    ):

        data = self.file.read()

        tag_ids = sorted({

            entry["tag_id"]

            for entry

            in data["assignments"]

            if (

                entry["session_id"]

                == session_id
            )
        })

        return [

            ResearchTag.from_dict(

                data["tags"][
                    tag_id
                ]
            )

            for tag_id

            in tag_ids

            if tag_id in data["tags"]
        ]

    def list_session_ids_for_tag(

        self,

        tag_id,

    ):

        data = self.file.read()

        return sorted({

            entry["session_id"]

            for entry

            in data["assignments"]

            if (

                entry["tag_id"]

                == tag_id
            )
        })

    def list_assignments_for_session(

        self,

        session_id,

    ):

        data = self.file.read()

        matching = [

            ResearchSessionTagAssignment
            .from_dict(

                entry
            )

            for entry

            in data["assignments"]

            if (

                entry["session_id"]

                == session_id
            )
        ]

        return sorted(

            matching,

            key=lambda item:
                item.tag_id,
        )
