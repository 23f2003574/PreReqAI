import re

# The richer six-pattern secret/credential set already used across this
# project: backend.llm.project_context, backend.llm.context_provenance,
# backend.llm.tool_execution, backend.llm.tool_results,
# backend.llm.tool_audit, backend.api_recommendation_export, and
# backend.transformation_audit all define this exact tuple locally --
# there is no shared util module in this repo, so every one of them
# duplicates it. It is the single most complete secret-pattern set
# already in use here (it also covers bearer tokens, unquoted credential
# assignments, and raw hex/base64-looking values that the narrower
# three-pattern set in backend.api_security_review-style modules does
# not), so it is the one made canonical here rather than inventing a new
# one. Commit #1's LLMInputSecurityService and Commit #2's
# LLMOutputSecurityService now redact through this service instead of
# keeping their own local copy.
_SECRET_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9_-]{10,}"), "sk- style API key"),
    (re.compile(r"AKIA[A-Z0-9]{12,}"), "AWS access key"),
    (re.compile(r"(?i)bearer\s+\S+"), "bearer token"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"), "credential assignment"),
    (re.compile(r"^[A-Fa-f0-9]{32,}$"), "hex-encoded secret"),
    (re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"), "base64-encoded secret"),
)

REDACTED = "[REDACTED]"


def _iter_strings(value, prefix: str = ""):
    """Yield (location, string) for every string reachable inside `value`.

    Same dotted/bracketed path convention ("a.b", "a[0]") already used by
    backend.code_patch_security_review and backend.api_security_review to
    make a finding traceable to an exact location. A bare string is
    reported at location "$".
    """
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from _iter_strings(sub, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            yield from _iter_strings(sub, f"{prefix}[{index}]")
    elif isinstance(value, str):
        yield prefix or "$", value


class LLMSecretRedactionService:
    """Detects and redacts secrets/credentials in any LLM-bound or
    LLM-generated value, using this project's own already-established
    secret-pattern set (_SECRET_PATTERNS) rather than a new scanner.

    detect()/redact()/contains_secret() all walk arbitrary Python values
    -- a bare string, or a dict/list/tuple such as a tool-call argument
    payload or a parsed JSON response -- recursively, so a secret nested
    inside structured data is found without disturbing anything else in
    that structure: redact() only ever replaces the matching span of a
    string, leaving dict keys, non-secret strings, and non-string values
    exactly as given. Both are pure functions of their input -- the same
    value always produces the same result (deterministic), and a value
    that has already been redacted contains no secret pattern itself, so
    redacting or detecting on it again is a no-op.
    """

    @staticmethod
    def _redact_string(text: str) -> str:
        redacted = text
        for pattern, _description in _SECRET_PATTERNS:
            redacted = pattern.sub(REDACTED, redacted)
        return redacted

    def redact(self, value):
        """A copy of `value` with every matched secret span replaced.

        dicts and lists/tuples are reconstructed with their own type and
        keys preserved; only string content is ever rewritten.
        """
        if isinstance(value, str):
            return self._redact_string(value)
        if isinstance(value, dict):
            return {key: self.redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        return value

    def detect(self, value) -> list:
        """Every location in `value` where a known secret pattern matched.

        Returns a list of {"location", "pattern"} dicts: `location` is a
        dotted/bracketed path ("$" for a bare string), `pattern` is the
        matched pattern's human-readable description. The secret value
        itself is never included in the result.
        """
        found = []
        for location, text in _iter_strings(value):
            for pattern, description in _SECRET_PATTERNS:
                if pattern.search(text):
                    found.append({"location": location, "pattern": description})
        return found

    def contains_secret(self, value) -> bool:
        """Whether `value` contains any known secret pattern anywhere.

        Recurses into dict keys as well as values -- the same convention
        backend.llm.project_context's own _contains_secret() already
        uses -- so a secret-looking key is caught too, not only a
        secret-looking value.
        """
        if isinstance(value, str):
            return any(pattern.search(value) for pattern, _ in _SECRET_PATTERNS)
        if isinstance(value, dict):
            return any(
                self.contains_secret(key) or self.contains_secret(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(self.contains_secret(item) for item in value)
        return False
