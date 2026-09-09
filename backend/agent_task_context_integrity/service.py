from datetime import datetime

from backend.agent_policy_engine import DENY, LLMAgentPolicyEvaluator
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_context_packaging import AgentContextPackage
from backend.llm.context_freshness import STALE, UNKNOWN, LLMContextFreshnessService
from backend.llm.context_injection import CONTEXT_ROLE
from backend.llm.context_provenance import (
    VALID_SOURCE_TYPES,
    InvalidSourceError,
    LLMContextProvenance,
    LLMContextProvenanceService,
    SecretProvenanceError,
)
from backend.llm.project_context import UnknownProjectContextError
from backend.llm.secret_redaction import LLMSecretRedactionService

from .models import ContextIntegrityResult


class InvalidContextIntegrityError(ValueError):
    """Raised when validate() is given something other than an
    AgentContextPackage, or a missing/blank agent_id or scope_id."""


class LLMAgentTaskContextIntegrityService:
    """Checks one packaged AgentContextPackage for integrity before it is
    allowed to reach an agent request.

    Not a second security/validation engine: provenance shape/consistency
    is backend.llm.context_provenance.LLMContextProvenanceService.validate()
    itself when a live one is supplied (verified against its own real
    stores), or that same service's own field-level checks mirrored
    locally (same-shape, not a private cross-module import) when it
    isn't; staleness is backend.llm.context_freshness.
    LLMContextFreshnessService.check(), unchanged; authorization is the
    exact backend.agent_policy_engine/backend.agent_policy_resolution
    pair backend.agent_task_context_resolution.LLMAgentTaskContextResolver
    already reuses for the same "explicit deny wins, absence of policy
    restricts nothing" posture; secret-content screening is backend.llm.
    secret_redaction.LLMSecretRedactionService.detect(), the repository's
    one canonical secret-pattern scanner.

    provenance_service, freshness_service, and policy_service are all
    optional collaborators (the same duck-typed "used only if given"
    shape every resolver in this series already uses): omitting any of
    them narrows what can be checked (no live store to check provenance
    existence against, no freshness verdict, no authorization
    restriction) but never makes validate() error out -- an integrity
    check with less wiring is strictly more permissive, never less safe
    to call. LLMSecretRedactionService needs no store, so it is always
    used.

    validate() only ever reads package/agent_id/scope_id and whatever
    the optional collaborators read internally -- it never calls
    provenance_service.attach(), freshness_service's own store, or
    policy_service's own store to change anything, and never rewrites,
    reorders, or drops anything from package itself (Rule: "do not
    modify the package" / "detect ... rather than silently repairing
    it"). The same (package, agent_id, scope_id, and current store/
    policy/freshness state) always validates to the same
    ContextIntegrityResult.
    """

    def __init__(
        self,
        provenance_service: LLMContextProvenanceService = None,
        freshness_service: LLMContextFreshnessService = None,
        policy_service=None,
        secret_redaction: LLMSecretRedactionService = None,
    ):
        self._provenance_service = provenance_service
        self._freshness_service = freshness_service
        self._policy_resolver = LLMAgentPolicyResolver(policy_service) if policy_service is not None else None
        self._policy_evaluator = LLMAgentPolicyEvaluator() if policy_service is not None else None
        self._secret_redaction = secret_redaction or LLMSecretRedactionService()

    def validate(self, package: AgentContextPackage, agent_id: str, scope_id: str) -> ContextIntegrityResult:
        """Validate package for agent_id in scope_id.

        Raises:
            InvalidContextIntegrityError: If package is not an
                AgentContextPackage, or agent_id/scope_id is missing/blank
        """
        self._validate_args(package, agent_id, scope_id)

        errors = []
        warnings = []
        invalid_sources = []
        stale_sources = []
        provenance_issues = []

        self._check_ownership(package, agent_id, scope_id, errors)
        self._check_mandatory_task_data(package, errors)

        provenance_by_id = {}
        for record in package.provenance:
            record = self._normalize_provenance(record)
            provenance_by_id[record.context_id] = record  # last (most recent) wins

        for message in package.context:
            source_id = self._check_source_shape(message, errors, invalid_sources)
            if source_id is None:
                continue
            self._check_provenance(source_id, provenance_by_id, provenance_issues, errors)
            self._check_authorization(
                agent_id, scope_id, source_id, message.get("metadata") or {}, invalid_sources, errors
            )
            self._check_secret_content(source_id, message.get("content"), invalid_sources, errors)
            self._check_freshness(source_id, provenance_by_id.get(source_id), stale_sources, warnings, errors)

        for memory in package.memories:
            memory_id = memory.get("memory_id") if isinstance(memory, dict) else None
            if not memory_id:
                errors.append(f"malformed memory entry (no memory_id): {memory!r}")
                continue
            self._check_provenance(memory_id, provenance_by_id, provenance_issues, errors)
            self._check_authorization(
                agent_id, scope_id, memory_id, {"context_type": memory.get("memory_type")}, invalid_sources, errors
            )
            self._check_secret_content(memory_id, memory.get("content"), invalid_sources, errors)
            # no freshness check for memories -- neither this series nor
            # backend.llm.context_freshness establishes a staleness
            # concept for them (see backend.agent_task_context_resolution's
            # own choice not to wire memory into freshness either)

        return ContextIntegrityResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            invalid_sources=sorted(set(invalid_sources)),
            stale_sources=sorted(set(stale_sources)),
            provenance_issues=provenance_issues,
        )

    # -- task-level checks ------------------------------------------------------

    @staticmethod
    def _check_ownership(package, agent_id, scope_id, errors) -> None:
        task = package.task
        if task.get("agent_id") != agent_id or task.get("scope_id") != scope_id:
            errors.append(
                f"package belongs to agent {task.get('agent_id')!r} in scope {task.get('scope_id')!r}, "
                f"not agent {agent_id!r} in scope {scope_id!r}"
            )

    @staticmethod
    def _check_mandatory_task_data(package, errors) -> None:
        task = package.task
        for field_name in ("task_id", "agent_id", "scope_id", "objective"):
            if not task.get(field_name):
                errors.append(f"mandatory task data missing: {field_name!r}")

    # -- per-source checks --------------------------------------------------------

    @staticmethod
    def _check_source_shape(message, errors, invalid_sources):
        if not isinstance(message, dict) or "role" not in message or "content" not in message:
            errors.append(f"malformed context message: {message!r}")
            return None

        metadata = message.get("metadata") or {}
        context_id = metadata.get("context_id")
        if not context_id:
            errors.append("context message is missing its own metadata.context_id")
            return None

        if message["role"] != CONTEXT_ROLE:
            invalid_sources.append(context_id)
            errors.append(f"context {context_id!r} has an unexpected role {message['role']!r}")

        if not message.get("content"):
            errors.append(f"context {context_id!r} has empty content")

        return context_id

    def _check_provenance(self, source_id, provenance_by_id, provenance_issues, errors) -> None:
        record = provenance_by_id.get(source_id)
        if record is None:
            provenance_issues.append({"id": source_id, "issue": "missing provenance"})
            errors.append(f"source {source_id!r} has no provenance record")
            return

        if self._provenance_service is not None:
            try:
                self._provenance_service.validate(record)
            except (InvalidSourceError, SecretProvenanceError) as error:
                provenance_issues.append({"id": source_id, "issue": str(error)})
                errors.append(f"source {source_id!r} has invalid provenance: {error}")
            return

        issues = self._provenance_shape_issues(record)
        if issues:
            issue_text = "; ".join(issues)
            provenance_issues.append({"id": source_id, "issue": issue_text})
            errors.append(f"source {source_id!r} has inconsistent provenance: {issue_text}")

    @staticmethod
    def _normalize_provenance(record):
        """package.provenance (backend.agent_task_context_packaging.
        AgentContextPackage's own documented shape) holds plain dicts --
        Commit #4's packager renders each LLMContextProvenance via
        asdict() for JSON-friendliness -- reconstructed back into the
        real repository type here, the same conversion backend.
        agent_task_context_provenance.provenance_from_dict() already
        performs for the identical shape mismatch. A caller that already
        passes real LLMContextProvenance instances is unaffected."""
        if isinstance(record, LLMContextProvenance):
            return record
        payload = dict(record)
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            payload["created_at"] = datetime.fromisoformat(created_at)
        return LLMContextProvenance(**payload)

    @staticmethod
    def _provenance_shape_issues(record) -> list:
        """The same field-level checks LLMContextProvenanceService.validate()
        itself applies before ever touching a store, mirrored locally so
        this still catches an inconsistent record even with no live
        provenance_service supplied."""
        issues = []
        for field_name in ("context_id", "source_id", "excerpt"):
            value = getattr(record, field_name, None)
            if not value or not isinstance(value, str):
                issues.append(f"{field_name} is missing")
        if record.source_type not in VALID_SOURCE_TYPES:
            issues.append(f"source_type {record.source_type!r} is not recognized")
        return issues

    def _check_authorization(self, agent_id, scope_id, source_id, metadata, invalid_sources, errors) -> None:
        if self._policy_resolver is None:
            return

        action = {
            "agent_id": agent_id,
            "scope_id": scope_id,
            "context_id": source_id,
            "context_type": metadata.get("context_type"),
        }
        for resolved in self._policy_resolver.resolve(scope_id):
            decision = self._policy_evaluator.evaluate(resolved.policy, action)
            if decision.rule_id is not None and decision.effect == DENY:
                invalid_sources.append(source_id)
                errors.append(
                    f"source {source_id!r} denied for agent {agent_id!r} in scope {scope_id!r} by "
                    f"policy {decision.policy_id!r} rule {decision.rule_id!r}: {decision.reason}"
                )
                return

    def _check_secret_content(self, source_id, content, invalid_sources, errors) -> None:
        findings = self._secret_redaction.detect(content)
        if findings:
            invalid_sources.append(source_id)
            locations = ", ".join(f"{finding['location']} ({finding['pattern']})" for finding in findings)
            errors.append(f"source {source_id!r} content appears to contain a secret: {locations}")

    def _check_freshness(self, source_id, provenance_record, stale_sources, warnings, errors) -> None:
        if self._freshness_service is None or provenance_record is None:
            return
        if provenance_record.source_type != "project_context":
            return

        try:
            result = self._freshness_service.check(source_id)
        except UnknownProjectContextError:
            stale_sources.append(source_id)
            errors.append(f"source {source_id!r} no longer exists in project context (stale)")
            return

        if result.status == STALE:
            stale_sources.append(source_id)
            errors.append(f"source {source_id!r} is stale: {result.reason}")
        elif result.status == UNKNOWN:
            warnings.append(f"source {source_id!r} freshness could not be determined: {result.reason}")

    @staticmethod
    def _validate_args(package, agent_id, scope_id) -> None:
        if not isinstance(package, AgentContextPackage):
            raise InvalidContextIntegrityError(
                f"package must be an AgentContextPackage, got {type(package).__name__}"
            )
        if not agent_id or not isinstance(agent_id, str):
            raise InvalidContextIntegrityError("agent_id is required and must be a non-empty string")
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidContextIntegrityError("scope_id is required and must be a non-empty string")
