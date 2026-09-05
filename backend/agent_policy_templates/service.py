import re

from backend.agent_policy_engine import LLMAgentPolicy, LLMAgentPolicyRule, LLMAgentPolicyService

from .in_memory_store import InMemoryLLMAgentPolicyTemplateInstantiationStore, InMemoryLLMAgentPolicyTemplateStore
from .models import ACTIVE, ARCHIVED, STATUSES, LLMAgentPolicyTemplate, LLMAgentPolicyTemplateInstantiation
from .store import LLMAgentPolicyTemplateInstantiationStore, LLMAgentPolicyTemplateStore

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _placeholders_in(value) -> set:
    """Every "{parameter}" name referenced anywhere within value (a
    template's policy_definition, or any part of it) -- the complete set
    of parameters instantiate() must be given, derived from the
    definition itself rather than kept as a second, independently
    maintained list that could drift out of sync with it."""
    found = set()
    if isinstance(value, str):
        found.update(_PLACEHOLDER_RE.findall(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.update(_placeholders_in(key))
            found.update(_placeholders_in(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_placeholders_in(item))
    return found


def _substitute(value, parameters: dict):
    """value with every "{parameter}" reference replaced by its resolved
    instantiate()-time value -- structure-preserving, applied recursively
    to every string reachable within a policy_definition's name_template
    and rules."""
    if isinstance(value, str):
        return value.format(**parameters) if _PLACEHOLDER_RE.search(value) else value
    if isinstance(value, dict):
        return {_substitute(key, parameters): _substitute(item, parameters) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_substitute(item, parameters) for item in value]
    return value


class UnknownPolicyTemplateError(KeyError):
    """Raised when get()/update()/archive()/instantiate() is given a
    template_id that was never created."""


class UnknownPolicyTemplateInstantiationError(KeyError):
    """Raised when provenance() is given a policy_id that was never
    produced by instantiate()."""


class InvalidPolicyTemplateError(ValueError):
    """Raised when a template's name or description is missing or the
    wrong type."""


class InvalidPolicyTemplateDefinitionError(ValueError):
    """Raised when a template's policy_definition is missing, malformed,
    or embeds a scope_id -- a template must stay reusable across every
    scope, never fixed to one."""


class InvalidPolicyTemplateStatusError(ValueError):
    """Raised when a status argument is not one of STATUSES."""


class ArchivedPolicyTemplateError(ValueError):
    """Raised when update() or instantiate() is given a template_id that
    is already ARCHIVED.

    An archived template is retired, deliberately-preserved history --
    the same reasoning backend.agent_policy_engine.LLMAgentPolicyService
    already applies to an ARCHIVED policy. Reviving one requires a fresh
    create() call, not a mutation of the archived record, and an archived
    template can never be instantiated again.
    """


class InvalidTemplateParametersError(ValueError):
    """Raised when instantiate() is given a parameters argument that is
    not a dict."""


class MissingTemplateParameterError(ValueError):
    """Raised when instantiate() is missing a value for a parameter the
    template's own policy_definition actually references."""


class UnexpectedTemplateParameterError(ValueError):
    """Raised when instantiate() is given a parameter value the
    template's own policy_definition never references."""


class LLMAgentPolicyTemplateService:
    """Creates, reads, and retires reusable, versioned policy templates,
    and instantiates them into real, scope-bound Commit #1 LLMAgentPolicy
    records.

    Not a second policy or registry framework: template persistence
    follows the exact save/get/list split
    backend.agent_policy_engine.LLMAgentPolicyStore already uses (an
    InMemoryLLMAgentPolicyTemplateStore by default, or a JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile), a template's
    own rules are screened through Commit #1's own
    LLMAgentPolicyRule.from_dict() -- the exact same rule validation an
    ordinary policy already gets, never a second rule-shape check -- and
    instantiate() always finishes by calling Commit #1's own
    LLMAgentPolicyService.create() verbatim, so an instantiated policy is
    a completely ordinary LLMAgentPolicy, indistinguishable from one
    created by hand, subject to the exact same later validation/version/
    history/governance machinery every other commit in this series
    already provides for it.

    A template is deliberately never scope-bound itself (see
    _validate_definition: a policy_definition may never embed its own
    scope_id) -- the real scope_id is supplied fresh at every
    instantiate() call, so the same template can be reused, unmodified,
    across as many scopes as a caller wants. What ties an instantiated
    policy back to the template/version that produced it is not a new
    field on LLMAgentPolicy itself (Commit #1's own record gains nothing
    new here) but a separate, append-only
    LLMAgentPolicyTemplateInstantiation record, looked up by the
    instantiated policy's own policy_id via provenance() -- so
    provenance for one scope's policy can never be confused with, or leak
    into, another scope's.

    No LLM call and no automatic policy generation happens anywhere in
    this class: instantiate() only ever fills in "{parameter}"
    placeholders a caller explicitly supplied, into a policy_definition a
    caller explicitly authored.
    """

    def __init__(
        self,
        policy_service: LLMAgentPolicyService,
        store: LLMAgentPolicyTemplateStore = None,
        instantiation_store: LLMAgentPolicyTemplateInstantiationStore = None,
    ):
        self._policy_service = policy_service
        self.store = store if store is not None else InMemoryLLMAgentPolicyTemplateStore()
        self._instantiation_store = (
            instantiation_store
            if instantiation_store is not None
            else InMemoryLLMAgentPolicyTemplateInstantiationStore()
        )

    def create(self, name: str, description: str, policy_definition: dict) -> LLMAgentPolicyTemplate:
        """Record a new, ACTIVE, version-1 policy template.

        Raises:
            InvalidPolicyTemplateError: If name or description is missing
                or the wrong type
            InvalidPolicyTemplateDefinitionError: If policy_definition is
                missing, malformed, or embeds a scope_id
            InvalidPolicyRuleError: If any rule within policy_definition's
                own fields are invalid (propagated from Commit #1's own
                LLMAgentPolicyRule.from_dict(), not wrapped)
        """
        self._validate_name(name)
        self._validate_description(description)
        resolved_definition = self._validate_definition(policy_definition)

        template = LLMAgentPolicyTemplate(
            name=name, description=description, policy_definition=resolved_definition, version=1, status=ACTIVE,
        )
        return self.store.save(template)

    def get(self, template_id: str) -> LLMAgentPolicyTemplate:
        template = self.store.get(template_id)
        if template is None:
            raise UnknownPolicyTemplateError(template_id)
        return template

    def list(self, status: str = None) -> list:
        if status is not None:
            self._validate_status(status)
        return self.store.list(status)

    def update(
        self, template_id: str, name: str = None, description: str = None, policy_definition: dict = None,
    ) -> LLMAgentPolicyTemplate:
        """Update one or more of name/description/policy_definition on an
        existing, still-ACTIVE template. Fields left as None are
        unchanged. Changing policy_definition to something that actually
        differs from the current one bumps version; renaming or
        redescribing a template never does.

        Raises:
            UnknownPolicyTemplateError: If template_id was never created
            ArchivedPolicyTemplateError: If template_id is already ARCHIVED
            InvalidPolicyTemplateError, InvalidPolicyTemplateDefinitionError,
                InvalidPolicyRuleError: If a given field fails validation
        """
        template = self.get(template_id)
        if template.status == ARCHIVED:
            raise ArchivedPolicyTemplateError(f"template {template_id!r} is archived and cannot be updated")

        if name is not None:
            self._validate_name(name)
            template.name = name
        if description is not None:
            self._validate_description(description)
            template.description = description
        if policy_definition is not None:
            resolved_definition = self._validate_definition(policy_definition)
            if resolved_definition != template.policy_definition:
                template.version += 1
            template.policy_definition = resolved_definition

        return self.store.save(template)

    def archive(self, template_id: str) -> LLMAgentPolicyTemplate:
        """Retire template_id by marking it ARCHIVED, never by deleting
        it -- an archived template stays exactly as reachable through
        get()/list() as any other. Idempotent: archiving an
        already-ARCHIVED template simply returns it unchanged. An
        ARCHIVED template can never be instantiated again (see
        instantiate()), though every policy already instantiated from it
        is completely unaffected.

        Raises:
            UnknownPolicyTemplateError: If template_id was never created
        """
        template = self.get(template_id)
        if template.status == ARCHIVED:
            return template

        template.status = ARCHIVED
        return self.store.save(template)

    def instantiate(self, template_id: str, scope_id: str, parameters: dict = None) -> LLMAgentPolicy:
        """Fill template_id's policy_definition in with parameters and
        create a completely ordinary, scope-bound LLMAgentPolicy from the
        result via Commit #1's own LLMAgentPolicyService.create().

        Raises:
            UnknownPolicyTemplateError: If template_id was never created
            ArchivedPolicyTemplateError: If template_id is ARCHIVED
            InvalidTemplateParametersError: If parameters is not a dict
            MissingTemplateParameterError: If a parameter the template's
                own definition references was not supplied
            UnexpectedTemplateParameterError: If a supplied parameter is
                never referenced anywhere in the template's definition
            InvalidAgentPolicyError, InvalidPolicyRuleError,
                DuplicateRuleIdError: Propagated unchanged from Commit
                #1's own LLMAgentPolicyService.create() (e.g. an invalid
                scope_id, or a duplicate rule_id only introduced once
                parameters are substituted in)
        """
        template = self.get(template_id)
        if template.status == ARCHIVED:
            raise ArchivedPolicyTemplateError(f"template {template_id!r} is archived and cannot be instantiated")

        if parameters is None:
            parameters = {}
        if not isinstance(parameters, dict):
            raise InvalidTemplateParametersError("parameters must be a dict")

        declared = _placeholders_in(template.policy_definition)
        given = set(parameters.keys())
        missing = declared - given
        if missing:
            raise MissingTemplateParameterError(f"missing required parameter(s): {sorted(missing)}")
        extra = given - declared
        if extra:
            raise UnexpectedTemplateParameterError(
                f"unexpected parameter(s) not used by this template: {sorted(extra)}"
            )

        resolved = _substitute(template.policy_definition, parameters)
        policy = self._policy_service.create(scope_id, resolved["name_template"], resolved["rules"])

        self._instantiation_store.save(
            LLMAgentPolicyTemplateInstantiation(
                template_id=template.template_id,
                template_version=template.version,
                scope_id=scope_id,
                policy_id=policy.policy_id,
                parameters=dict(parameters),
            )
        )
        return policy

    def provenance(self, policy_id: str) -> LLMAgentPolicyTemplateInstantiation:
        """The LLMAgentPolicyTemplateInstantiation record for policy_id --
        exactly which template, and which version of it, produced this
        policy, and with what parameters.

        Raises:
            UnknownPolicyTemplateInstantiationError: If policy_id was
                never produced by instantiate()
        """
        record = self._instantiation_store.get_for_policy(policy_id)
        if record is None:
            raise UnknownPolicyTemplateInstantiationError(policy_id)
        return record

    def list_instantiations(self, template_id: str) -> list:
        """Every LLMAgentPolicyTemplateInstantiation produced from
        template_id, oldest first -- across every scope it has ever been
        instantiated into."""
        return self._instantiation_store.list_for_template(template_id)

    @staticmethod
    def _validate_name(name):
        if not name or not isinstance(name, str):
            raise InvalidPolicyTemplateError("name is required")

    @staticmethod
    def _validate_description(description):
        if not description or not isinstance(description, str):
            raise InvalidPolicyTemplateError("description is required")

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidPolicyTemplateStatusError(f"status {status!r} is not one of {sorted(STATUSES)}")

    @staticmethod
    def _validate_definition(policy_definition) -> dict:
        if not isinstance(policy_definition, dict):
            raise InvalidPolicyTemplateDefinitionError("policy_definition must be a dict")
        if "scope_id" in policy_definition:
            raise InvalidPolicyTemplateDefinitionError(
                "policy_definition must not embed a scope_id -- templates must stay "
                "scope-safe, reusable across every scope"
            )

        name_template = policy_definition.get("name_template")
        if not name_template or not isinstance(name_template, str):
            raise InvalidPolicyTemplateDefinitionError("policy_definition.name_template is required")

        rules = policy_definition.get("rules")
        if not rules or not isinstance(rules, list):
            raise InvalidPolicyTemplateDefinitionError(
                "policy_definition.rules is required and must be a non-empty list"
            )

        seen_ids = set()
        for rule in rules:
            if not isinstance(rule, dict):
                raise InvalidPolicyTemplateDefinitionError("each rule in policy_definition.rules must be a dict")
            try:
                resolved_rule = LLMAgentPolicyRule.from_dict(rule)
            except TypeError as error:
                raise InvalidPolicyTemplateDefinitionError(
                    f"invalid rule in policy_definition.rules: {error}"
                ) from error
            # InvalidPolicyRuleError (already ValueError) propagates unchanged --
            # reuses Commit #1's own rule validation verbatim, never a second check.
            if resolved_rule.rule_id in seen_ids:
                raise InvalidPolicyTemplateDefinitionError(
                    f"rule_id {resolved_rule.rule_id!r} is duplicated within this template"
                )
            seen_ids.add(resolved_rule.rule_id)

        return {"name_template": name_template, "rules": [dict(rule) for rule in rules]}
