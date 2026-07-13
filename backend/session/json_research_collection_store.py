from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_collection import (
    ResearchCollection,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)

from .research_collection_store import (
    ResearchCollectionStore,
)


def _default_data():

    return {

        "collections": {},

        "memberships": [],
    }


class JsonResearchCollectionStore(
    ResearchCollectionStore,
):
    """
    Persists research collections and
    memberships to JSON.
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

    def save_collection(

        self,

        collection,

    ):

        data = self.file.read()

        data["collections"][
            collection.id
        ] = collection.to_dict()

        self.file.write(
            data
        )

    def get_collection(

        self,

        collection_id,

    ):

        data = self.file.read()

        raw = (

            data["collections"].get(

                collection_id
            )
        )

        if raw is None:

            return None

        return (

            ResearchCollection
            .from_dict(

                raw
            )
        )

    def list_collections(self):

        data = self.file.read()

        return [

            ResearchCollection
            .from_dict(

                raw
            )

            for raw

            in (
                data["collections"]
                .values()
            )
        ]

    def delete_collection(

        self,

        collection_id,

    ):

        data = self.file.read()

        if (

            collection_id

            not in data["collections"]
        ):

            return False

        del data["collections"][
            collection_id
        ]

        data["memberships"] = [

            entry

            for entry

            in data["memberships"]

            if (

                entry["collection_id"]

                != collection_id
            )
        ]

        self.file.write(
            data
        )

        return True

    def add_membership(

        self,

        membership,

    ):

        data = self.file.read()

        exists = any(

            (

                entry["collection_id"]

                == membership.collection_id
            )

            and (

                entry["session_id"]

                == membership.session_id
            )

            for entry

            in data["memberships"]
        )

        if exists:

            return False

        data["memberships"].append(

            membership.to_dict()
        )

        self.file.write(
            data
        )

        return True

    def remove_membership(

        self,

        collection_id,

        session_id,

    ):

        data = self.file.read()

        remaining = [

            entry

            for entry

            in data["memberships"]

            if not (

                entry["collection_id"]

                == collection_id

                and entry["session_id"]

                == session_id
            )
        ]

        if (

            len(remaining)

            == len(
                data["memberships"]
            )
        ):

            return False

        data["memberships"] = (
            remaining
        )

        self.file.write(
            data
        )

        return True

    def list_session_ids(

        self,

        collection_id,

    ):

        data = self.file.read()

        return sorted({

            entry["session_id"]

            for entry

            in data["memberships"]

            if (

                entry["collection_id"]

                == collection_id
            )
        })

    def list_for_session(

        self,

        session_id,

    ):

        data = self.file.read()

        collection_ids = sorted({

            entry["collection_id"]

            for entry

            in data["memberships"]

            if (

                entry["session_id"]

                == session_id
            )
        })

        return [

            ResearchCollection
            .from_dict(

                data["collections"][
                    collection_id
                ]
            )

            for collection_id

            in collection_ids

            if (

                collection_id

                in data["collections"]
            )
        ]

    def list_memberships_for_session(

        self,

        session_id,

    ):

        data = self.file.read()

        matching = [

            ResearchCollectionMembership
            .from_dict(

                entry
            )

            for entry

            in data["memberships"]

            if (

                entry["session_id"]

                == session_id
            )
        ]

        return sorted(

            matching,

            key=lambda item:
                item.collection_id,
        )

    def export_state(self):

        return self.file.read()

    def restore_state(

        self,

        state,

    ) -> None:

        self.file.write(
            state
        )
