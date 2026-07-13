from collections import (
    Counter,
    defaultdict,
)

from .research_integrity_finding import (
    ResearchIntegrityFinding,
)

from .research_integrity_report import (
    ResearchIntegrityReport,
)

from .research_integrity_severity import (
    ResearchIntegritySeverity,
)


class ResearchWorkspaceIntegrityAuditor:
    """
    Performs read-only structural,
    referential, graph, and semantic
    integrity checks across the workspace.
    """

    def __init__(

        self,

        session_manager,

        profile_store,

        checkpoint_store,

        version_store,

        branch_store,

        tag_store,

        collection_store,

        activity_store,

    ):

        self.session_manager = (
            session_manager
        )

        self.profile_store = (
            profile_store
        )

        self.checkpoint_store = (
            checkpoint_store
        )

        self.version_store = (
            version_store
        )

        self.branch_store = (
            branch_store
        )

        self.tag_store = (
            tag_store
        )

        self.collection_store = (
            collection_store
        )

        self.activity_store = (
            activity_store
        )

    def _build_context(self):

        sessions = list(

            self.session_manager
            .list_sessions()
        )

        profiles = list(

            self.profile_store
            .list_all()
        )

        checkpoints = list(

            self.checkpoint_store
            .list_all()
        )

        versions = list(

            self.version_store
            .list_all()
        )

        branches = list(

            self.branch_store
            .list_all()
        )

        tags = list(

            self.tag_store
            .list_tags()
        )

        collections = list(

            self.collection_store
            .list_collections()
        )

        tag_assignments = list(

            self.tag_store
            .list_all_assignments()
        )

        collection_memberships = list(

            self.collection_store
            .list_all_memberships()
        )

        activity_events = list(

            self.activity_store
            .list_all()
        )

        return {

            "sessions":
                sessions,

            "profiles":
                profiles,

            "checkpoints":
                checkpoints,

            "versions":
                versions,

            "branches":
                branches,

            "tags":
                tags,

            "collections":
                collections,

            "tag_assignments":
                tag_assignments,

            "collection_memberships":
                collection_memberships,

            "activity_events":
                activity_events,

            "session_ids": {

                session.session_id

                for session

                in sessions
            },

            "checkpoint_ids": {

                checkpoint.id

                for checkpoint

                in checkpoints
            },

            "version_ids": {

                version.id

                for version

                in versions
            },

            "tag_ids": {

                tag.id

                for tag

                in tags
            },

            "collection_ids": {

                collection.id

                for collection

                in collections
            },
        }

    def _audit_orphan_profiles(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        for profile in (

            context["profiles"]

        ):

            if (

                profile.session_id

                in session_ids
            ):

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "orphan_profile"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message=(

                        "Research session "
                        "profile references "
                        "a missing session."
                    ),

                    entity_type=(
                        "profile"
                    ),

                    entity_id=(
                        profile.session_id
                    ),

                    related_entity_ids=[

                        profile.session_id
                    ],
                )
            )

    def _audit_missing_profiles(

        self,

        context,

        findings,

    ):

        profile_session_ids = {

            profile.session_id

            for profile

            in context["profiles"]
        }

        for session_id in (

            context["session_ids"]

        ):

            if (

                session_id

                in profile_session_ids
            ):

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "missing_profile"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message=(

                        "Research session has "
                        "no human-readable "
                        "profile."
                    ),

                    entity_type=(
                        "session"
                    ),

                    entity_id=(
                        session_id
                    ),
                )
            )

    def _audit_checkpoint_references(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        version_ids = (
            context["version_ids"]
        )

        for checkpoint in (

            context["checkpoints"]

        ):

            if (

                checkpoint.session_id

                not in session_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "orphan_checkpoint"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Checkpoint references "
                            "a missing research "
                            "session."
                        ),

                        entity_type=(
                            "checkpoint"
                        ),

                        entity_id=(
                            checkpoint.id
                        ),

                        related_entity_ids=[

                            checkpoint
                            .session_id
                        ],
                    )
                )

            version_id = (

                checkpoint
                .snapshot_version_id
            )

            if (

                version_id is not None

                and

                version_id
                not in version_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "checkpoint_version_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Checkpoint references "
                            "a missing immutable "
                            "version."
                        ),

                        entity_type=(
                            "checkpoint"
                        ),

                        entity_id=(
                            checkpoint.id
                        ),

                        related_entity_ids=[

                            version_id
                        ],
                    )
                )

    def _audit_version_references(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        for version in (

            context["versions"]

        ):

            if (

                version.session_id

                in session_ids
            ):

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "version_session_missing"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message=(

                        "Research version "
                        "references a missing "
                        "session."
                    ),

                    entity_type=(
                        "version"
                    ),

                    entity_id=(
                        version.id
                    ),

                    related_entity_ids=[

                        version.session_id
                    ],
                )
            )

    def _audit_branch_references(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        for branch in (

            context["branches"]

        ):

            if (

                branch.source_session_id

                not in session_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "dangling_branch_parent"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Branch references "
                            "a missing parent "
                            "session."
                        ),

                        entity_type=(
                            "branch"
                        ),

                        entity_id=(
                            branch.id
                        ),

                        related_entity_ids=[

                            branch
                            .source_session_id,

                            branch
                            .branch_session_id,
                        ],
                    )
                )

            if (

                branch.branch_session_id

                not in session_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "dangling_branch_child"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Branch references "
                            "a missing child "
                            "session."
                        ),

                        entity_type=(
                            "branch"
                        ),

                        entity_id=(
                            branch.id
                        ),

                        related_entity_ids=[

                            branch
                            .source_session_id,

                            branch
                            .branch_session_id,
                        ],
                    )
                )

    def _audit_self_branches(

        self,

        context,

        findings,

    ):

        for branch in (

            context["branches"]

        ):

            if (

                branch.source_session_id

                != branch.branch_session_id
            ):

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "self_branch"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message=(

                        "Research session "
                        "branches directly to "
                        "itself."
                    ),

                    entity_type=(
                        "branch"
                    ),

                    entity_id=(
                        branch.id
                    ),

                    related_entity_ids=[

                        branch
                        .branch_session_id
                    ],
                )
            )

    def _audit_duplicate_branches(

        self,

        context,

        findings,

    ):

        relationships = [

            (

                branch.source_session_id,

                branch.branch_session_id,
            )

            for branch

            in context["branches"]
        ]

        counts = Counter(
            relationships
        )

        for (

            relationship,
            count,

        ) in counts.items():

            if count <= 1:

                continue

            (

                source_session_id,
                branch_session_id,

            ) = relationship

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "duplicate_branch"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message=(

                        "Duplicate research "
                        "branch relationship "
                        "detected."
                    ),

                    entity_type=(
                        "branch"
                    ),

                    related_entity_ids=[

                        source_session_id,

                        branch_session_id,
                    ],

                    metadata={

                        "count":
                            count,
                    },
                )
            )

    def _audit_multiple_branch_parents(

        self,

        context,

        findings,

    ):

        parents_by_child = (

            defaultdict(
                set
            )
        )

        for branch in (

            context["branches"]

        ):

            parents_by_child[

                branch.branch_session_id

            ].add(

                branch.source_session_id
            )

        for (

            child_id,
            parent_ids,

        ) in (

            parents_by_child.items()

        ):

            if len(parent_ids) <= 1:

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "multiple_branch_parents"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message=(

                        "Research session has "
                        "multiple branch "
                        "parents."
                    ),

                    entity_type=(
                        "session"
                    ),

                    entity_id=(
                        child_id
                    ),

                    related_entity_ids=(
                        sorted(
                            parent_ids
                        )
                    ),
                )
            )

    @staticmethod
    def _canonicalize_cycle(

        cycle,

    ):

        nodes = list(
            cycle[:-1]
        )

        rotations = [

            tuple(

                nodes[index:]

                + nodes[:index]
            )

            for index

            in range(
                len(nodes)
            )
        ]

        return min(
            rotations
        )

    def _audit_lineage_cycles(

        self,

        context,

        findings,

    ):

        adjacency = defaultdict(
            list
        )

        for branch in (

            context["branches"]

        ):

            adjacency[

                branch.source_session_id

            ].append(

                branch.branch_session_id
            )

        visiting = set()

        visited = set()

        reported_cycles = set()

        def visit(

            session_id,

            path,

        ):

            if session_id in visiting:

                cycle_start = (

                    path.index(
                        session_id
                    )
                )

                cycle = (

                    path[cycle_start:]

                    + [session_id]
                )

                canonical = (

                    self
                    ._canonicalize_cycle(

                        cycle
                    )
                )

                if (

                    canonical

                    not in reported_cycles
                ):

                    reported_cycles.add(
                        canonical
                    )

                    findings.append(

                        ResearchIntegrityFinding(

                            code=(
                                "lineage_cycle"
                            ),

                            severity=(

                                ResearchIntegritySeverity
                                .CRITICAL
                            ),

                            message=(

                                "Research lineage "
                                "contains a cycle."
                            ),

                            entity_type=(
                                "lineage"
                            ),

                            related_entity_ids=(
                                cycle
                            ),
                        )
                    )

                return

            if session_id in visited:

                return

            visiting.add(
                session_id
            )

            path.append(
                session_id
            )

            for child_id in (

                adjacency.get(

                    session_id,

                    [],
                )

            ):

                visit(

                    child_id,

                    path,
                )

            path.pop()

            visiting.remove(
                session_id
            )

            visited.add(
                session_id
            )

        for session_id in (

            context["session_ids"]

        ):

            if session_id not in visited:

                visit(
                    session_id,

                    [],
                )

    def _audit_tag_assignments(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        tag_ids = (
            context["tag_ids"]
        )

        for assignment in (

            context["tag_assignments"]

        ):

            if (

                assignment.session_id

                not in session_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "tag_assignment_session_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Tag assignment "
                            "references a missing "
                            "research session."
                        ),

                        entity_type=(
                            "tag_assignment"
                        ),

                        related_entity_ids=[

                            assignment
                            .session_id,

                            assignment.tag_id,
                        ],
                    )
                )

            if (

                assignment.tag_id

                not in tag_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "tag_assignment_tag_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Tag assignment "
                            "references a missing "
                            "research tag."
                        ),

                        entity_type=(
                            "tag_assignment"
                        ),

                        related_entity_ids=[

                            assignment
                            .session_id,

                            assignment.tag_id,
                        ],
                    )
                )

    def _audit_duplicate_tag_assignments(

        self,

        context,

        findings,

    ):

        relationships = [

            (

                assignment.session_id,

                assignment.tag_id,
            )

            for assignment

            in context[
                "tag_assignments"
            ]
        ]

        for (

            relationship,
            count,

        ) in Counter(
            relationships
        ).items():

            if count <= 1:

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "duplicate_tag_assignment"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message=(

                        "Duplicate tag "
                        "assignment detected."
                    ),

                    entity_type=(
                        "tag_assignment"
                    ),

                    related_entity_ids=(
                        list(
                            relationship
                        )
                    ),

                    metadata={

                        "count":
                            count,
                    },
                )
            )

    def _audit_collection_memberships(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        collection_ids = (
            context["collection_ids"]
        )

        for membership in (

            context[
                "collection_memberships"
            ]

        ):

            if (

                membership.session_id

                not in session_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "collection_membership_session_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Collection membership "
                            "references a missing "
                            "session."
                        ),

                        entity_type=(
                            "collection_membership"
                        ),

                        related_entity_ids=[

                            membership
                            .collection_id,

                            membership
                            .session_id,
                        ],
                    )
                )

            if (

                membership.collection_id

                not in collection_ids
            ):

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "collection_membership_collection_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .ERROR
                        ),

                        message=(

                            "Collection membership "
                            "references a missing "
                            "collection."
                        ),

                        entity_type=(
                            "collection_membership"
                        ),

                        related_entity_ids=[

                            membership
                            .collection_id,

                            membership
                            .session_id,
                        ],
                    )
                )

    def _audit_duplicate_collection_memberships(

        self,

        context,

        findings,

    ):

        relationships = [

            (

                membership.collection_id,

                membership.session_id,
            )

            for membership

            in context[
                "collection_memberships"
            ]
        ]

        for (

            relationship,
            count,

        ) in Counter(
            relationships
        ).items():

            if count <= 1:

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=(
                        "duplicate_collection_membership"
                    ),

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message=(

                        "Duplicate collection "
                        "membership detected."
                    ),

                    entity_type=(
                        "collection_membership"
                    ),

                    related_entity_ids=(
                        list(
                            relationship
                        )
                    ),

                    metadata={

                        "count":
                            count,
                    },
                )
            )

    def _audit_activity_references(

        self,

        context,

        findings,

    ):

        session_ids = (
            context["session_ids"]
        )

        for event in (

            context["activity_events"]

        ):

            for field_name in [

                "session_id",

                "related_session_id",
            ]:

                session_id = (

                    getattr(

                        event,

                        field_name,

                        None,
                    )
                )

                if session_id is None:

                    continue

                if session_id in session_ids:

                    continue

                findings.append(

                    ResearchIntegrityFinding(

                        code=(
                            "activity_session_missing"
                        ),

                        severity=(

                            ResearchIntegritySeverity
                            .WARNING
                        ),

                        message=(

                            "Historical activity "
                            "references a missing "
                            "session."
                        ),

                        entity_type=(
                            "activity_event"
                        ),

                        entity_id=(
                            event.id
                        ),

                        related_entity_ids=[

                            session_id
                        ],

                        metadata={

                            "reference_field":
                                field_name,
                        },
                    )
                )

    def _audit_duplicate_ids(

        self,

        records,

        id_getter,

        entity_type,

        code,

        findings,

    ):

        ids = [

            id_getter(record)

            for record

            in records
        ]

        for (

            entity_id,
            count,

        ) in Counter(ids).items():

            if count <= 1:

                continue

            findings.append(

                ResearchIntegrityFinding(

                    code=code,

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message=(

                        "Duplicate "
                        f"{entity_type} "
                        "identifier detected."
                    ),

                    entity_type=(
                        entity_type
                    ),

                    entity_id=(
                        entity_id
                    ),

                    metadata={

                        "count":
                            count,
                    },
                )
            )

    def _audit_duplicate_entity_ids(

        self,

        context,

        findings,

    ):

        self._audit_duplicate_ids(

            context["sessions"],

            lambda item:
                item.session_id,

            "session",

            "duplicate_session_id",

            findings,
        )

        self._audit_duplicate_ids(

            context["checkpoints"],

            lambda item: item.id,

            "checkpoint",

            "duplicate_checkpoint_id",

            findings,
        )

        self._audit_duplicate_ids(

            context["versions"],

            lambda item: item.id,

            "version",

            "duplicate_version_id",

            findings,
        )

        self._audit_duplicate_ids(

            context["tags"],

            lambda item: item.id,

            "tag",

            "duplicate_tag_id",

            findings,
        )

        self._audit_duplicate_ids(

            context["collections"],

            lambda item: item.id,

            "collection",

            "duplicate_collection_id",

            findings,
        )

        self._audit_duplicate_ids(

            context["activity_events"],

            lambda item: item.id,

            "activity_event",

            "duplicate_activity_event_id",

            findings,
        )

    @staticmethod
    def _severity_rank(

        severity,

    ):

        ranking = {

            ResearchIntegritySeverity
            .CRITICAL: 0,

            ResearchIntegritySeverity
            .ERROR: 1,

            ResearchIntegritySeverity
            .WARNING: 2,

            ResearchIntegritySeverity
            .INFO: 3,
        }

        return ranking[severity]

    def audit(self):

        context = (
            self._build_context()
        )

        findings = []

        self._audit_orphan_profiles(

            context,

            findings,
        )

        self._audit_missing_profiles(

            context,

            findings,
        )

        self._audit_checkpoint_references(

            context,

            findings,
        )

        self._audit_version_references(

            context,

            findings,
        )

        self._audit_branch_references(

            context,

            findings,
        )

        self._audit_self_branches(

            context,

            findings,
        )

        self._audit_duplicate_branches(

            context,

            findings,
        )

        self._audit_multiple_branch_parents(

            context,

            findings,
        )

        self._audit_lineage_cycles(

            context,

            findings,
        )

        self._audit_tag_assignments(

            context,

            findings,
        )

        self._audit_duplicate_tag_assignments(

            context,

            findings,
        )

        self._audit_collection_memberships(

            context,

            findings,
        )

        self._audit_duplicate_collection_memberships(

            context,

            findings,
        )

        self._audit_activity_references(

            context,

            findings,
        )

        self._audit_duplicate_entity_ids(

            context,

            findings,
        )

        findings.sort(

            key=lambda finding: (

                self._severity_rank(
                    finding.severity
                ),

                finding.code,

                finding.entity_id
                or "",
            )
        )

        return (

            ResearchIntegrityReport(

                findings=findings
            )
        )
