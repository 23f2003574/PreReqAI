from datetime import datetime

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)


class ResearchSessionSerializer:
    """
    Converts visual research workspace
    state into persistent session
    snapshots.
    """

    def serialize(

        self,

        session_id: str,

        workspace,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ) -> ResearchSessionSnapshot:

        snapshot = workspace.snapshot()

        selected_object = snapshot.get(
            "selected_object"
        )

        breadcrumb_items = snapshot.get(
            "breadcrumbs",

            [],
        )

        selected_section = next(

            (

                item

                for item

                in reversed(
                    breadcrumb_items
                )

                if item.context_type

                == "section"
            ),

            None,
        )

        selected_graph_node = next(

            (

                item

                for item

                in reversed(
                    breadcrumb_items
                )

                if item.context_type
                .startswith(
                    "graph_"
                )
            ),

            None,
        )

        return ResearchSessionSnapshot(

            session_id=session_id,

            paper_id=paper_id,

            paper_title=paper_title,

            active_view=(

                snapshot.get(
                    "active_view"
                )

                or "paper"
            ),

            selected_object_id=(

                getattr(

                    selected_object,

                    "id",

                    None,
                )
            ),

            selected_section_id=(

                getattr(

                    selected_section,

                    "id",

                    None,
                )
            ),

            selected_graph_node_id=(

                getattr(

                    selected_graph_node,

                    "id",

                    None,
                )
            ),

            breadcrumbs=[

                {

                    "id": item.id,

                    "label": item.label,

                    "context_type":
                        item.context_type,
                }

                for item

                in breadcrumb_items
            ],

            timeline=[

                {

                    "id": step.id,

                    "title": step.title,

                    "status": (

                        step.status.value

                        if hasattr(

                            step.status,

                            "value",
                        )

                        else str(
                            step.status
                        )
                    ),
                }

                for step

                in snapshot.get(

                    "timeline",

                    [],
                )
            ],

            interaction_history=[

                {

                    "id": entry.id,

                    "object_id":
                        entry.object_id,

                    "object_title":
                        entry.object_title,

                    "action":
                        entry.action,

                    "timestamp": (

                        entry.timestamp
                        .isoformat()
                    ),
                }

                for entry

                in snapshot.get(

                    "history",

                    [],
                )
            ],

            recommendations=[

                {

                    "id":
                        recommendation.id,

                    "title":
                        recommendation.title,

                    "description":
                        recommendation.description,

                    "action":
                        recommendation.action,

                    "object_id":
                        recommendation.object_id,

                    "priority":
                        recommendation.priority,
                }

                for recommendation

                in snapshot.get(

                    "recommendations",

                    [],
                )
            ],

            metadata={

                "workspace_event_count": (

                    len(

                        workspace.workspace
                        .workspace_events()
                    )
                )
            },

            updated_at=datetime.utcnow(),
        )
