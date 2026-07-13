from datetime import (
    datetime,
    timezone,
)

from uuid import (
    uuid4,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_type import (
    ResearchActivityType,
)

from .research_collection import (
    ResearchCollection,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)

from .research_session_tag_assignment import (
    ResearchSessionTagAssignment,
)

from .research_tag import (
    ResearchTag,
)

from .research_tag_normalizer import (
    normalize_research_tag_name,
)


class ResearchWorkspaceOrganizationService:
    """
    Manages tags, collections, and
    session organization relationships.
    """

    def __init__(

        self,

        session_manager,

        tag_store,

        collection_store,

        activity_recorder=None,

    ):

        self.session_manager = (
            session_manager
        )

        self.tag_store = (
            tag_store
        )

        self.collection_store = (
            collection_store
        )

        self.activity_recorder = (
            activity_recorder
        )

    def _record(

        self,

        activity_type,

        **kwargs,

    ):

        if self.activity_recorder is None:

            return

        self.activity_recorder.record(

            activity_type,

            actor_type=(

                ResearchActivityActorType
                .USER
            ),

            **kwargs,
        )

    @staticmethod
    def _now():

        return datetime.now(
            timezone.utc
        )

    def _require_session(

        self,

        session_id,

    ):

        session = (

            self.session_manager
            .load_session(

                session_id
            )
        )

        if session is None:

            raise ValueError(

                "Research session "
                "does not exist: "
                f"{session_id}"
            )

        return session

    def get_or_create_tag(

        self,

        name: str,

    ):

        normalized = (

            normalize_research_tag_name(

                name
            )
        )

        existing = (

            self.tag_store
            .get_tag_by_name(

                normalized
            )
        )

        if existing is not None:

            return existing

        tag = ResearchTag(

            id=str(
                uuid4()
            ),

            name=normalized,

            created_at=(
                self._now()
            ),
        )

        self.tag_store.save_tag(
            tag
        )

        return tag

    def tag_session(

        self,

        session_id: str,

        tag_name: str,

    ):

        self._require_session(

            session_id
        )

        tag = (

            self.get_or_create_tag(

                tag_name
            )
        )

        assignment = (

            ResearchSessionTagAssignment(

                session_id=(
                    session_id
                ),

                tag_id=(
                    tag.id
                ),

                assigned_at=(
                    self._now()
                ),
            )
        )

        created = (

            self.tag_store.assign(

                assignment
            )
        )

        if created:

            self._record(

                ResearchActivityType
                .TAG_ASSIGNED,

                session_id=session_id,

                metadata={

                    "tag_id":
                        tag.id,

                    "tag_name":
                        tag.name,
                },
            )

        return tag

    def untag_session(

        self,

        session_id: str,

        tag_name: str,

    ):

        normalized = (

            normalize_research_tag_name(

                tag_name
            )
        )

        tag = (

            self.tag_store
            .get_tag_by_name(

                normalized
            )
        )

        if tag is None:

            return False

        removed = (

            self.tag_store
            .unassign(

                session_id,

                tag.id,
            )
        )

        if removed:

            self._record(

                ResearchActivityType
                .TAG_REMOVED,

                session_id=session_id,

                metadata={

                    "tag_id":
                        tag.id,

                    "tag_name":
                        tag.name,
                },
            )

        return removed

    def tags_for_session(

        self,

        session_id: str,

    ):

        self._require_session(

            session_id
        )

        return (

            self.tag_store
            .list_for_session(

                session_id
            )
        )

    def create_collection(

        self,

        name: str,

        description: str | None = None,

    ):

        normalized_name = (
            name.strip()
        )

        if not normalized_name:

            raise ValueError(

                "Research collection "
                "name cannot be empty"
            )

        now = self._now()

        collection = (

            ResearchCollection(

                id=str(
                    uuid4()
                ),

                name=(
                    normalized_name
                ),

                description=(

                    description.strip()

                    if (

                        description is not None

                        and description.strip()
                    )

                    else None
                ),

                created_at=now,

                updated_at=now,
            )
        )

        self.collection_store.save_collection(

            collection
        )

        self._record(

            ResearchActivityType
            .COLLECTION_CREATED,

            metadata={

                "collection_id":
                    collection.id,

                "collection_name":
                    collection.name,
            },
        )

        return collection

    def update_collection(

        self,

        collection_id: str,

        name: str | None = None,

        description: str | None = None,

    ):

        collection = (

            self.collection_store
            .get_collection(

                collection_id
            )
        )

        if collection is None:

            raise ValueError(

                "Research collection "
                "does not exist: "
                f"{collection_id}"
            )

        old_name = collection.name

        old_description = (
            collection.description
        )

        if name is not None:

            normalized_name = (
                name.strip()
            )

            if not normalized_name:

                raise ValueError(

                    "Research collection "
                    "name cannot be empty"
                )

            collection.name = (
                normalized_name
            )

        if description is not None:

            collection.description = (

                description.strip()

                or None
            )

        changed = (

            collection.name

            != old_name

            or collection.description

            != old_description
        )

        if not changed:

            return collection

        collection.updated_at = (
            self._now()
        )

        self.collection_store.save_collection(

            collection
        )

        self._record(

            ResearchActivityType
            .COLLECTION_UPDATED,

            metadata={

                "collection_id":
                    collection.id,

                "collection_name":
                    collection.name,
            },
        )

        return collection

    def add_session_to_collection(

        self,

        collection_id: str,

        session_id: str,

    ):

        self._require_session(

            session_id
        )

        collection = (

            self.collection_store
            .get_collection(

                collection_id
            )
        )

        if collection is None:

            raise ValueError(

                "Research collection "
                "does not exist: "
                f"{collection_id}"
            )

        membership = (

            ResearchCollectionMembership(

                collection_id=(
                    collection_id
                ),

                session_id=(
                    session_id
                ),

                added_at=(
                    self._now()
                ),
            )
        )

        created = (

            self.collection_store
            .add_membership(

                membership
            )
        )

        if created:

            self._record(

                ResearchActivityType
                .COLLECTION_SESSION_ADDED,

                session_id=session_id,

                metadata={

                    "collection_id":
                        collection.id,

                    "collection_name":
                        collection.name,
                },
            )

        return membership

    def remove_session_from_collection(

        self,

        collection_id: str,

        session_id: str,

    ):

        collection = (

            self.collection_store
            .get_collection(

                collection_id
            )
        )

        removed = (

            self.collection_store
            .remove_membership(

                collection_id,

                session_id,
            )
        )

        if removed and collection is not None:

            self._record(

                ResearchActivityType
                .COLLECTION_SESSION_REMOVED,

                session_id=session_id,

                metadata={

                    "collection_id":
                        collection.id,

                    "collection_name":
                        collection.name,
                },
            )

        return removed

    def delete_collection(

        self,

        collection_id: str,

    ):

        collection = (

            self.collection_store
            .get_collection(

                collection_id
            )
        )

        deleted = (

            self.collection_store
            .delete_collection(

                collection_id
            )
        )

        if deleted and collection is not None:

            self._record(

                ResearchActivityType
                .COLLECTION_DELETED,

                metadata={

                    "collection_id":
                        collection.id,

                    "collection_name":
                        collection.name,
                },
            )

        return deleted

    def collections_for_session(

        self,

        session_id: str,

    ):

        self._require_session(

            session_id
        )

        return (

            self.collection_store
            .list_for_session(

                session_id
            )
        )

    def session_ids_in_collection(

        self,

        collection_id: str,

    ):

        collection = (

            self.collection_store
            .get_collection(

                collection_id
            )
        )

        if collection is None:

            raise ValueError(

                "Research collection "
                "does not exist: "
                f"{collection_id}"
            )

        return (

            self.collection_store
            .list_session_ids(

                collection_id
            )
        )
