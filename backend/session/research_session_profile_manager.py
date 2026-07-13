from copy import deepcopy

from dataclasses import (
    replace,
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

    ):

        self.profile_store = (
            profile_store
        )

        self.session_manager = (
            session_manager
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

        return (

            self.profile_store
            .save(

                updated
            )
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
