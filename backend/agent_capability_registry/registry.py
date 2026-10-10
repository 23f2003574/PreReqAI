from copy import deepcopy

from .in_memory_store import InMemoryCapabilityStore
from .models import ACTIVE, ARCHIVED, STATUSES, LLMAgentCapability
from .store import CapabilityStore

_UPDATABLE_FIELDS = frozenset({"name", "description", "category", "version", "metadata"})
_IMMUTABLE_FIELDS = frozenset({"capability_id", "status", "created_at", "updated_at"})


class UnknownCapabilityError(KeyError):
    """Raised when get()/update()/archive() is given a capability_id that
    was never registered."""


class InvalidCapabilityError(ValueError):
    """Raised when a capability's capability_id, name, description,
    category, version, status, or metadata is missing, blank, or the
    wrong type."""


class DuplicateCapabilityIdError(InvalidCapabilityError):
    """Raised when register() is given a capability_id that is already
    registered -- capability_id must uniquely identify one capability
    across the entire registry, active or archived."""


class InvalidCapabilityChangesError(InvalidCapabilityError):
    """Raised when update()'s changes argument is not a dict, is empty,
    or attempts to change an immutable field (capability_id, status,
    created_at, updated_at) or an unrecognized one.

    capability_id must stay stable for the life of a capability record,
    and status is changed only through archive(), never through an
    arbitrary changes dict -- the same "identifiers/lifecycle transitions
    are never smuggled through a generic update" discipline
    backend.agent_policy_templates.LLMAgentPolicyTemplateService.update()
    and backend.agent_risk_profile.LLMAgentRiskProfileService.update()
    already keep for their own explicit-kwargs update() signatures.
    """


class ArchivedCapabilityError(ValueError):
    """Raised when update() is given a capability_id that is already
    ARCHIVED.

    An archived capability is retired, deliberately-preserved history --
    the same reasoning backend.agent_policy_templates.
    LLMAgentPolicyTemplateService and backend.agent_risk_profile.
    LLMAgentRiskProfileService already apply to an ARCHIVED record.
    Reviving one requires a fresh register() call under a new
    capability_id, not a mutation of the archived record. Archived
    capabilities remain fully readable via get()/list()/exists(), only
    update() rejects them.
    """


class LLMAgentCapabilityRegistry:
    """The canonical, queryable inventory of concrete capabilities an LLM
    agent may use.

    This is capability metadata only -- register()/get()/list()/update()/
    archive()/exists() catalog what capabilities exist, their category,
    version, and status. It never executes a capability, never grants or
    checks a permission to use one (backend.llm.tool_permissions already
    owns that), and never plans which capabilities an agent should invoke
    for a task (that stays entirely a planning concern downstream of this
    registry). Persistence follows the exact save/get/list split
    backend.agent_policy_templates.LLMAgentPolicyTemplateStore already
    established (an InMemoryCapabilityStore by default, or a
    JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile) -- not a second registry/storage
    framework, and not a duplicate of backend.llm.tools.LLMToolRegistryService,
    which catalogs tool-use/function-calling schemas, an unrelated concern.

    register() takes an already-constructed LLMAgentCapability (or an
    equivalent dict) rather than building one from individual keyword
    arguments -- capability_id is caller-chosen and human-meaningful (the
    same convention backend.llm.tools.LLMToolDefinition.tool_id already
    uses), never registry-generated, so callers always know up front the
    identifier under which a capability will be registered.

    list() defaults to ACTIVE-only results (status=None), so archived
    capabilities never leak into normal listings -- exactly the
    "excluded from normal active listings" rule this registry keeps.
    They remain fully reachable by passing status=ARCHIVED explicitly, or
    via get()/exists(), which never filter by status at all.
    """

    def __init__(self, store: CapabilityStore = None):
        self.store = store if store is not None else InMemoryCapabilityStore()

    def register(self, capability) -> LLMAgentCapability:
        """Record a new capability under its own capability_id.

        capability may be an LLMAgentCapability instance or an
        equivalent dict.

        Raises:
            InvalidCapabilityError: If capability_id, name, description,
                category, version, status, or metadata is missing, blank,
                or the wrong type
            DuplicateCapabilityIdError: If capability_id is already
                registered (active or archived)
        """
        resolved = self._resolve_capability(capability)
        self._validate_capability(resolved)

        if self.exists(resolved.capability_id):
            raise DuplicateCapabilityIdError(
                f"capability_id {resolved.capability_id!r} is already registered"
            )

        return self.store.save(resolved)

    def get(self, capability_id: str) -> LLMAgentCapability:
        """Fetch capability_id regardless of status -- archived
        capabilities remain fully readable.

        Raises:
            UnknownCapabilityError: If capability_id was never registered
        """
        capability = self.store.get(capability_id)
        if capability is None:
            raise UnknownCapabilityError(capability_id)
        return capability

    def list(self, category: str = None, status: str = None) -> list:
        """Every registered capability, oldest first, optionally filtered
        by category and/or status.

        status=None (the default) returns ACTIVE capabilities only --
        archived capabilities are excluded from this normal listing.
        Pass status=ARCHIVED explicitly to see archived capabilities, or
        get()/exists() to reach one directly regardless of status.

        Raises:
            InvalidCapabilityError: If category or status is given and
                fails validation (status must be one of STATUSES)
        """
        if category is not None:
            self._validate_category(category)
        if status is not None:
            self._validate_status(status)
            effective_status = status
        else:
            effective_status = ACTIVE

        capabilities = self.store.list(effective_status)
        if category is not None:
            capabilities = [capability for capability in capabilities if capability.category == category]
        return capabilities

    def update(self, capability_id: str, changes: dict) -> LLMAgentCapability:
        """Apply changes (a dict of field -> new value) to an existing,
        still-ACTIVE capability. Only name/description/category/version/
        metadata may be changed; capability_id, status, created_at, and
        updated_at are immutable through this method. Fields not
        mentioned in changes are left exactly as they were -- update()
        never resets or bumps version on its own, it only ever assigns
        what changes explicitly provides.

        Raises:
            UnknownCapabilityError: If capability_id was never registered
            ArchivedCapabilityError: If capability_id is already ARCHIVED
            InvalidCapabilityChangesError: If changes is not a dict, is
                empty, or names an immutable or unrecognized field
            InvalidCapabilityError: If a given field's new value fails
                validation
        """
        capability = self.get(capability_id)
        if capability.status == ARCHIVED:
            raise ArchivedCapabilityError(f"capability {capability_id!r} is archived and cannot be updated")

        if not isinstance(changes, dict) or not changes:
            raise InvalidCapabilityChangesError("changes must be a non-empty dict")

        unknown_or_immutable = set(changes) - _UPDATABLE_FIELDS
        if unknown_or_immutable:
            raise InvalidCapabilityChangesError(
                f"cannot change field(s) {sorted(unknown_or_immutable)}; "
                f"only {sorted(_UPDATABLE_FIELDS)} may be updated"
            )

        if "name" in changes:
            self._validate_name(changes["name"])
            capability.name = changes["name"]
        if "description" in changes:
            self._validate_description(changes["description"])
            capability.description = changes["description"]
        if "category" in changes:
            self._validate_category(changes["category"])
            capability.category = changes["category"]
        if "version" in changes:
            self._validate_version(changes["version"])
            capability.version = changes["version"]
        if "metadata" in changes:
            self._validate_metadata(changes["metadata"])
            capability.metadata = changes["metadata"]

        return self.store.save(capability)

    def archive(self, capability_id: str) -> LLMAgentCapability:
        """Retire capability_id by marking it ARCHIVED, never by deleting
        it -- an archived capability stays exactly as reachable through
        get()/exists() as any other, only list()'s default excludes it.
        Idempotent: archiving an already-ARCHIVED capability simply
        returns it unchanged.

        Raises:
            UnknownCapabilityError: If capability_id was never registered
        """
        capability = self.get(capability_id)
        if capability.status == ARCHIVED:
            return capability

        capability.status = ARCHIVED
        return self.store.save(capability)

    def exists(self, capability_id: str) -> bool:
        """Whether capability_id has ever been registered, regardless of
        status -- an archived capability still exists()."""
        return self.store.get(capability_id) is not None

    def _resolve_capability(self, capability) -> LLMAgentCapability:
        if isinstance(capability, LLMAgentCapability):
            return deepcopy(capability)
        if isinstance(capability, dict):
            return LLMAgentCapability.from_dict(capability)
        raise InvalidCapabilityError(
            f"capability must be an LLMAgentCapability or dict, got {type(capability).__name__}"
        )

    def _validate_capability(self, capability: LLMAgentCapability):
        if not capability.capability_id or not isinstance(capability.capability_id, str):
            raise InvalidCapabilityError("capability_id is required and must be a non-empty string")
        self._validate_name(capability.name)
        self._validate_description(capability.description)
        self._validate_category(capability.category)
        self._validate_version(capability.version)
        self._validate_status(capability.status)
        self._validate_metadata(capability.metadata)

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str):
            raise InvalidCapabilityError("name is required and must be a non-empty string")

    @staticmethod
    def _validate_description(description):
        if not description or not isinstance(description, str):
            raise InvalidCapabilityError("description is required and must be a non-empty string")

    @staticmethod
    def _validate_category(category):
        if not category or not isinstance(category, str):
            raise InvalidCapabilityError("category is required and must be a non-empty string")

    @staticmethod
    def _validate_version(version):
        if not version or not isinstance(version, str):
            raise InvalidCapabilityError("version is required and must be a non-empty string")

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidCapabilityError(f"status {status!r} is not one of {sorted(STATUSES)}")

    @staticmethod
    def _validate_metadata(metadata):
        if not isinstance(metadata, dict):
            raise InvalidCapabilityError("metadata must be a dict")
