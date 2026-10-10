from contextlib import (
    contextmanager,
)

from .research_workspace_consumer_projection_budget_decision import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
)

from .research_workspace_consumer_projection_diagnostic_failure import (
    ResearchWorkspaceConsumerProjectionDiagnosticFailure,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_consumer_projection_input_diagnostic import (
    ResearchWorkspaceConsumerProjectionInputDiagnostic,
)

from .research_workspace_consumer_projection_stage_diagnostic import (
    ResearchWorkspaceConsumerProjectionStageDiagnostic,
)


class _StageHandle:

    def __init__(self):

        self.degraded = False

        self.reason_code = None

    def mark_degraded(

        self,

        *,

        reason_code=None,

    ):

        self.degraded = True

        self.reason_code = reason_code


class ResearchWorkspaceConsumerProjectionDiagnosticsCollector:
    """
    Mutable, operation-scoped recorder of
    shared input resolution/reuse and
    projection stage execution. Produces
    one immutable diagnostic report when
    finalized.

    The report is only ever produced when
    the operation did not raise a fatal,
    unhandled exception — a stage that
    fails and is never caught propagates
    normally, and no report is returned
    for that call. A report therefore
    describes SUCCEEDED (every recorded
    stage succeeded) or DEGRADED (the
    operation continued despite at least
    one stage failing or being explicitly
    marked degraded).
    """

    def __init__(

        self,

        *,

        operation_name,

        clock,

    ):

        self._operation_name = (
            operation_name
        )

        self._clock = clock

        self._started_at = (
            clock.now()
        )

        self._finalized = False

        self._final_report = None

        self._inputs = {}

        self._input_order = []

        self._stages = []

        self._budget_admissions = []

    def _ensure_open(self):

        if self._finalized:

            raise RuntimeError(
                "Cannot record diagnostics "
                "after the collector has "
                "been finalized"
            )

    def record_input_resolution(

        self,

        *,

        name,

        duration_seconds,

        status,

        key=None,

        failure=None,

    ):

        self._ensure_open()

        entry_key = (
            name,

            key,
        )

        if entry_key not in self._inputs:

            self._inputs[
                entry_key
            ] = {

                "resolution_count": 0,

                "reuse_count": 0,

                "duration_seconds": 0.0,

                "status": status,

                "failure": failure,

                "freshness": None,
            }

            self._input_order.append(
                entry_key
            )

        entry = self._inputs[
            entry_key
        ]

        entry[
            "resolution_count"
        ] += 1

        entry[
            "duration_seconds"
        ] += duration_seconds

        entry[
            "status"
        ] = status

        entry[
            "failure"
        ] = failure

    def record_input_reuse(

        self,

        *,

        name,

        key=None,

    ):

        self._ensure_open()

        entry_key = (
            name,

            key,
        )

        if entry_key not in self._inputs:

            self._inputs[
                entry_key
            ] = {

                "resolution_count": 0,

                "reuse_count": 0,

                "duration_seconds": 0.0,

                "status": (

                    ResearchWorkspaceConsumerProjectionDiagnosticStatus
                    .SUCCEEDED
                ),

                "failure": None,

                "freshness": None,
            }

            self._input_order.append(
                entry_key
            )

        self._inputs[
            entry_key
        ][
            "reuse_count"
        ] += 1

    def record_input_freshness(

        self,

        *,

        name,

        freshness,

        key=None,

    ):

        self._ensure_open()

        entry_key = (
            name,

            key,
        )

        if entry_key not in self._inputs:

            self._inputs[
                entry_key
            ] = {

                "resolution_count": 0,

                "reuse_count": 0,

                "duration_seconds": 0.0,

                "status": (

                    ResearchWorkspaceConsumerProjectionDiagnosticStatus
                    .SUCCEEDED
                ),

                "failure": None,

                "freshness": None,
            }

            self._input_order.append(
                entry_key
            )

        self._inputs[
            entry_key
        ][
            "freshness"
        ] = freshness

    def record_budget_admission(

        self,

        admission,

    ):

        self._ensure_open()

        self._budget_admissions.append(
            admission
        )

    @contextmanager
    def stage(

        self,

        *,

        name,

        kind,

    ):

        self._ensure_open()

        handle = _StageHandle()

        started_at = (
            self._clock.now()
        )

        try:

            yield handle

        except Exception as error:

            duration_ms = (

                (

                    self._clock.now()

                    - started_at
                )

                * 1000
            )

            self._stages.append(

                ResearchWorkspaceConsumerProjectionStageDiagnostic(

                    name=name,

                    kind=kind,

                    status=(

                        ResearchWorkspaceConsumerProjectionDiagnosticStatus
                        .FAILED
                    ),

                    duration_ms=(
                        duration_ms
                    ),

                    reason_code=None,

                    failure=(

                        ResearchWorkspaceConsumerProjectionDiagnosticFailure(

                            error_type=(

                                type(
                                    error
                                ).__name__
                            ),
                        )
                    ),
                )
            )

            raise

        else:

            duration_ms = (

                (

                    self._clock.now()

                    - started_at
                )

                * 1000
            )

            status = (

                ResearchWorkspaceConsumerProjectionDiagnosticStatus
                .DEGRADED

                if handle.degraded

                else (

                    ResearchWorkspaceConsumerProjectionDiagnosticStatus
                    .SUCCEEDED
                )
            )

            self._stages.append(

                ResearchWorkspaceConsumerProjectionStageDiagnostic(

                    name=name,

                    kind=kind,

                    status=status,

                    duration_ms=(
                        duration_ms
                    ),

                    reason_code=(
                        handle.reason_code
                    ),

                    failure=None,
                )
            )

    def finalize(self):

        if self._finalized:

            return self._final_report

        self._finalized = True

        total_duration_ms = (

            (

                self._clock.now()

                - self._started_at
            )

            * 1000
        )

        inputs = []

        for entry_key in (
            self._input_order
        ):

            name, key = entry_key

            data = self._inputs[
                entry_key
            ]

            inputs.append(

                ResearchWorkspaceConsumerProjectionInputDiagnostic(

                    name=name,

                    key=key,

                    resolution_count=(
                        data[
                            "resolution_count"
                        ]
                    ),

                    reuse_count=(
                        data[
                            "reuse_count"
                        ]
                    ),

                    duration_ms=(

                        data[
                            "duration_seconds"
                        ]

                        * 1000
                    ),

                    status=(
                        data[
                            "status"
                        ]
                    ),

                    failure=(
                        data[
                            "failure"
                        ]
                    ),

                    freshness=(
                        data.get(
                            "freshness"
                        )
                    ),
                )
            )

        has_unsuccessful_stage = any(

            stage.status

            != ResearchWorkspaceConsumerProjectionDiagnosticStatus
            .SUCCEEDED

            for stage

            in self._stages
        )

        has_budget_skip = any(

            admission.decision

            == ResearchWorkspaceConsumerProjectionBudgetDecision
            .SKIP

            for admission

            in self._budget_admissions
        )

        overall_status = (

            ResearchWorkspaceConsumerProjectionDiagnosticStatus
            .DEGRADED

            if (

                has_unsuccessful_stage

                or has_budget_skip
            )

            else (

                ResearchWorkspaceConsumerProjectionDiagnosticStatus
                .SUCCEEDED
            )
        )

        self._final_report = (

            ResearchWorkspaceConsumerProjectionDiagnosticReport(

                operation_name=(
                    self._operation_name
                ),

                status=overall_status,

                duration_ms=(
                    total_duration_ms
                ),

                inputs=inputs,

                stages=list(
                    self._stages
                ),

                budget_decisions=list(
                    self._budget_admissions
                ),
            )
        )

        return self._final_report
