import json

from backend.input_schema import LLMInputSchema
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import DEFAULT, REQUIRED, TYPE, LLMInputValidation

_NUMERIC_CONSTRAINTS = {"min", "max"}


class MalformedValidationResponseError(ValueError):
    """Raised when the LLM's validation-message response isn't well-formed."""


class UnknownValidationRulesError(KeyError):
    """Raised when validate()/violations() is called before infer() for a candidate_id."""


class ValidationFailedError(ValueError):
    """Raised by validate() when a payload violates one or more inferred rules.

    Carries the full list of violated LLMInputValidation rules so a caller
    can report every problem, not just the first -- the payload must never
    be executed once this is raised.
    """

    def __init__(self, candidate_id: str, violations: list):
        self.candidate_id = candidate_id
        self.violations = violations
        summary = "; ".join(f"{v.field} ({v.rule}): {v.message}" for v in violations)
        super().__init__(f"payload for candidate_id {candidate_id!r} failed validation: {summary}")


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API documentation assistant. Given a candidate's inferred "
    "input schema and the list of validation rules generated from it, write "
    "one short, human-readable error message per rule -- the message shown "
    "to a caller when that specific rule is violated. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"messages\": {\"<field>:<rule>\": \"<message>\", ...}}, with exactly "
    "one entry for every rule key given."
)


def _matches_type(value, type_name: str) -> bool:
    if isinstance(value, bool):
        return type_name == "bool"
    if type_name == "int":
        return isinstance(value, int)
    if type_name == "float":
        return isinstance(value, (int, float))
    if type_name == "str":
        return isinstance(value, str)
    if type_name == "list":
        return isinstance(value, list)
    if type_name == "dict":
        return isinstance(value, dict)
    if type_name == "tuple":
        return isinstance(value, tuple)
    return False


class LLMInputValidationService:
    """Generates and applies validation rules for an inferred input schema (Commit #4).

    infer() takes an LLMInputSchema directly and deterministically derives one
    rule per required field, per field type, per detected default, and per
    constraint -- the LLM (via the same orchestration pipeline used
    throughout) is only asked for a human-readable message per rule, never
    for the rule's structure or value. validate()/violations() are then pure
    deterministic checks against those stored rules; validate() raises
    rather than letting an invalid payload proceed.
    """

    def __init__(self, orchestration_service, context_service, route_request: LLMRouteRequest = None):
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="input_validation_messages", required_capabilities=["chat"]
        )
        self._rules_by_candidate = {}
        self._request_counter = 0

    @staticmethod
    def _draft_rules(schema: LLMInputSchema) -> list:
        drafted = []
        for field in schema.fields:
            if field in schema.required:
                drafted.append((field, REQUIRED, None))

            drafted.append((field, TYPE, schema.types[field]))

            if field in schema.defaults:
                drafted.append((field, DEFAULT, schema.defaults[field]))

            for constraint_key, constraint_value in schema.constraints.get(field, {}).items():
                drafted.append((field, constraint_key, constraint_value))

        return drafted

    @staticmethod
    def _build_prompt(schema: LLMInputSchema, keys: list) -> str:
        payload = {
            "candidate_id": schema.candidate_id,
            "types": schema.types,
            "required": schema.required,
            "defaults": schema.defaults,
            "constraints": schema.constraints,
            "rules": keys,
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, keys: list) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedValidationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("messages"), dict):
            raise MalformedValidationResponseError(
                "LLM response must be a JSON object with a 'messages' object"
            )

        messages = parsed["messages"]
        for key in keys:
            if key not in messages:
                raise MalformedValidationResponseError(f"LLM response is missing a message for {key!r}")
            if not isinstance(messages[key], str) or not messages[key].strip():
                raise MalformedValidationResponseError(f"message for {key!r} must be a non-empty string")

        return messages

    def infer(self, schema: LLMInputSchema) -> list:
        candidate_id = schema.candidate_id
        drafted = self._draft_rules(schema)
        keys = [f"{field}:{rule}" for field, rule, _ in drafted]

        self._request_counter += 1
        request_id = f"input-validation-{candidate_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(schema, keys), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedValidationResponseError(f"LLM request failed: {decision.reason}")

        messages = self._parse_response(response.content, keys)

        rules = [
            LLMInputValidation(
                candidate_id=candidate_id,
                field=field,
                rule=rule,
                value=value,
                message=messages[f"{field}:{rule}"],
            )
            for field, rule, value in drafted
        ]

        self._rules_by_candidate[candidate_id] = rules
        return rules

    def _get_rules(self, candidate_id: str) -> list:
        try:
            return self._rules_by_candidate[candidate_id]
        except KeyError:
            raise UnknownValidationRulesError(candidate_id)

    def violations(self, candidate_id: str, payload: dict) -> list:
        rules = self._get_rules(candidate_id)
        found = []

        for rule in rules:
            if rule.rule == REQUIRED:
                if rule.field not in payload:
                    found.append(rule)
                continue

            if rule.rule == DEFAULT:
                continue

            if rule.field not in payload:
                continue

            value = payload[rule.field]

            if rule.rule == TYPE:
                if not _matches_type(value, rule.value):
                    found.append(rule)
                continue

            if rule.rule in _NUMERIC_CONSTRAINTS:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    found.append(rule)
                elif rule.rule == "min" and value < rule.value:
                    found.append(rule)
                elif rule.rule == "max" and value > rule.value:
                    found.append(rule)
                continue

            if rule.rule == "enum":
                if isinstance(rule.value, (list, tuple)) and value not in rule.value:
                    found.append(rule)
                continue

        return found

    def validate(self, candidate_id: str, payload: dict) -> bool:
        found = self.violations(candidate_id, payload)
        if found:
            raise ValidationFailedError(candidate_id, found)
        return True
