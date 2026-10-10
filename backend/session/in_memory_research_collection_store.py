from copy import (
    deepcopy,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)

from .research_collection_store import (
    ResearchCollectionStore,
)


class InMemoryResearchCollectionStore(
    ResearchCollectionStore,
):
    """
    Stores research collections and
    memberships in memory.
    """

    def __init__(self):

        self._collections = {}

        self._memberships = {}

    def save_collection(

        self,

        collection,

    ):

        self._collections[
            collection.id
        ] = deepcopy(
            collection
        )

    def get_collection(

        self,

        collection_id,

    ):

        collection = (

            self._collections.get(

                collection_id
            )
        )

        return (

            deepcopy(
                collection
            )

            if collection is not None

            else None
        )

    def list_collections(self):

        return [

            deepcopy(
                collection
            )

            for collection

            in self._collections.values()
        ]

    def delete_collection(

        self,

        collection_id,

    ):

        removed = (

            self._collections.pop(

                collection_id,

                None,
            )
        )

        if removed is None:

            return False

        membership_keys = [

            key

            for key

            in self._memberships

            if key[0] == collection_id
        ]

        for key in membership_keys:

            del self._memberships[
                key
            ]

        return True

    def add_membership(

        self,

        membership,

    ):

        key = (

            membership.collection_id,

            membership.session_id,
        )

        if key in self._memberships:

            return False

        self._memberships[
            key
        ] = deepcopy(
            membership
        )

        return True

    def remove_membership(

        self,

        collection_id,

        session_id,

    ):

        key = (

            collection_id,

            session_id,
        )

        return (

            self._memberships.pop(

                key,

                None,
            )

            is not None
        )

    def list_session_ids(

        self,

        collection_id,

    ):

        return sorted({

            membership.session_id

            for membership

            in self._memberships.values()

            if (

                membership.collection_id

                == collection_id
            )
        })

    def list_for_session(

        self,

        session_id,

    ):

        collection_ids = {

            membership.collection_id

            for membership

            in self._memberships.values()

            if (

                membership.session_id

                == session_id
            )
        }

        return [

            deepcopy(

                self._collections[
                    collection_id
                ]
            )

            for collection_id

            in sorted(
                collection_ids
            )

            if (

                collection_id

                in self._collections
            )
        ]

    def list_memberships_for_session(

        self,

        session_id,

    ):

        memberships = [

            membership

            for membership

            in self._memberships.values()

            if (

                membership.session_id

                == session_id
            )
        ]

        return [

            deepcopy(
                membership
            )

            for membership

            in sorted(

                memberships,

                key=lambda item:
                    item.collection_id,
            )
        ]

    def export_state(self):

        return {

            "collections":
                deepcopy(
                    self._collections
                ),

            "memberships":
                deepcopy(
                    self._memberships
                ),
        }

    def restore_state(

        self,

        state,

    ) -> None:

        self._collections = deepcopy(

            state["collections"]
        )

        self._memberships = deepcopy(

            state["memberships"]
        )

    def list_all_memberships(

        self,

    ) -> list[
        ResearchCollectionMembership
    ]:

        return [

            deepcopy(
                membership
            )

            for membership

            in sorted(

                self._memberships.values(),

                key=lambda item: (
                    item.collection_id,
                    item.session_id,
                ),
            )
        ]
