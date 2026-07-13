from copy import (
    deepcopy,
)

import json

from pathlib import (
    Path,
)

from threading import (
    RLock,
)

from .research_workspace_change_event import (
    ResearchWorkspaceChangeEvent,
)

from .research_workspace_change_page import (
    ResearchWorkspaceChangePage,
)


class ResearchWorkspaceChangeFeed:
    """
    Stores ordered workspace change events
    and supports cursor-based synchronization.
    """

    def __init__(

        self,

        storage_path=None,

        event_bus=None,

    ):

        self.storage_path = (

            Path(
                storage_path
            )

            if storage_path

            else None
        )

        self.event_bus = (
            event_bus
        )

        self._events = []

        self._last_sequence = 0

        self._lock = RLock()

        self._load()

    def _load(self):

        if self.storage_path is None:

            return

        if not self.storage_path.exists():

            return

        payload = json.loads(

            self.storage_path
            .read_text(
                encoding="utf-8"
            )
        )

        self._events = [

            ResearchWorkspaceChangeEvent
            .from_dict(
                record
            )

            for record

            in payload.get(
                "events",
                [],
            )
        ]

        self._last_sequence = (

            payload.get(
                "last_sequence",
                0,
            )
        )

    def _persist(self):

        if self.storage_path is None:

            return

        self.storage_path.parent.mkdir(

            parents=True,

            exist_ok=True,
        )

        payload = {

            "last_sequence":
                self._last_sequence,

            "events": [

                event.to_dict()

                for event

                in self._events
            ],
        }

        temporary_path = (

            self.storage_path
            .with_suffix(

                self.storage_path.suffix

                + ".tmp"
            )
        )

        temporary_path.write_text(

            json.dumps(

                payload,

                indent=2,

                sort_keys=True,
            ),

            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )

    def append(

        self,

        operation,

        entity_type,

        entity_id=None,

        related_entity_ids=None,

        metadata=None,

    ):

        with self._lock:

            sequence = (

                self._last_sequence

                + 1
            )

            event = (

                ResearchWorkspaceChangeEvent
                .create(

                    sequence=(
                        sequence
                    ),

                    operation=(
                        operation
                    ),

                    entity_type=(
                        entity_type
                    ),

                    entity_id=(
                        entity_id
                    ),

                    related_entity_ids=(

                        related_entity_ids
                    ),

                    metadata=(
                        metadata
                    ),
                )
            )

            self._events.append(
                event
            )

            self._last_sequence = (
                sequence
            )

            self._persist()

        if self.event_bus is not None:

            self.event_bus.publish(
                event
            )

        return event

    def get_changes(

        self,

        after_sequence=0,

        limit=100,

        entity_types=None,

        operations=None,

    ):

        if limit <= 0:

            raise ValueError(

                "Change feed limit "
                "must be greater than zero."
            )

        entity_types = set(

            entity_types
            or []
        )

        operations = set(

            operations
            or []
        )

        with self._lock:

            matching = [

                event

                for event

                in self._events

                if (

                    event.sequence

                    > after_sequence
                )

                and

                (

                    not entity_types

                    or

                    event.entity_type

                    in entity_types
                )

                and

                (

                    not operations

                    or

                    event.operation.value

                    in operations
                )
            ]

            selected = (

                matching[
                    :limit
                ]
            )

            has_more = (

                len(
                    matching
                )

                > len(
                    selected
                )
            )

            next_cursor = (

                selected[-1]
                .sequence

                if selected

                else None
            )

            return (

                ResearchWorkspaceChangePage(

                    events=(

                        deepcopy(
                            selected
                        )
                    ),

                    next_cursor=(
                        next_cursor
                    ),

                    has_more=(
                        has_more
                    ),
                )
            )

    @property
    def latest_sequence(self):

        with self._lock:

            return self._last_sequence

    def export_state(self):

        with self._lock:

            return {

                "events":
                    deepcopy(
                        self._events
                    ),

                "last_sequence":
                    self._last_sequence,
            }

    def restore_state(

        self,

        state,

    ):

        with self._lock:

            self._events = deepcopy(

                state[
                    "events"
                ]
            )

            self._last_sequence = (

                state[
                    "last_sequence"
                ]
            )

            self._persist()
