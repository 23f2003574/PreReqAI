from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)

from .research_workspace_readiness_assessment import (
    ResearchWorkspaceReadinessAssessment,
)

from .research_workspace_readiness_check import (
    ResearchWorkspaceReadinessCheck,
)

from .research_workspace_readiness_check_status import (
    ResearchWorkspaceReadinessCheckStatus,
)

from .research_workspace_readiness_status import (
    ResearchWorkspaceReadinessStatus,
)


class ResearchWorkspaceReadinessAssessor:
    """
    Performs read-only checks to determine
    whether the research workspace is
    currently operational.
    """

    def __init__(

        self,

        capability_registry,

        session_manager,

        integrity_auditor=None,

        change_feed=None,

    ):

        self.capability_registry = (
            capability_registry
        )

        self.session_manager = (
            session_manager
        )

        self.integrity_auditor = (
            integrity_auditor
        )

        self.change_feed = (
            change_feed
        )

    def assess(self):

        checks = [

            self._check_session_workspace(),

            self._check_capability_discovery(),
        ]

        if (

            self.integrity_auditor
            is not None

            and self.capability_registry.supports(

                ResearchWorkspaceCapability
                .INTEGRITY
            )
        ):

            checks.append(
                self._check_workspace_integrity()
            )

        if (

            self.change_feed
            is not None

            and self.capability_registry.supports(

                ResearchWorkspaceCapability
                .CHANGE_FEED
            )
        ):

            checks.append(
                self._check_change_feed()
            )

        return self._aggregate(
            checks
        )

    def _check_session_workspace(self):

        try:

            self.session_manager.list_sessions()

        except Exception:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="session_workspace",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .FAIL
                    ),

                    critical=True,

                    message=(

                        "Research session workspace "
                        "could not be accessed."
                    ),

                    capability=(

                        ResearchWorkspaceCapability
                        .SESSIONS
                    ),
                )
            )

        return (

            ResearchWorkspaceReadinessCheck(

                name="session_workspace",

                status=(

                    ResearchWorkspaceReadinessCheckStatus
                    .PASS
                ),

                critical=True,

                message=(
                    "Research session workspace "
                    "is available."
                ),

                capability=(

                    ResearchWorkspaceCapability
                    .SESSIONS
                ),
            )
        )

    def _check_capability_discovery(self):

        try:

            capabilities = (

                self.capability_registry
                .list_capabilities()
            )

        except Exception:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="capability_discovery",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .FAIL
                    ),

                    critical=True,

                    message=(
                        "Workspace capability discovery "
                        "could not be accessed."
                    ),
                )
            )

        if not capabilities:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="capability_discovery",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .FAIL
                    ),

                    critical=True,

                    message=(
                        "Workspace capability discovery "
                        "returned no capabilities."
                    ),
                )
            )

        return (

            ResearchWorkspaceReadinessCheck(

                name="capability_discovery",

                status=(

                    ResearchWorkspaceReadinessCheckStatus
                    .PASS
                ),

                critical=True,

                message=(
                    "Workspace capability discovery "
                    "is available."
                ),
            )
        )

    def _check_workspace_integrity(self):

        try:

            report = (

                self.integrity_auditor
                .audit()
            )

        except Exception:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="workspace_integrity",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .WARNING
                    ),

                    critical=False,

                    message=(
                        "Could not complete workspace "
                        "integrity assessment."
                    ),

                    capability=(

                        ResearchWorkspaceCapability
                        .INTEGRITY
                    ),
                )
            )

        if not report.findings:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="workspace_integrity",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .PASS
                    ),

                    critical=False,

                    message=(
                        "Workspace integrity audit "
                        "found no issues."
                    ),

                    capability=(

                        ResearchWorkspaceCapability
                        .INTEGRITY
                    ),
                )
            )

        finding_count = len(
            report.findings
        )

        if report.has_critical_findings:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="workspace_integrity",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .FAIL
                    ),

                    critical=False,

                    message=(

                        "Workspace integrity audit "
                        f"detected {finding_count} "
                        "issue(s), including critical "
                        "findings."
                    ),

                    capability=(

                        ResearchWorkspaceCapability
                        .INTEGRITY
                    ),
                )
            )

        return (

            ResearchWorkspaceReadinessCheck(

                name="workspace_integrity",

                status=(

                    ResearchWorkspaceReadinessCheckStatus
                    .WARNING
                ),

                critical=False,

                message=(

                    "Workspace integrity audit "
                    f"detected {finding_count} "
                    "issue(s)."
                ),

                capability=(

                    ResearchWorkspaceCapability
                    .INTEGRITY
                ),
            )
        )

    def _check_change_feed(self):

        try:

            self.change_feed.latest_sequence

        except Exception:

            return (

                ResearchWorkspaceReadinessCheck(

                    name="change_feed",

                    status=(

                        ResearchWorkspaceReadinessCheckStatus
                        .WARNING
                    ),

                    critical=False,

                    message=(
                        "Reactive workspace "
                        "synchronization is "
                        "currently unavailable."
                    ),

                    capability=(

                        ResearchWorkspaceCapability
                        .CHANGE_FEED
                    ),
                )
            )

        return (

            ResearchWorkspaceReadinessCheck(

                name="change_feed",

                status=(

                    ResearchWorkspaceReadinessCheckStatus
                    .PASS
                ),

                critical=False,

                message=(
                    "Reactive workspace "
                    "synchronization is available."
                ),

                capability=(

                    ResearchWorkspaceCapability
                    .CHANGE_FEED
                ),
            )
        )

    def _aggregate(

        self,

        checks,

    ):

        blocking_reasons = [

            check.message

            for check

            in checks

            if (

                check.critical

                and check.status

                == ResearchWorkspaceReadinessCheckStatus
                .FAIL
            )
        ]

        warnings = [

            check.message

            for check

            in checks

            if (

                check.status

                != ResearchWorkspaceReadinessCheckStatus
                .PASS

                and check.message

                not in blocking_reasons
            )
        ]

        if blocking_reasons:

            status = (

                ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            )

            ready = False

            blocking = True

        elif warnings:

            status = (

                ResearchWorkspaceReadinessStatus
                .DEGRADED
            )

            ready = True

            blocking = False

        else:

            status = (

                ResearchWorkspaceReadinessStatus
                .READY
            )

            ready = True

            blocking = False

        return (

            ResearchWorkspaceReadinessAssessment(

                status=status,

                ready=ready,

                blocking=blocking,

                checks=checks,

                warnings=warnings,

                blocking_reasons=(
                    blocking_reasons
                ),
            )
        )
