from copy import deepcopy

from dataclasses import (
    replace,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_type import (
    ResearchActivityType,
)

from .research_session_profile import (
    ResearchSessionProfile,
    utc_now,
)

from .research_session_status import (
    ResearchSessionStatus,
)


_UNSET = object()


class ResearchSessionProfileManager:
    """
    Manages mutable human-facing
    research session profiles.
    """

    def __init__(

        self,

        profile_store,

        session_manager,

        activity_recorder=None,

    ):

        self.profile_store = (
            profile_store
        )

        self.session_manager = (
            session_manager
        )

        self.activity_recorder = (
            activity_recorder
        )

    def _require_session(

        self,

        session_id: str,

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

    def create(

        self,

        session_id: str,

        display_name:
            str | None = None,

        description:
            str | None = None,

        status:
            ResearchSessionStatus = (
                ResearchSessionStatus
                .ACTIVE
            ),

        archived: bool = False,

        metadata:
            dict | None = None,

    ) -> ResearchSessionProfile:

        self._require_session(
            session_id
        )

        existing = (

            self.profile_store
            .get(

                session_id
            )
        )

        if existing is not None:

            raise ValueError(

                "Research session profile "
                "already exists: "
                f"{session_id}"
            )

        profile = (

            ResearchSessionProfile(

                session_id=(
                    session_id
                ),

                display_name=(
                    display_name
                ),

                description=(
                    description
                ),

                status=status,

                archived=archived,

                metadata=(

                    deepcopy(
                        metadata
                    )

                    if metadata

                    else {}
                ),
            )
        )

        return (

            self.profile_store
            .save(

                profile
            )
        )

    def get_or_create(

        self,

        session_id: str,

        **defaults,

    ):

        existing = (

            self.profile_store
            .get(

                session_id
            )
        )

        if existing is not None:

            return existing

        return self.create(

            session_id=(
                session_id
            ),

            **defaults,
        )

    def update(

        self,

        session_id: str,

        display_name=_UNSET,

        description=_UNSET,

        status=_UNSET,

        archived=_UNSET,

        metadata=_UNSET,

    ) -> ResearchSessionProfile:

        self._require_session(
            session_id
        )

        profile = (

            self.profile_store
            .get(

                session_id
            )
        )

        if profile is None:

            profile = (

                ResearchSessionProfile(

                    session_id=(
                        session_id
                    )
                )
            )

        changes = {}

        if display_name is not _UNSET:

            changes[
                "display_name"
            ] = display_name

        if description is not _UNSET:

            changes[
                "description"
            ] = description

        if status is not _UNSET:

            changes[
                "status"
            ] = (

                status

                if isinstance(

                    status,

                    ResearchSessionStatus,
                )

                else (

                    ResearchSessionStatus(
                        status
                    )
                )
            )

        if archived is not _UNSET:

            changes[
                "archived"
            ] = bool(
                archived
            )

        if metadata is not _UNSET:

            changes[
                "metadata"
            ] = deepcopy(

                metadata

                if metadata is not None

                else {}
            )

        changes[
            "updated_at"
        ] = utc_now()

        updated = replace(

            profile,

            **changes,
        )

        saved = (

            self.profile_store
            .save(

                updated
            )
        )

        self._record_profile_changes(

            session_id,

            profile,

            saved,
        )

        return saved

    def _record_profile_changes(

        self,

        session_id,

        old_profile,

        new_profile,

    ):

        if self.activity_recorder is None:

            return

        if (

            old_profile.display_name

            != new_profile.display_name
        ):

            self.activity_recorder.record(

                ResearchActivityType
                .SESSION_RENAMED,

                session_id=session_id,

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),

                metadata={

                    "old_name":
                        old_profile
                        .display_name,

                    "new_name":
                        new_profile
                        .display_name,
                },
            )

        if (

            old_profile.description

            != new_profile.description
        ):

            self.activity_recorder.record(

                ResearchActivityType
                .SESSION_DESCRIPTION_UPDATED,

                session_id=session_id,

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),

                metadata={

                    "old_description":
                        old_profile
                        .description,

                    "new_description":
                        new_profile
                        .description,
                },
            )

        if (

            old_profile.status

            != new_profile.status
        ):

            self.activity_recorder.record(

                ResearchActivityType
                .SESSION_STATUS_CHANGED,

                session_id=session_id,

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),

                metadata={

                    "old_status":
                        old_profile
                        .status
                        .value,

                    "new_status":
                        new_profile
                        .status
                        .value,
                },
            )

        if (

            old_profile.archived

            != new_profile.archived
        ):

            self.activity_recorder.record(

                (

                    ResearchActivityType
                    .SESSION_ARCHIVED

                    if new_profile.archived

                    else (

                        ResearchActivityType
                        .SESSION_RESTORED
                    )
                ),

                session_id=session_id,

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),
            )

    def pause(

        self,

        session_id: str,

    ):

        return self.update(

            session_id=(
                session_id
            ),

            status=(

                ResearchSessionStatus
                .PAUSED
            ),
        )

    def resume(

        self,

        session_id: str,

    ):

        return self.update(

            session_id=(
                session_id
            ),

            status=(

                ResearchSessionStatus
                .ACTIVE
            ),
        )

    def complete(

        self,

        session_id: str,

    ):

        return self.update(

            session_id=(
                session_id
            ),

            status=(

                ResearchSessionStatus
                .COMPLETED
            ),
        )

    def archive(

        self,

        session_id: str,

    ):

        return self.update(

            session_id=(
                session_id
            ),

            archived=True,
        )

    def unarchive(

        self,

        session_id: str,

    ):

        return self.update(

            session_id=(
                session_id
            ),

            archived=False,
        )

    def display_name(

        self,

        session_id: str,

    ) -> str:

        profile = (

            self.profile_store
            .get(

                session_id
            )
        )

        if (

            profile is not None

            and

            profile.display_name
        ):

            return (
                profile.display_name
            )

        session = (

            self._require_session(
                session_id
            )
        )

        paper_title = getattr(

            session,

            "paper_title",

            None,
        )

        if paper_title:

            return paper_title

        return session_id
