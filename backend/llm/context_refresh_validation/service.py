from ..context_freshness import STALE, UNKNOWN, LLMContextFreshnessService
from ..context_provenance import UnknownProvenanceError
from ..context_refresh_execution import PARTIAL, LLMContextRefreshExecutionService
from ..context_version import UnknownContextVersionError
from ..project_context import InvalidContentError, SecretContentError, UnknownProjectContextError
from .models import (
    INCOMPLETE_REFRESH,
    MALFORMED_CONTENT,
    MISSING_PROVENANCE,
    SOURCE_VERSION_MISMATCH,
    STALE_REFRESH,
    UNVERIFIABLE_FRESHNESS,
    LLMContextRefreshValidation,
)

_MISSING = object()


class LLMContextRefreshValidationService:
    """Re-checks a completed Commit #11 execution's result against its own contracts.

    Reuses rather than re-implements: Commit #1's LLMProjectContextService
    for the current stored content (and its own private content validator,
    called directly since there is no second copy of that rule anywhere in
    this service), Commit #2's LLMContextVersionService and a
    backend.session artifact store (both reached the way Commit #9/#10/#11
    already reach them, off provenance_service) for what the pinned
    source/version actually holds, Commit #6's LLMContextProvenanceService
    for what the refresh claims to have come from, and Commit #9's
    LLMContextFreshnessService for whether the source has already moved on
    again. Nothing here writes anywhere: validate()/findings()/blocking()
    only read, and no automatic activation or rollback happens in this
    commit.
    """

    def __init__(
        self,
        execution_service: LLMContextRefreshExecutionService,
        freshness_service: LLMContextFreshnessService,
    ):
        self.execution_service = execution_service
        self.context_service = execution_service.context_service
        self.provenance_service = execution_service.provenance_service
        self.freshness_service = freshness_service
        self._validations: dict[str, list] = {}

    def validate(self, execution_id: str) -> LLMContextRefreshValidation:
        execution = self.execution_service.status(execution_id)

        findings = []
        if execution.status == PARTIAL:
            findings.append(
                self._finding(
                    None,
                    INCOMPLETE_REFRESH,
                    f"execution {execution_id!r} only partially applied its approved "
                    "refresh actions",
                    blocking=True,
                )
            )

        for context_id in execution.refreshed_context_ids:
            findings.extend(self._check_context(context_id))

        validation = LLMContextRefreshValidation(
            execution_id=execution_id,
            valid=not any(finding["blocking"] for finding in findings),
            findings=tuple(findings),
        )
        self._validations.setdefault(execution_id, []).append(validation)
        return validation

    def findings(self, execution_id: str) -> list:
        """Every finding from a fresh validation of execution_id, run now."""
        return list(self.validate(execution_id).findings)

    def blocking(self, execution_id: str) -> list:
        """The subset of findings() that would prevent activation."""
        return [finding for finding in self.findings(execution_id) if finding["blocking"]]

    # -- internals ------------------------------------------------------

    def _check_context(self, context_id: str) -> list:
        findings = []

        try:
            context = self.context_service.get(context_id)
        except UnknownProjectContextError:
            return [
                self._finding(
                    context_id,
                    MALFORMED_CONTENT,
                    f"context {context_id!r} no longer exists",
                    blocking=True,
                )
            ]

        try:
            self.context_service._validate_content(context.content)
        except (InvalidContentError, SecretContentError) as error:
            findings.append(self._finding(context_id, MALFORMED_CONTENT, str(error), blocking=True))

        try:
            provenance = self.provenance_service.get(context_id)
        except UnknownProvenanceError:
            findings.append(
                self._finding(
                    context_id,
                    MISSING_PROVENANCE,
                    f"context {context_id!r} carries no provenance after being refreshed",
                    blocking=True,
                )
            )
            provenance = None

        if provenance is not None:
            pinned_content = self._pinned_source_content(provenance)
            if pinned_content is not _MISSING and pinned_content != context.content:
                findings.append(
                    self._finding(
                        context_id,
                        SOURCE_VERSION_MISMATCH,
                        f"stored content for {context_id!r} does not match its recorded "
                        "source/version",
                        blocking=True,
                    )
                )

        freshness = self.freshness_service.check(context_id)
        if freshness.status == STALE:
            findings.append(
                self._finding(
                    context_id,
                    STALE_REFRESH,
                    f"context {context_id!r} is already stale again: {freshness.reason}",
                    blocking=True,
                )
            )
        elif freshness.status == UNKNOWN:
            findings.append(
                self._finding(
                    context_id,
                    UNVERIFIABLE_FRESHNESS,
                    f"freshness of {context_id!r} cannot be verified: {freshness.reason}",
                    blocking=False,
                )
            )

        return findings

    def _pinned_source_content(self, provenance):
        """What provenance's exact recorded source/version currently holds.

        Deliberately compares against the *exact pinned* version/artifact a
        refresh claims to have used -- not the latest one, which is what
        Commit #9's freshness check (staleness) and Commit #11's own resolve
        (what to refresh *to*) already look at. _MISSING means nothing
        pinned remains to compare against.
        """
        if provenance.source_type == "context_version":
            version_service = self.provenance_service.version_service
            if version_service is None or provenance.source_version is None:
                return _MISSING
            try:
                return version_service.get(provenance.source_id, provenance.source_version).content
            except UnknownContextVersionError:
                return _MISSING

        if provenance.source_type == "research_artifact":
            artifact_store = self.provenance_service.artifact_store
            if artifact_store is None:
                return _MISSING
            artifact = artifact_store.get(provenance.source_id)
            if artifact is None:
                return _MISSING
            if provenance.source_version is not None and artifact.version != provenance.source_version:
                return _MISSING
            return artifact.content

        if provenance.source_type == "project_context":
            try:
                return self.context_service.get(provenance.source_id).content
            except UnknownProjectContextError:
                return _MISSING

        return _MISSING  # "external": nothing pinned in the repository to compare against

    @staticmethod
    def _finding(context_id, code: str, message: str, blocking: bool) -> dict:
        return {"context_id": context_id, "code": code, "message": message, "blocking": blocking}
