from backend.agent_policy_templates import (
    ACTIVE,
    STATUSES,
    LLMAgentPolicyTemplate,
    LLMAgentPolicyTemplateService,
    UnknownPolicyTemplateError,
)


class InvalidPolicyTemplateRegistrationError(ValueError):
    """Raised when register() is given something other than a real,
    already-created Commit #1 LLMAgentPolicyTemplate."""


class DuplicatePolicyTemplateVersionError(ValueError):
    """Raised when register() is given a template whose (name, version)
    pair is already registered -- including re-registering the exact
    same template_id a second time, since its (name, version) has
    necessarily not changed."""


class InvalidPolicyTemplateFilterError(ValueError):
    """Raised when list() is given a status filter that is not one of
    Commit #1's own STATUSES."""


class LLMAgentPolicyTemplateRegistry:
    """Discovers, resolves, and validates which Commit #1
    LLMAgentPolicyTemplate records are currently available for use, by
    name and version -- kept entirely separate from instantiated
    policies (the LLMAgentPolicy objects Commit #1's own
    LLMAgentPolicyTemplateService.instantiate() produces), which this
    registry never touches, stores, or resolves.

    Not a second storage framework: every LLMAgentPolicyTemplate this
    registry ever returns is fetched fresh from Commit #1's own
    LLMAgentPolicyTemplateService.get() -- the registry's own state is
    nothing more than a name/version -> template_id index, never a copy
    of a template's own fields, so a registration can never drift from,
    or go stale against, the one real Commit #1 record it names.
    get()/list()/resolve() are pure reads: none of them ever calls the
    underlying service's create()/update()/archive(), so a lookup can
    never mutate a template, exactly as "no template mutation through
    lookup/resolve operations" requires.

    version, for both register() and resolve(), is always Commit #1's
    own LLMAgentPolicyTemplate.version field -- never a second,
    independently-tracked counter. A template's own name is not unique in
    Commit #1 (create() may be called with the same name any number of
    times, each getting its own template_id starting at version 1) --
    this registry is what actually enforces name+version uniqueness
    among the templates a caller chooses to register, rejecting a
    duplicate (name, version) pair outright rather than silently
    overwriting the earlier registration. To register a second version
    under one name, a caller creates a second, independent template (a
    new template_id) and, before registering it, bumps its own version
    via Commit #1's own update() (e.g. by editing its policy_definition)
    -- since Commit #1's update() mutates a template_id's version in
    place rather than minting a new record, a caller who wants an old
    version's content to remain resolvable forever must never update()
    that same template_id again after registering it; this registry
    always reflects a template_id's current, live state, exactly like
    Commit #1's own get(), and does not keep a private, second copy of
    what a version "used to" contain.

    scope_id never appears anywhere in this registry's API: templates
    stay scope-safe exactly as Commit #1 established, and the real
    scope_id is still only ever supplied at
    LLMAgentPolicyTemplateService.instantiate() time, once a caller has
    resolved the template it wants through this registry.
    """

    def __init__(self, template_service: LLMAgentPolicyTemplateService):
        self._template_service = template_service
        self._by_name_version: dict[str, dict[int, str]] = {}
        self._name_by_template_id: dict[str, str] = {}

    def register(self, template: LLMAgentPolicyTemplate) -> LLMAgentPolicyTemplate:
        """Admit template into this registry's name/version index, keyed
        by its own current name and version.

        template is trusted only for its template_id: the record
        actually indexed and returned is always re-fetched fresh via
        Commit #1's own get(), so a caller can never register a forged
        or stale name/version by mutating a local copy before calling
        this.

        Raises:
            InvalidPolicyTemplateRegistrationError: If template is not
                an LLMAgentPolicyTemplate
            UnknownPolicyTemplateError: If template.template_id was never
                created by Commit #1's own service (propagated from
                get(), not wrapped)
            DuplicatePolicyTemplateVersionError: If this exact
                (name, version) pair is already registered
        """
        if not isinstance(template, LLMAgentPolicyTemplate):
            raise InvalidPolicyTemplateRegistrationError(
                f"template must be an LLMAgentPolicyTemplate, got {type(template).__name__}"
            )

        canonical = self._template_service.get(template.template_id)

        versions = self._by_name_version.setdefault(canonical.name, {})
        if canonical.version in versions:
            raise DuplicatePolicyTemplateVersionError(
                f"version {canonical.version} of template {canonical.name!r} is already registered"
            )

        versions[canonical.version] = canonical.template_id
        self._name_by_template_id[canonical.template_id] = canonical.name
        return canonical

    def unregister(self, template_id: str) -> None:
        """Remove template_id from this registry's discovery index --
        never touches, archives, or deletes the underlying Commit #1
        record itself, which remains exactly as reachable through
        LLMAgentPolicyTemplateService as before.

        Raises:
            UnknownPolicyTemplateError: If template_id was never
                registered in this registry
        """
        name = self._name_by_template_id.pop(template_id, None)
        if name is None:
            raise UnknownPolicyTemplateError(template_id)

        versions = self._by_name_version.get(name, {})
        for version, registered_id in list(versions.items()):
            if registered_id == template_id:
                del versions[version]
        if not versions:
            del self._by_name_version[name]

    def get(self, template_id: str) -> LLMAgentPolicyTemplate:
        """The current, canonical LLMAgentPolicyTemplate registered under
        template_id.

        Raises:
            UnknownPolicyTemplateError: If template_id was never
                registered in this registry -- even if it exists in
                Commit #1's own store, since registration is this
                registry's own, separate notion of "available for
                discovery"
        """
        if template_id not in self._name_by_template_id:
            raise UnknownPolicyTemplateError(template_id)
        return self._template_service.get(template_id)

    def list(self, filters: dict = None) -> list:
        """Every registered template matching filters, ordered
        deterministically by (name, version).

        filters is an optional dict supporting:
          - "name": only templates registered under this exact name
          - "status": only templates currently at this Commit #1 status
            (ACTIVE or ARCHIVED)

        Omitted, list() returns templates of every status: an archived
        template stays fully discoverable through list()/get(), never
        hidden by default. It is only resolve()'s own default (no
        version given) that skips ARCHIVED templates.

        Raises:
            InvalidPolicyTemplateFilterError: If filters["status"] is
                given and is not one of Commit #1's own STATUSES
        """
        filters = filters or {}
        name_filter = filters.get("name")
        status_filter = filters.get("status")
        if status_filter is not None and status_filter not in STATUSES:
            raise InvalidPolicyTemplateFilterError(f"status {status_filter!r} is not one of {sorted(STATUSES)}")

        results = []
        for template_id in self._name_by_template_id:
            template = self._template_service.get(template_id)
            if name_filter is not None and template.name != name_filter:
                continue
            if status_filter is not None and template.status != status_filter:
                continue
            results.append(template)

        return sorted(results, key=lambda item: (item.name, item.version))

    def resolve(self, name: str, version: int = None) -> LLMAgentPolicyTemplate:
        """The registered template for name -- deterministically, the
        exact version when version is given (returned regardless of its
        current ACTIVE/ARCHIVED status: an explicit version request
        always resolves, since an archived template stays fully
        discoverable), or otherwise the highest-numbered still-ACTIVE
        version registered under name.

        Raises:
            UnknownPolicyTemplateError: If name was never registered, no
                such version was ever registered under it, or (when
                version is omitted) every registered version under name
                is currently ARCHIVED
        """
        versions = self._by_name_version.get(name)
        if not versions:
            raise UnknownPolicyTemplateError(f"no registered template named {name!r}")

        if version is not None:
            template_id = versions.get(version)
            if template_id is None:
                raise UnknownPolicyTemplateError(f"no version {version} registered for template {name!r}")
            return self._template_service.get(template_id)

        for candidate_version in sorted(versions, reverse=True):
            template = self._template_service.get(versions[candidate_version])
            if template.status == ACTIVE:
                return template
        raise UnknownPolicyTemplateError(f"no active version registered for template {name!r}")
