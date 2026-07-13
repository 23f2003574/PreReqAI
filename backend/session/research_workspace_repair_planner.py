from .research_repair_action import (
    ResearchRepairAction,
)

from .research_repair_plan import (
    ResearchRepairPlan,
)

from .research_repair_risk import (
    ResearchRepairRisk,
)


class ResearchWorkspaceRepairPlanner:
    """
    Converts integrity findings into explicit
    repair recommendations without mutating
    workspace state.
    """

    def _plan_missing_profile(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "create_default_profile"
                ),

                description=(

                    "Create a default "
                    "human-readable profile "
                    "for the research "
                    "session."
                ),

                risk=(

                    ResearchRepairRisk
                    .REVIEW
                ),

                entity_type=(
                    "session"
                ),

                entity_id=(
                    finding.entity_id
                ),

                automatic=False,
            )
        )

    def _plan_duplicate_branch(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "deduplicate_branch"
                ),

                description=(

                    "Keep one branch "
                    "relationship and "
                    "remove exact "
                    "duplicates."
                ),

                risk=(

                    ResearchRepairRisk
                    .SAFE
                ),

                entity_type=(
                    "branch"
                ),

                parameters={

                    "source_session_id":

                        finding
                        .related_entity_ids[
                            0
                        ],

                    "branch_session_id":

                        finding
                        .related_entity_ids[
                            1
                        ],
                },

                automatic=True,
            )
        )

    def _plan_duplicate_tag_assignment(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "deduplicate_tag_assignment"
                ),

                description=(

                    "Keep one tag "
                    "assignment and remove "
                    "exact duplicates."
                ),

                risk=(

                    ResearchRepairRisk
                    .SAFE
                ),

                entity_type=(
                    "tag_assignment"
                ),

                parameters={

                    "session_id":

                        finding
                        .related_entity_ids[
                            0
                        ],

                    "tag_id":

                        finding
                        .related_entity_ids[
                            1
                        ],
                },

                automatic=True,
            )
        )

    def _plan_duplicate_collection_membership(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "deduplicate_collection_membership"
                ),

                description=(

                    "Keep one collection "
                    "membership and remove "
                    "exact duplicates."
                ),

                risk=(

                    ResearchRepairRisk
                    .SAFE
                ),

                entity_type=(
                    "collection_membership"
                ),

                parameters={

                    "collection_id":

                        finding
                        .related_entity_ids[
                            0
                        ],

                    "session_id":

                        finding
                        .related_entity_ids[
                            1
                        ],
                },

                automatic=True,
            )
        )

    def _plan_orphan_checkpoint(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "review_orphan_checkpoint"
                ),

                description=(

                    "Review the orphan "
                    "checkpoint before "
                    "deciding whether to "
                    "reassociate or delete "
                    "it."
                ),

                risk=(

                    ResearchRepairRisk
                    .REVIEW
                ),

                entity_type=(
                    "checkpoint"
                ),

                entity_id=(
                    finding.entity_id
                ),

                automatic=False,
            )
        )

    def _plan_orphan_profile(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "review_orphan_profile"
                ),

                description=(

                    "Review the orphan "
                    "profile before "
                    "deciding whether to "
                    "delete it."
                ),

                risk=(

                    ResearchRepairRisk
                    .REVIEW
                ),

                entity_type=(
                    "profile"
                ),

                entity_id=(
                    finding.entity_id
                ),

                automatic=False,
            )
        )

    def _plan_lineage_cycle(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "review_lineage_cycle"
                ),

                description=(

                    "Review the lineage "
                    "cycle and explicitly "
                    "choose which branch "
                    "relationship to "
                    "remove."
                ),

                risk=(

                    ResearchRepairRisk
                    .REVIEW
                ),

                entity_type=(
                    "lineage"
                ),

                parameters={

                    "cycle_session_ids":

                        list(

                            finding
                            .related_entity_ids
                        ),
                },

                automatic=False,
            )
        )

    def _plan_multiple_branch_parents(

        self,

        finding,

    ):

        return (

            ResearchRepairAction(

                finding_code=(
                    finding.code
                ),

                action_type=(
                    "review_multiple_branch_parents"
                ),

                description=(

                    "Review the conflicting "
                    "branch parents and "
                    "explicitly choose the "
                    "canonical one."
                ),

                risk=(

                    ResearchRepairRisk
                    .REVIEW
                ),

                entity_type=(
                    "session"
                ),

                entity_id=(
                    finding.entity_id
                ),

                parameters={

                    "candidate_parent_session_ids":

                        list(

                            finding
                            .related_entity_ids
                        ),
                },

                automatic=False,
            )
        )

    def plan(

        self,

        report,

    ):

        actions = []

        planners = {

            "missing_profile":
                self._plan_missing_profile,

            "duplicate_branch":
                self._plan_duplicate_branch,

            "duplicate_tag_assignment":
                self._plan_duplicate_tag_assignment,

            "duplicate_collection_membership":
                self._plan_duplicate_collection_membership,

            "orphan_checkpoint":
                self._plan_orphan_checkpoint,

            "orphan_profile":
                self._plan_orphan_profile,

            "lineage_cycle":
                self._plan_lineage_cycle,

            "multiple_branch_parents":
                self._plan_multiple_branch_parents,
        }

        for finding in (

            report.findings

        ):

            planner = (

                planners.get(
                    finding.code
                )
            )

            if planner is None:

                actions.append(

                    ResearchRepairAction(

                        finding_code=(
                            finding.code
                        ),

                        action_type=(
                            "manual_review"
                        ),

                        description=(

                            "Review this "
                            "integrity finding "
                            "manually."
                        ),

                        risk=(

                            ResearchRepairRisk
                            .REVIEW
                        ),

                        entity_type=(
                            finding
                            .entity_type
                        ),

                        entity_id=(
                            finding
                            .entity_id
                        ),

                        automatic=False,
                    )
                )

                continue

            actions.append(

                planner(finding)
            )

        return (

            ResearchRepairPlan(

                actions=actions
            )
        )
