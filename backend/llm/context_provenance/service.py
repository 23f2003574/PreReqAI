import re

from ..context_version import LLMContextVersionService, UnknownContextVersionError
from ..project_context import LLMProjectContextService, UnknownProjectContextError
from .models import VALID_SOURCE_TYPES, LLMContextProvenance

# Same secret-detection convention used by backend.transformation_audit,
# backend.api_recommendation_export, backend.llm.tool_execution,
# backend.llm.tool_results, backend.llm.tool_audit, and
# backend.llm.project_context.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


class UnknownProvenanceError(KeyError):
    """Raised when get() finds no provenance record for a context_id."""


class InvalidSourceError(ValueError):
    """Raised when a provenance's source fields fail validation, or cannot
    be verified against the artifact/version it claims to reference."""


class SecretProvenanceError(ValueError):
    """Raised when a provenance's excerpt or source_id looks like a secret."""


class LLMContextProvenanceService:
    """Records an append-only trail of which project artifact each stored
    context came from.

    Reuses Commit #1's LLMProjectContextService to confirm context_id (and,
    for source_type="project_context", source_id) names a real context, and
    Commit #2's LLMContextVersionService -- when supplied -- to confirm a
    source_type="context_version" reference names a version that was
    actually recorded. An optional research-artifact store (anything
    exposing get(artifact_id), such as backend.session's
    ResearchArtifactStore) verifies source_type="research_artifact"
    references the same way. source_type="external" cannot be verified
    against anything the repository holds, and is accepted on trust.

    Holds its own append-only trail in memory, the same shape
    backend.llm.audit.LLMRequestAuditService and
    backend.llm.tool_audit.LLMToolAuditService already use for a lifecycle
    trail, rather than a second persistence framework: no record is ever
    edited or removed once attach() has written it.
    """

    def __init__(
        self,
        context_service: LLMProjectContextService,
        version_service: LLMContextVersionService = None,
        artifact_store=None,
    ):
        self.context_service = context_service
        self.version_service = version_service
        self.artifact_store = artifact_store
        self._records_by_context: dict[str, list] = {}

    def attach(self, context_id: str, source: dict) -> LLMContextProvenance:
        """Record a new provenance entry for context_id.

        Raises UnknownProjectContextError (Commit #1) if context_id is not
        a real, currently stored context; InvalidSourceError or
        SecretProvenanceError if the source itself does not pass
        validate().
        """
        self.context_service.get(context_id)

        provenance = LLMContextProvenance(
            context_id=context_id,
            source_type=source.get("source_type"),
            source_id=source.get("source_id"),
            excerpt=source.get("excerpt"),
            source_version=source.get("source_version"),
        )
        self.validate(provenance)

        self._records_by_context.setdefault(context_id, []).append(provenance)
        return provenance

    def get(self, context_id: str) -> LLMContextProvenance:
        """The most recently attached provenance record for context_id."""
        records = self._records_by_context.get(context_id)
        if not records:
            raise UnknownProvenanceError(context_id)
        return records[-1]

    def sources(self, context_id: str) -> list:
        """Every provenance record attached to context_id, oldest first."""
        return list(self._records_by_context.get(context_id, []))

    def validate(self, provenance: LLMContextProvenance) -> bool:
        """Whether a provenance record is fit to be recorded. Raises if not."""
        if not isinstance(provenance, LLMContextProvenance):
            raise InvalidSourceError(f"not an LLMContextProvenance: {provenance!r}")

        for field_name in ("context_id", "source_id", "excerpt"):
            value = getattr(provenance, field_name)
            if not value or not isinstance(value, str):
                raise InvalidSourceError(f"{field_name} is required")

        if provenance.source_type not in VALID_SOURCE_TYPES:
            raise InvalidSourceError(
                f"source_type {provenance.source_type!r} is not one of "
                f"{sorted(VALID_SOURCE_TYPES)}"
            )

        version = provenance.source_version
        if version is not None and (
            isinstance(version, bool) or not isinstance(version, int) or version < 1
        ):
            raise InvalidSourceError("source_version must be a positive integer when present")

        if _looks_secret(provenance.excerpt) or _looks_secret(provenance.source_id):
            raise SecretProvenanceError(
                "provenance excerpt/source_id appears to contain a secret or credential"
            )

        self._verify_source(provenance)
        return True

    def _verify_source(self, provenance: LLMContextProvenance) -> None:
        """Confirm the claimed source exists, wherever the repository can check."""
        if provenance.source_type == "project_context":
            try:
                self.context_service.get(provenance.source_id)
            except UnknownProjectContextError as error:
                raise InvalidSourceError(
                    f"source_id {provenance.source_id!r} is not a known project context"
                ) from error
            return

        if provenance.source_type == "context_version":
            if provenance.source_version is None:
                raise InvalidSourceError(
                    "context_version provenance requires a source_version"
                )
            if self.version_service is not None:
                try:
                    self.version_service.get(provenance.source_id, provenance.source_version)
                except UnknownContextVersionError as error:
                    raise InvalidSourceError(
                        f"no version {provenance.source_version} is recorded for context "
                        f"{provenance.source_id!r}"
                    ) from error
            return

        if provenance.source_type == "research_artifact":
            if self.artifact_store is not None:
                artifact = self.artifact_store.get(provenance.source_id)
                if artifact is None:
                    raise InvalidSourceError(
                        f"source_id {provenance.source_id!r} is not a known research artifact"
                    )
                if (
                    provenance.source_version is not None
                    and artifact.version != provenance.source_version
                ):
                    raise InvalidSourceError(
                        f"research artifact {provenance.source_id!r} is at version "
                        f"{artifact.version}, not {provenance.source_version}"
                    )
            return

        # source_type == "external": nothing in the repository to verify this against
