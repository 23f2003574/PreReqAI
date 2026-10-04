from backend.engine import (
    InteractiveResearchEngine,
)

from backend.api.workflow_result import (
    cancelled_body,
    failure_body,
    success_body,
)

from backend.pipeline.research_paper_pipeline import (
    PipelineCancelled,
)

from backend.pipeline import (
    InteractiveLearningPipeline,
    ResearchNavigationPipeline,
    ResearchPaperPipeline,
)


def _diagnostics(outcome: dict, stage_timings: dict, report) -> dict:
    """What the run already knows, for development: final status, completed
    stages with their durations, where a failed run stopped, warnings and the
    report's own statistics. Counts and timings only -- no inputs or paths."""
    completed = list(stage_timings)
    return {
        "status": outcome["status"], "stage": outcome["stage"], "completed_stages": completed,
        "failed_after": completed[-1] if outcome["status"] == "failure" and completed else None,
        "stopped_after": completed[-1] if outcome["status"] == "cancelled" and completed else None,
        "stage_seconds": dict(stage_timings), "total_seconds": round(sum(stage_timings.values()), 6),
        "slowest_stage": max(stage_timings, key=stage_timings.get) if stage_timings else None,
        "warnings": list(outcome["warnings"]), "statistics": dict(report["statistics"]) if report else None,
    }


class PreReqAIPlatform:
    """
    High-level platform entry point
    coordinating every educational
    subsystem: analysis (PDF to
    knowledge graph and prerequisites),
    navigation, interaction, and the
    learning workflow/tutoring pipeline.
    """

    def __init__(self):

        self.analysis = (
            ResearchPaperPipeline()
        )

        self.navigation = (
            ResearchNavigationPipeline()
        )

        self.interaction = (
            InteractiveResearchEngine()
        )

        self.learning = (
            InteractiveLearningPipeline()
        )

    def analyze(self, file_path: str, diagnostics: bool = False, should_cancel=None) -> dict:
        """Run the analysis pipeline on a paper PDF and open a learning
        session for it. Returns the public workflow result envelope
        (backend.api.workflow_result): a success body carrying session_id and
        report, or a failure body for the analysis stage. This is the one
        place the analysis workflow is turned into a public result; the HTTP
        endpoint and the CLI both call it. With diagnostics=True the result
        also carries a "diagnostics" summary (see _diagnostics); otherwise the
        result is exactly as before. should_cancel is an optional callable polled
        between stages; when it returns True the run stops before the next
        stage and the result has status "cancelled" (no session is created)."""
        from backend.session import session_manager

        try:
            result = self.analysis.run(file_path, should_cancel=should_cancel)
        except PipelineCancelled as exc:
            outcome = cancelled_body(
                "analysis", "Analysis was cancelled before it finished.",
                hint="Run the analysis again to start over; nothing was kept.",
            )
            if diagnostics:
                outcome["diagnostics"] = _diagnostics(outcome, getattr(exc, "stage_timings", {}), None)
            return outcome
        except Exception as exc:
            outcome = failure_body(
                "analysis", f"Failed to process the uploaded paper: {exc}", error=exc,
                hint="Upload a text-based PDF research paper.",
            )
            if diagnostics:
                outcome["diagnostics"] = _diagnostics(outcome, getattr(exc, "stage_timings", {}), None)
            return outcome
        session = session_manager.create(
            paper_title=result.report["paper"]["title"], report=result.report, paper=result.paper,
        )
        outcome = success_body(
            "Prerequisite Explorer", "session_created", session_id=session.session_id, report=result.report,
            timings=result.timings,
        )
        if diagnostics:
            outcome["diagnostics"] = _diagnostics(outcome, result.timings, result.report)
        return outcome


# The one platform instance the HTTP application (backend.main) and its routers
# share, so the user-facing endpoints run the platform's own pipelines.
platform = PreReqAIPlatform()
