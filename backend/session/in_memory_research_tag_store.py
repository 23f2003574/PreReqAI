from copy import (
    deepcopy,
)

from .research_tag_store import (
    ResearchTagStore,
)


class InMemoryResearchTagStore(
    ResearchTagStore,
):
    """
    Stores research tags and session-tag
    assignments in memory.
    """

    def __init__(self):

        self._tags = {}

        self._assignments = {}

    def save_tag(

        self,

        tag,

    ):

        self._tags[
            tag.id
        ] = deepcopy(
            tag
        )

    def get_tag(

        self,

        tag_id,

    ):

        tag = self._tags.get(
            tag_id
        )

        return (

            deepcopy(
                tag
            )

            if tag is not None

            else None
        )

    def get_tag_by_name(

        self,

        name,

    ):

        for tag in (

            self._tags.values()
        ):

            if tag.name == name:

                return deepcopy(
                    tag
                )

        return None

    def list_tags(self):

        return [

            deepcopy(
                tag
            )

            for tag

            in self._tags.values()
        ]

    def assign(

        self,

        assignment,

    ):

        key = (

            assignment.session_id,

            assignment.tag_id,
        )

        if key in self._assignments:

            return False

        self._assignments[
            key
        ] = deepcopy(
            assignment
        )

        return True

    def unassign(

        self,

        session_id,

        tag_id,

    ):

        key = (
            session_id,
            tag_id,
        )

        return (

            self._assignments.pop(

                key,

                None,
            )

            is not None
        )

    def list_for_session(

        self,

        session_id,

    ):

        tag_ids = {

            assignment.tag_id

            for assignment

            in self._assignments.values()

            if (

                assignment.session_id

                == session_id
            )
        }

        return [

            deepcopy(
                self._tags[
                    tag_id
                ]
            )

            for tag_id

            in sorted(
                tag_ids
            )

            if tag_id in self._tags
        ]

    def list_session_ids_for_tag(

        self,

        tag_id,

    ):

        return sorted({

            assignment.session_id

            for assignment

            in self._assignments.values()

            if (

                assignment.tag_id

                == tag_id
            )
        })

    def list_assignments_for_session(

        self,

        session_id,

    ):

        assignments = [

            assignment

            for assignment

            in self._assignments.values()

            if (

                assignment.session_id

                == session_id
            )
        ]

        return [

            deepcopy(
                assignment
            )

            for assignment

            in sorted(

                assignments,

                key=lambda item:
                    item.tag_id,
            )
        ]

    def export_state(self):

        return {

            "tags":
                deepcopy(
                    self._tags
                ),

            "assignments":
                deepcopy(
                    self._assignments
                ),
        }

    def restore_state(

        self,

        state,

    ) -> None:

        self._tags = deepcopy(

            state["tags"]
        )

        self._assignments = deepcopy(

            state["assignments"]
        )
