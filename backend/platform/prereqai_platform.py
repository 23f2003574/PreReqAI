import difflib
import os
from copy import deepcopy
from time import perf_counter

import pymupdf
import requests
import urllib3

from backend.api.workflow_result import (
    REQUIRED_REPORT_KEYS,
    cancelled_body,
    failure_body,
    limit_exceeded_body,
    success_body,
    terminal_violations,
    timeout_body,
)
from backend.engine import (
    InteractiveResearchEngine,
)
from backend.llm.config import (
    InvalidConfigurationError,
)
from backend.pipeline import (
    InteractiveLearningPipeline,
    ResearchNavigationPipeline,
    ResearchPaperPipeline,
)
from backend.pipeline.research_paper_pipeline import (
    PIPELINE_STAGES,
    PipelineCancelled,
)


def _diagnostics(outcome: dict, stage_timings: dict, report, failed_stage=None) -> dict:
    """What the run already knows, for development: final status, completed
    stages with their durations, where a failed run stopped, warnings and the
    report's own statistics. Counts and timings only -- no inputs or paths.
    completed_stages holds only stages that finished: the stage that failed
    (failed_stage) and every stage after it are never listed."""
    completed = list(stage_timings)
    return {
        "status": outcome["status"], "stage": outcome["stage"], "completed_stages": completed,
        "failed_after": completed[-1] if outcome["status"] == "failure" and completed else None,
        "failed_stage": failed_stage if outcome["status"] == "failure" else None,
        "stopped_after": completed[-1] if outcome["status"] in ("cancelled", "limit_exceeded", "timeout") and completed else None,
        "stage_seconds": dict(stage_timings), "total_seconds": round(sum(stage_timings.values()), 6),
        "slowest_stage": max(stage_timings, key=stage_timings.get) if stage_timings else None,
        "warnings": list(outcome["warnings"]), "statistics": dict(report["statistics"]) if report else None,
    }


# PyMuPDF reports a missing file with its own FileNotFoundError (a RuntimeError).
_MISSING_FILE_ERRORS = (FileNotFoundError, getattr(pymupdf, "FileNotFoundError", FileNotFoundError))


def _caused_by(exc: BaseException, types) -> bool:
    """Whether `exc` is, or was caused by, an exception of `types`. A stage may
    wrap an error in its own ("raise ... from", or as its first argument)."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, types):
            return True
        wrapped = exc.args[0] if exc.args and isinstance(exc.args[0], BaseException) else None
        exc = exc.__cause__ or wrapped
    return False


def _is_timeout(exc: BaseException) -> bool:
    """Whether `exc` is, or was caused by, an operation running out of time.
    requests reports a read timeout while downloading the body as a plain
    ConnectionError wrapping urllib3's ReadTimeoutError, and a stage may wrap a
    timeout in its own error ("raise ... from"); both are still timeouts."""
    return _caused_by(exc, (requests.exceptions.Timeout, TimeoutError, urllib3.exceptions.TimeoutError))


# Stages that read the user's input: a failure there is about the paper or its path, which the
# generic hints already explain. A failure in any later stage is an internal one.
_INPUT_STAGES = ("source_detector", "source_resolver", "ingestion")


def _stopped_outcome(exc: Exception, exceeded_limits=None) -> dict:
    """The terminal outcome of an analysis run that raised `exc`: a cancellation
    caused by an exceeded time limit (exceeded_limits) is limit_exceeded, any
    other cancellation is cancelled, a timed-out operation (in practice the
    arXiv/Crossref download) is timeout, and anything else is a failure."""
    if isinstance(exc, PipelineCancelled):
        if exceeded_limits is not None:
            return limit_exceeded_body(
                "analysis", f"The analysis exceeded its time limit of {exceeded_limits.max_seconds} seconds.",
                hint="Raise the time limit or analyse a smaller paper; nothing was kept.",
            )
        return cancelled_body(
            "analysis", "Analysis was cancelled before it finished.",
            hint="Run the analysis again to start over; nothing was kept.",
        )
    if _is_timeout(exc):
        return timeout_body(
            "analysis", f"The analysis timed out: {exc}", error=exc,
            hint="Check the network connection and try again; nothing was kept.",
        )
    if _caused_by(exc, _MISSING_FILE_ERRORS):  # a mistyped path is not a bad paper
        return failure_body(
            "analysis", f"Failed to process the uploaded paper: {exc}", error=exc,
            hint="Check the paper path: it must name an existing PDF file (relative paths start from the current directory).",
        )
    if isinstance(exc, ValueError) and str(exc).startswith("Unsupported research source"):  # e.g. a .txt file or a directory
        return failure_body(
            "analysis", f"Failed to process the uploaded paper: {exc}", error=exc,
            hint="The paper must be a PDF file (a path ending in .pdf), not another file type or a directory.",
        )
    if "encrypted" in str(exc).casefold():  # a password-protected PDF: say so instead of a bare library message
        return failure_body(
            "analysis", "The paper is a password-protected PDF and cannot be read.", error=exc,
            hint="Remove the password (for example, print the PDF to a new file) and upload that copy.",
        )
    return failure_body(
        "analysis", f"Failed to process the uploaded paper: {exc}", error=exc,
        hint="Upload a text-based PDF research paper.",
    )


def _concept_label(name: str) -> str:
    """A learner-typed concept name with stray and repeated whitespace collapsed ("  linear   algebra " -> "linear algebra")."""
    return " ".join(name.split())


def _split_names(values) -> list:
    """`known`/`studied` values with comma-separated lists split, so every surface (CLI, upload form, Python)
    accepts "Probability,Calculus"; concept names never contain commas."""
    return [name for value in (values or ()) for name in str(value).split(",")]


def _concept_key(name: str) -> str:
    return _concept_label(name).casefold()


def _did_you_mean(name, concept_names):
    """' (did you mean 'Probability'?)' for a near-miss spelling of a prerequisite, else nothing."""
    by_folded = {concept.casefold(): concept for concept in concept_names}
    folded = " ".join(str(name).split()).casefold()
    if folded in by_folded:  # spelled right: it is simply not in the plan (e.g. already known)
        return ""
    close = difflib.get_close_matches(folded, by_folded, n=1, cutoff=0.7)
    return f" (did you mean {by_folded[close[0]]!r}?)" if close else ""


# Why a prerequisite the learner marked known counts as satisfied.
KNOWN_REASON = "Already known (reported by the learner)"

# The report sections that change when the learner studies a concept.
PROGRESS_REPORT_KEYS = ("study_progress", "readiness", "study_actions", "prerequisite_tree")


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

    def analyze(self, file_path: str, diagnostics: bool = False, should_cancel=None, limits=None, known=(), studied=()) -> dict:
        """The workflow's public entry point: _analyze() plus the final-state guard. A result that is
        not a valid terminal state (see workflow_result.terminal_violations) is never returned as it
        is -- it becomes a failure at stage "finalization"."""
        outcome = self._analyze(file_path, diagnostics, should_cancel, limits, _split_names(known), _split_names(studied))
        problems = terminal_violations(outcome)
        if problems:
            outcome = failure_body(
                "finalization", "The analysis did not reach a valid final state: " + "; ".join(problems),
                error=RuntimeError("; ".join(problems)), hint="This is a bug in the workflow; report it.",
            )
            if diagnostics:
                outcome["diagnostics"] = _diagnostics(outcome, {}, None)
        return outcome

    def _analyze(self, file_path: str, diagnostics: bool, should_cancel, limits, known=(), studied=()) -> dict:
        """Run the analysis pipeline on a paper PDF and open a learning
        session for it. Returns the public workflow result envelope
        (backend.api.workflow_result): a success body carrying session_id and
        report, or a failure body for the analysis stage. This is the one
        place the analysis workflow is turned into a public result; the HTTP
        endpoint and the CLI both call it. With diagnostics=True the result
        also carries a "diagnostics" summary (see _diagnostics); otherwise the
        result is exactly as before. should_cancel is an optional callable polled
        between stages; when it returns True the run stops before the next
        stage and the result has status "cancelled" (no session is created).
        limits is an optional AnalysisLimits: an invalid one is a failure at
        stage "configuration"; a run that hits one ends with status
        "limit_exceeded" (distinct from failure and cancellation, and with no
        session). The default is no limits."""
        from backend.session import session_manager

        def with_diagnostics(outcome, timings=None, report=None, failed_stage=None):
            if diagnostics:
                outcome["diagnostics"] = _diagnostics(outcome, timings or {}, report, failed_stage)
            return outcome

        exceeded = []
        if limits is not None:
            try:
                limits.validate()
            except InvalidConfigurationError as exc:
                return with_diagnostics(failure_body(
                    "configuration", f"Invalid analysis limits: {exc}", error=exc,
                    hint="Limits must be positive numbers; leave them unset for no limit.",
                ))
            if limits.max_file_bytes is not None and os.path.isfile(file_path) and os.path.getsize(file_path) > limits.max_file_bytes:
                return with_diagnostics(limit_exceeded_body(
                    "analysis", f"The paper is larger than the limit of {limits.max_file_bytes} bytes.",
                    hint="Raise the file size limit or analyse a smaller paper.",
                ))
            if limits.max_seconds is not None:
                deadline = perf_counter() + limits.max_seconds
                user_cancel = should_cancel

                def should_cancel():
                    if user_cancel is not None and user_cancel():
                        return True
                    if perf_counter() > deadline:
                        exceeded.append("max_seconds")
                        return True
                    return False

        try:
            result = self.analysis.run(file_path, should_cancel=should_cancel)
        except Exception as exc:
            # Every way a run can stop becomes one terminal outcome here, with what finished before it.
            outcome = _stopped_outcome(exc, limits if exceeded else None)
            failed_stage = getattr(exc, "failed_stage", None) if outcome["status"] == "failure" else None
            if failed_stage not in (None, *_INPUT_STAGES):  # name the stage so the failure can be located without --diagnose
                outcome["detail"] += f" (in analysis stage '{failed_stage}')"
                outcome["hint"] = (f"The '{failed_stage}' stage failed on this paper, which usually means a bug rather than a "
                                   f"problem with the file; re-run with --diagnose and report it.")
            return with_diagnostics(outcome, getattr(exc, "stage_timings", {}), failed_stage=failed_stage)
        incomplete = [stage for stage in PIPELINE_STAGES if stage not in result.timings]
        incomplete += [f"report.{key}" for key in REQUIRED_REPORT_KEYS if key not in result.report]
        if incomplete:  # a partial result must never open a session or be reported as a success
            return with_diagnostics(failure_body(
                "finalization", f"The analysis did not complete: {', '.join(incomplete)}",
                error=RuntimeError("incomplete analysis"), hint="This is a bug in the workflow; report it.",
            ), result.timings)
        concept_names = [item["concept"] for item in result.report.get("missing_prerequisites", [])]
        unmatched = self._personalize(result, known) if known else []
        not_studied = self._apply_studied(result, studied) if studied else []
        # The session keeps its own copy of the report: the caller owns the one returned below, and
        # changing it must not change what later session requests (tutoring, lookups) read.
        session = session_manager.create(
            paper_title=result.report["paper"]["title"], report=deepcopy(result.report), paper=result.paper,
        )
        unsaved = [] if session_manager.last_save_ok else [
            "The session could not be saved to PREREQAI_SESSION_DIR, so it will not survive a server restart; "
            "check that the directory exists and is writable."
        ]
        no_concepts = []
        if not result.report.get("concepts"):
            has_text = any((getattr(page, "text", "") or "").strip() for page in (result.paper.pages or []))
            no_concepts = [
                "No concepts were detected in this paper, so the study plan is empty and 'Ready to Read' means nothing."
                + ("" if has_text else " The PDF has no extractable text (a scanned or image-only paper?); run OCR on it first.")
            ]
        outcome = success_body(
            "Prerequisite Explorer", "session_created", session_id=session.session_id, report=result.report,
            timings=result.timings,
            warnings=unsaved + no_concepts + [f"--known {name!r} is not in this paper's study plan and was ignored{_did_you_mean(name, concept_names)}" for name in unmatched]
            + [f"--studied {name!r} is not in this paper's study plan and was ignored{_did_you_mean(name, concept_names)}" for name in not_studied],
        )
        return with_diagnostics(outcome, result.timings, result.report)

    def mark_concept_studied(self, session_id: str, concept: str) -> dict | None:
        """Record that the learner finished studying `concept` in an analysed session and return the
        refreshed study progress and readiness. None: unknown session; ValueError: concept not in its plan.
        The concept name is matched ignoring case and surrounding spaces."""
        return self._set_concept_studied(session_id, concept, True)

    def unmark_concept_studied(self, session_id: str, concept: str) -> dict | None:
        """Undo a mistaken `mark_concept_studied`; same return values and errors."""
        return self._set_concept_studied(session_id, concept, False)

    def _set_concept_studied(self, session_id: str, concept: str, studied: bool) -> dict | None:
        from backend.progress import StudyProgressTracker
        from backend.session import session_manager

        session = session_manager.get(session_id)
        if session is None or session.paper is None:
            return None
        planned = {item.concept.casefold(): item.concept for item in session.paper.study_progress}
        if _concept_key(concept) not in planned:  # matched like --studied and question topics: case-insensitively
            raise ValueError(f"'{concept}' is not a concept in this session's study plan ({', '.join(planned.values()) or 'it is empty'})")
        concept = planned[_concept_key(concept)]
        tracker = StudyProgressTracker()
        (tracker.complete if studied else tracker.reset)(session.paper, concept)
        fresh = self._refresh_progress(session.paper, session.report)
        session_manager.save(session)
        return {"study_progress": fresh["study_progress"], "readiness": fresh["readiness"]}

    def _refresh_progress(self, paper, report) -> dict:
        """Re-evaluate readiness after the paper's study progress changed and copy the parts of a freshly
        generated report that depend on it into `report`; returns the fresh report. The one place that
        knows which report keys follow progress (analysis-time --studied and the session endpoints share it)."""
        self.analysis.readiness_engine.evaluate(paper)
        fresh = self.analysis.report_generator.generate(paper)
        for key in PROGRESS_REPORT_KEYS:
            report[key] = fresh[key]
        return fresh

    def mark_concept_known(self, session_id: str, concept: str) -> dict | None:
        """Drop a concept the learner already knows from an analysed session's study plan (like --known at
        analysis time) and return the rebuilt report. None: unknown session; ValueError: concept not in its plan."""
        from types import SimpleNamespace
        from backend.session import session_manager

        session = session_manager.get(session_id)
        if session is None or session.paper is None:
            return None
        planned = {item.concept.casefold(): item.concept for item in session.paper.learning_plan}
        if _concept_key(concept) not in planned and any(
            item.concept.casefold() == _concept_key(concept) and item.reason == KNOWN_REASON
            for item in session.paper.missing_prerequisites
        ):  # already marked known: repeating the request (a retry, a double click) changes nothing
            return session.report
        if _concept_key(concept) not in planned:
            raise ValueError(f"'{concept}' is not a concept in this session's study plan ({', '.join(planned.values()) or 'it is empty'})")
        target = SimpleNamespace(paper=session.paper, report=session.report)
        studied = [item.concept for item in session.paper.study_progress if item.completed]  # rebuilding the plan resets progress
        self._personalize(target, [planned[_concept_key(concept)]])
        self._apply_studied(target, studied)
        session_manager.save(session)
        return session.report

    def _personalize(self, result, known) -> list:
        """Drop concepts the learner says they already know from the study plan: the plan, time estimate,
        difficulty, actions, roadmap, progress and readiness are rebuilt without them, their resources are dropped and they
        are no longer reported as missing prerequisites."""
        wanted = {_concept_key(name) for name in known if name and name.strip()}
        paper, pipeline = result.paper, self.analysis
        planned = {step.concept.casefold() for step in paper.learning_plan}
        unmatched = sorted(_concept_label(name) for name in known if name and name.strip() and _concept_key(name) not in planned)
        paper.learning_plan = [step for step in paper.learning_plan if step.concept.casefold() not in wanted]
        for order, step in enumerate(paper.learning_plan, start=1):  # numbering restarts after the skipped steps
            step.order = order
        paper.learning_resources = [item for item in paper.learning_resources if item.concept.casefold() not in wanted]
        for prerequisite in paper.missing_prerequisites:  # a known concept is no longer missing
            if prerequisite.concept.casefold() in wanted and not prerequisite.satisfied:
                prerequisite.satisfied, prerequisite.reason = True, KNOWN_REASON
        pipeline.difficulty_engine.assess(paper)  # the paper is easier once known concepts are not missing
        pipeline.study_time_estimator.estimate(paper)
        pipeline.difficulty_explanation_engine.explain(paper)
        pipeline.study_action_generator.generate(paper)
        pipeline.study_roadmap_generator.generate(paper)
        pipeline.progress_tracker.initialize(paper)
        pipeline.readiness_engine.evaluate(paper)
        result.report.update(pipeline.report_generator.generate(paper))
        return unmatched

    def _apply_studied(self, result, studied) -> list:
        """Start the learner with these planned concepts already marked studied (progress and readiness
        follow); returns the names that are not in the study plan."""
        paper, pipeline = result.paper, self.analysis
        planned = {item.concept.casefold(): item.concept for item in paper.study_progress}
        names = [_concept_label(name) for name in studied if name and name.strip()]
        matched = [name for name in names if _concept_key(name) in planned]
        for name in matched:
            pipeline.progress_tracker.complete(paper, planned[_concept_key(name)])
        if matched:  # nothing completed: the report is already current, so do not rebuild it a second time
            self._refresh_progress(paper, result.report)
        return sorted(name for name in names if _concept_key(name) not in planned)


# The one platform instance the HTTP application (backend.main) and its routers
# share, so the user-facing endpoints run the platform's own pipelines.
platform = PreReqAIPlatform()
