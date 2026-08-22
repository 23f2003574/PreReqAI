import dataclasses
import string

from .models import LLMPromptTemplate


class InvalidTemplateError(ValueError):
    """Raised when a template's declared variables don't match its content."""


class MissingVariableError(ValueError):
    """Raised when render() is called without a value for a declared variable."""


class DisabledTemplateError(Exception):
    """Raised when render() is called on a version that is not active."""


class UnknownTemplateError(KeyError):
    """Raised when a template_id or template name has not been registered."""


class LLMPromptTemplateService:
    """Registers and renders reusable, versioned prompt templates.

    Each register() call for a given `name` creates a new immutable version.
    The first version of a name is active on creation; later versions start
    disabled until activate() promotes them, at which point any other active
    version of the same name is deactivated -- one active version per name.
    """

    def __init__(self):
        self._templates = {}
        self._versions_by_name = {}

    @staticmethod
    def _referenced_variables(template: str) -> set:
        names = set()
        for _, field_name, _, _ in string.Formatter().parse(template):
            if not field_name:
                continue
            base = field_name.split(".")[0].split("[")[0]
            if base:
                names.add(base)
        return names

    def register(self, name: str, template: str, variables) -> LLMPromptTemplate:
        if not name or not isinstance(name, str):
            raise InvalidTemplateError("name is required")

        if not template or not isinstance(template, str):
            raise InvalidTemplateError("template is required")

        declared = tuple(variables or [])
        referenced = self._referenced_variables(template)
        undeclared = sorted(referenced - set(declared))
        if undeclared:
            raise InvalidTemplateError(
                f"template references undeclared variable(s): {undeclared}"
            )

        existing_ids = self._versions_by_name.setdefault(name, [])
        version = len(existing_ids) + 1
        template_id = f"{name}:v{version}"

        prompt_template = LLMPromptTemplate(
            template_id=template_id,
            name=name,
            version=version,
            template=template,
            variables=declared,
            enabled=(version == 1),
        )

        self._templates[template_id] = prompt_template
        existing_ids.append(template_id)

        return prompt_template

    def _get(self, template_id: str) -> LLMPromptTemplate:
        try:
            return self._templates[template_id]
        except KeyError:
            raise UnknownTemplateError(template_id)

    def render(self, template_id: str, values: dict) -> str:
        template = self._get(template_id)

        if not template.enabled:
            raise DisabledTemplateError(
                f"template {template_id!r} is disabled and cannot render"
            )

        missing = [name for name in template.variables if name not in values]
        if missing:
            raise MissingVariableError(
                f"missing required variable(s) for template {template_id!r}: {missing}"
            )

        return template.template.format(**values)

    def versions(self, name: str) -> list:
        try:
            ids = self._versions_by_name[name]
        except KeyError:
            raise UnknownTemplateError(name)
        return [self._templates[template_id] for template_id in ids]

    def activate(self, template_id: str) -> LLMPromptTemplate:
        template = self._get(template_id)

        for other_id in self._versions_by_name[template.name]:
            if other_id == template_id:
                continue
            other = self._templates[other_id]
            if other.enabled:
                self._templates[other_id] = dataclasses.replace(other, enabled=False)

        activated = dataclasses.replace(template, enabled=True)
        self._templates[template_id] = activated
        return activated
