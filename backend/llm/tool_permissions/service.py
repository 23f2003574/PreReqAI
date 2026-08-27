from threading import RLock

from ..tool_invocation import READY, LLMToolInvocationPlan
from ..tools import DisabledToolError, LLMToolRegistryService, UnknownToolError
from .models import (
    ANY_SUBJECT,
    AUTHORIZED,
    CONDITIONAL,
    DENIED,
    InvalidToolPolicyError,
    LLMToolAuthorization,
    LLMToolPermissionPolicy,
)


class DuplicateToolPolicyError(InvalidToolPolicyError):
    """Raised when register() is called twice for the same policy_id."""


class UnknownToolPolicyError(KeyError):
    """Raised when revoke() names a policy_id that is not registered."""


class LLMToolPermissionService:
    """Controls which subjects may invoke which registered LLM tools (Commit #4).

    Follows the authorization model the repo already uses for execution
    resources -- ExecutionNetworkTrafficPolicyService for allow/deny policy
    bookkeeping and ExecutionArtifactAccessService for default-deny
    authorization -- rather than introducing a second one:

    - register() admits a policy the caller already built, once per
      policy_id; a second register() for the same policy_id is rejected
      outright, and the tool it governs must already exist in the Commit #1
      registry
    - authorize() decides whether a subject may run one Commit #3 invocation
      plan, and denies by default when no policy applies
    - revoke() takes effect immediately: the next authorize() reflects it
    - policies() reports every policy registered for a tool, in registration
      order

    Where it deliberately differs from the network-traffic precedent: that
    service resolves competing policies by specificity and recency, while
    here an explicit deny always wins over any allow, however specific or
    recent, because a tool denial must never be overridable by adding
    another policy.

    This service is bookkeeping and decision-making only. It enforces
    nothing and executes nothing -- a caller is expected to authorize()
    before invoking a tool and to act on the result. No tool is executed in
    this commit at all.

    The service is thread-safe: all mutation and reads are guarded by an
    internal lock.
    """

    def __init__(
        self,
        registry: LLMToolRegistryService,
        invocation_service=None,
    ):
        """
        Args:
            registry: The Commit #1 tool registry, used to confirm a tool
                exists before a policy is registered for it, and to check
                that it is still enabled at authorization time
            invocation_service: Optional Commit #3 LLMToolInvocationService.
                When given, its validate() is re-run at authorization time so
                a plan that has since gone stale is denied
        """
        self._registry = registry
        self._invocation_service = invocation_service
        self._policies_by_id = {}
        self._order = []
        self._lock = RLock()

    def register(self, policy: LLMToolPermissionPolicy) -> LLMToolPermissionPolicy:
        """Register a policy for an already-registered tool.

        Raises:
            InvalidToolPolicyError: If policy is not an
                LLMToolPermissionPolicy
            DuplicateToolPolicyError: If its policy_id is already registered
            UnknownToolError: If its tool_name is not in the registry
        """
        if not isinstance(policy, LLMToolPermissionPolicy):
            raise InvalidToolPolicyError(
                f"Cannot register a policy that is not an LLMToolPermissionPolicy: {policy!r}."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise DuplicateToolPolicyError(
                    f"Cannot register policy ID {policy.policy_id!r}: it is already registered."
                )

            # Rule: the tool must exist. get() raises UnknownToolError, and is
            # used rather than get_invocable() so a policy may be written for a
            # tool that is currently disabled.
            self._registry.get(policy.tool_name)

            self._policies_by_id[policy.policy_id] = policy
            self._order.append(policy.policy_id)

            return policy

    def policies(self, tool_name: str) -> tuple:
        """Every policy registered for tool_name, in registration order.

        Raises:
            UnknownToolError: If tool_name is not in the registry
        """
        self._registry.get(tool_name)

        with self._lock:
            return tuple(
                self._policies_by_id[policy_id]
                for policy_id in self._order
                if self._policies_by_id[policy_id].tool_name == tool_name
            )

    def revoke(self, policy_id: str) -> LLMToolPermissionPolicy:
        """Remove a policy. The next authorize() call reflects it immediately.

        Raises:
            UnknownToolPolicyError: If no policy is registered under policy_id
        """
        with self._lock:
            policy = self._policies_by_id.pop(policy_id, None)
            if policy is None:
                raise UnknownToolPolicyError(policy_id)

            self._order.remove(policy_id)
            return policy

    @staticmethod
    def _subject_identities(subject) -> set:
        """The identities a caller presents -- one subject, or several scopes.

        A caller is usually more than one thing at once (a user, and the
        roles or scopes it holds), so authorize() accepts either a single
        string or a collection of them.
        """
        if isinstance(subject, str):
            identities = {subject}
        elif isinstance(subject, (list, tuple, set, frozenset)):
            identities = set(subject)
        else:
            raise InvalidToolPolicyError(
                f"subject must be a string or a collection of strings, got "
                f"{type(subject).__name__}"
            )

        if not identities or not all(
            isinstance(identity, str) and identity.strip() for identity in identities
        ):
            raise InvalidToolPolicyError("Cannot authorize an empty or blank subject.")

        return identities

    @staticmethod
    def _conditions_met(conditions: dict, arguments: dict) -> bool:
        """Whether a policy's argument constraints hold for this call.

        An argument the call does not carry can never satisfy a condition,
        so a conditioned policy simply does not apply to that call.
        """
        for name, expected in conditions.items():
            if name not in arguments:
                return False

            actual = arguments[name]
            if isinstance(expected, (list, tuple, set, frozenset)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False

        return True

    def _applicable(self, tool_name: str, identities: set, arguments: dict) -> list:
        """Registered policies matching this tool, subject, and arguments."""
        return [
            policy
            for policy_id in self._order
            for policy in (self._policies_by_id[policy_id],)
            if policy.tool_name == tool_name
            and (policy.subject in identities or policy.subject == ANY_SUBJECT)
            and self._conditions_met(policy.conditions, arguments)
        ]

    def authorize(self, plan, subject) -> LLMToolAuthorization:
        """Whether `subject` may invoke the tool call `plan` describes.

        Runs before any execution and performs none. Denies by default: a
        call is allowed only when the tool exists, is enabled, the plan is
        currently valid, and a matching allow policy applies with no
        matching deny.

        Raises:
            InvalidToolPolicyError: If plan is not an LLMToolInvocationPlan,
                or subject is empty, blank, or the wrong type
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise InvalidToolPolicyError(
                f"Cannot authorize something that is not an LLMToolInvocationPlan: {plan!r}."
            )

        identities = self._subject_identities(subject)
        tool_name = plan.tool_name

        # Rule: the tool must exist, and a disabled tool stays unavailable no
        # matter what any policy says. Both come straight from the Commit #1
        # registry's own gate rather than being re-derived here.
        try:
            self._registry.get_invocable(tool_name)
        except UnknownToolError:
            return LLMToolAuthorization(
                allowed=False,
                decision=DENIED,
                reason=f"Tool {tool_name!r} is not registered.",
            )
        except DisabledToolError:
            return LLMToolAuthorization(
                allowed=False,
                decision=DENIED,
                reason=f"Tool {tool_name!r} is disabled and cannot be invoked.",
            )

        # A plan that failed Commit #2/#3 validation is never authorized --
        # authorization does not rescue an invalid call.
        if plan.status != READY:
            return LLMToolAuthorization(
                allowed=False,
                decision=DENIED,
                reason=f"Plan {plan.plan_id!r} is {plan.status}, not {READY}.",
            )

        if self._invocation_service is not None and not self._invocation_service.validate(
            plan.plan_id
        ):
            return LLMToolAuthorization(
                allowed=False,
                decision=DENIED,
                reason=f"Plan {plan.plan_id!r} is no longer valid.",
            )

        with self._lock:
            applicable = self._applicable(tool_name, identities, plan.arguments)

        # Rule: an explicit deny overrides any allow, regardless of how
        # specific or how recent the competing allow is.
        denials = [policy for policy in applicable if not policy.allowed]
        if denials:
            policy = denials[0]
            return LLMToolAuthorization(
                allowed=False,
                decision=DENIED,
                reason=(
                    f"Policy {policy.policy_id!r} explicitly denies subject "
                    f"{policy.subject!r} on tool {tool_name!r}."
                ),
                policy_id=policy.policy_id,
            )

        allowances = [policy for policy in applicable if policy.allowed]
        if allowances:
            # A subject-specific allow is preferred over a tool-wide default
            # purely so the reported policy_id is the most meaningful one --
            # either way the answer is allow.
            policy = next(
                (p for p in allowances if p.subject != ANY_SUBJECT),
                allowances[0],
            )
            conditional = bool(policy.conditions)
            return LLMToolAuthorization(
                allowed=True,
                decision=CONDITIONAL if conditional else AUTHORIZED,
                reason=(
                    f"Policy {policy.policy_id!r} allows subject {policy.subject!r} "
                    f"on tool {tool_name!r}"
                    + (
                        f", conditions {policy.conditions!r} met."
                        if conditional
                        else "."
                    )
                ),
                policy_id=policy.policy_id,
            )

        return LLMToolAuthorization(
            allowed=False,
            decision=DENIED,
            reason=(
                f"No policy grants {sorted(identities)!r} invocation of tool "
                f"{tool_name!r}: denied by default."
            ),
        )
