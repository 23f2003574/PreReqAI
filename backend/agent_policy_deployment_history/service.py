import re

from .in_memory_store import InMemoryLLMAgentPolicyDeploymentHistoryStore
from .models import STATUSES, LLMAgentPolicyDeploymentRecord
from .store import LLMAgentPolicyDeploymentHistoryStore

# Same secret-detection/redaction convention already kept locally by
# backend.agent_policy_audit, backend.llm.tool_audit,
# backend.agent_strategy_decision_audit, backend.agent_execution_memory,
# and backend.agent_strategy_library -- kept local here too rather than
# refactoring any of those.
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


def _redact(value: str) -> str:
    return "[REDACTED]" if _looks_secret(value) else value


class UnknownDeploymentRecordError(KeyError):
    """Raised when get() is given a deployment_id that was never
    recorded."""


class InvalidDeploymentRecordError(ValueError):
    """Raised when record() is given a policy_id/target_scope that is
    missing, or a status that is not one of STATUSES."""


class LLMAgentPolicyDeploymentHistory:
    """Makes every Commit #7 deploy() attempt -- successful or failed --
    observable after the fact, as one append-only, scope-isolated
    history trail.

    Not a new audit/event framework: persistence follows the exact
    save/get/list_for_-- split
    backend.agent_policy_audit.LLMAgentPolicyAuditService already
    established for this series' other decision trail (an
    InMemoryLLMAgentPolicyDeploymentHistoryStore by default, or the
    JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile), and provenance string values are
    passed through the exact same secret-redaction convention that
    service already applies to its own reason fields.

    record() takes already-known facts about one deployment attempt --
    it never calls Commit #7's own deploy(), evaluates compatibility, or
    mutates a policy/template itself. Recording is always the last thing
    that happens to a deployment attempt already fully decided (see
    backend.agent_policy_deployment_history.tracked.
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService, which is
    the actual integration point into the real deployment path), so
    recording can never itself change what was deployed, by
    construction.
    """

    def __init__(self, store: LLMAgentPolicyDeploymentHistoryStore = None):
        self.store = store if store is not None else InMemoryLLMAgentPolicyDeploymentHistoryStore()

    def record(
        self,
        policy_id: str,
        target_scope: str,
        status: str,
        template_id: str = None,
        template_version: int = None,
        policy_version: int = None,
        provenance: dict = None,
        deployment_id: str = None,
    ) -> LLMAgentPolicyDeploymentRecord:
        """Append one deployment record.

        deployment_id, when given, is used verbatim as this record's own
        id -- the integration point (see
        backend.agent_policy_deployment_history.tracked) passes Commit
        #7's own real DeploymentResult.deployment_id here for a
        DEPLOYMENT_SUCCEEDED record, so the two stay directly
        correlated by the same id, rather than minting a second,
        independent identifier for the same successful deployment. Left
        as None (a fresh one generated), it is always appropriate for a
        DEPLOYMENT_FAILED record, since no DeploymentResult was ever
        produced for a failed attempt.

        Raises:
            InvalidDeploymentRecordError: If policy_id/target_scope is
                missing, status is not one of STATUSES, or provenance is
                given and is not a dict
        """
        self._validate_text(policy_id, "policy_id")
        self._validate_text(target_scope, "target_scope")
        if status not in STATUSES:
            raise InvalidDeploymentRecordError(f"status {status!r} is not one of {sorted(STATUSES)}")
        if provenance is not None and not isinstance(provenance, dict):
            raise InvalidDeploymentRecordError("provenance must be a dict")

        redacted_provenance = {
            key: (_redact(value) if isinstance(value, str) else value) for key, value in (provenance or {}).items()
        }

        kwargs = dict(
            policy_id=policy_id,
            target_scope=target_scope,
            status=status,
            template_id=template_id,
            template_version=template_version,
            policy_version=policy_version,
            provenance=redacted_provenance,
        )
        if deployment_id is not None:
            kwargs["deployment_id"] = deployment_id

        return self.store.save(LLMAgentPolicyDeploymentRecord(**kwargs))

    def get(self, deployment_id: str) -> LLMAgentPolicyDeploymentRecord:
        record = self.store.get(deployment_id)
        if record is None:
            raise UnknownDeploymentRecordError(deployment_id)
        return record

    def list_for_policy(self, policy_id: str) -> list:
        """Every deployment record for policy_id, oldest first."""
        self._validate_text(policy_id, "policy_id")
        return self.store.list_for_policy(policy_id)

    def list_for_scope(self, scope_id: str) -> list:
        """Every deployment record for scope_id, oldest first -- never
        includes a record from any other scope."""
        self._validate_text(scope_id, "scope_id")
        return self.store.list_for_scope(scope_id)

    @staticmethod
    def _validate_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidDeploymentRecordError(f"{field_name} is required")
