import json
import re

from backend.compilation_execution import COMPILER_STATUSES, COMPILER_SUCCEEDED, CompilerJobResult
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import (
    CATEGORIES,
    CORRECTNESS,
    CRITICAL,
    SECURITY,
    SEVERITIES,
    APPROVED,
    INFO,
    REJECTED,
    LLMGeneratedCodeReview,
)

_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}

_DANGEROUS_PATTERNS = (
    ("eval(", "eval() can execute arbitrary code"),
    ("exec(", "exec() can execute arbitrary code"),
    ("os.system(", "os.system() can execute arbitrary shell commands"),
    ("subprocess.", "subprocess usage can execute arbitrary shell commands"),
    ("pickle.loads(", "pickle.loads() can execute arbitrary code from untrusted input"),
    ("__import__(", "dynamic __import__ can load arbitrary modules"),
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]"),
)

GENERATED_CODE_REVIEW_SYSTEM_PROMPT = (
    "You are an API generated-code reviewer performing a final check on "
    "what the existing deterministic compiler actually produced. You are "
    "given the compiler job's id and its own generated `output` object "
    "verbatim. Identify any additional issues beyond what deterministic "
    "checks already caught -- incorrect or inconsistent generated "
    "structure, remaining security concerns, quality/maintainability "
    "problems, or anything incompatible with how this output would be "
    "used. Respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"findings\": [...], \"confidence\": 0.0}. "
    "'findings' may be an empty list if the output looks sound. Each "
    "finding is an object with: 'category' (one of CORRECTNESS, SECURITY, "
    "QUALITY, COMPATIBILITY), 'location' (the exact job id or a dotted/"
    "bracketed key path into `output` this finding is about -- taken only "
    "from the paths listed in 'valid_locations', never invented), "
    "'severity' (one of INFO, WARNING, ERROR, CRITICAL), and 'message' (a "
    "specific, concrete reason grounded in the given output -- never a "
    "vague or unsupported claim). 'confidence' is a number between 0.0 and "
    "1.0 for the review as a whole. This is a read-only review -- never "
    "propose editing the generated output, the compiler, or anything "
    "upstream of it."
)


class InvalidGeneratedOutputError(ValueError):
    """Raised when generated_output doesn't satisfy the compiler's own CompilerJobResult contract."""


class MalformedGeneratedCodeReviewResponseError(ValueError):
    """Raised when the LLM's generated-code-review response isn't well-formed."""


class UnknownReviewError(KeyError):
    """Raised when findings()/blocking() is called for a review_id that was never produced."""


class UnknownGeneratedOutputError(KeyError):
    """Raised when get_generated_output() is called for a job_id that was never reviewed."""


def _validate_generated_output(generated_output) -> None:
    if not isinstance(generated_output, CompilerJobResult):
        raise InvalidGeneratedOutputError(
            f"generated_output must be a CompilerJobResult, got {type(generated_output).__name__}"
        )
    if not isinstance(generated_output.job_id, str) or not generated_output.job_id.strip():
        raise InvalidGeneratedOutputError("generated_output.job_id must be a non-empty string")
    if generated_output.status not in COMPILER_STATUSES:
        raise InvalidGeneratedOutputError(f"generated_output.status {generated_output.status!r} is not valid")
    if not isinstance(generated_output.output, dict):
        raise InvalidGeneratedOutputError("generated_output.output must be a dict")


def _make_finding(category: str, location: str, severity: str, message: str) -> dict:
    return {"category": category, "location": location, "severity": severity, "message": message}


def _walk(value, prefix: str, locations: set, strings: list) -> None:
    if isinstance(value, dict):
        for key, sub in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            locations.add(path)
            _walk(sub, path, locations, strings)
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            path = f"{prefix}[{index}]"
            locations.add(path)
            _walk(sub, path, locations, strings)
    elif isinstance(value, str):
        strings.append((prefix, value))


def _inspect_output(output: dict):
    locations = set()
    strings = []
    _walk(output, "", locations, strings)
    return locations, strings


def _secrets_findings(strings: list) -> list:
    findings = []
    for location, value in strings:
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(value)
            if match:
                findings.append(
                    _make_finding(
                        SECURITY,
                        location,
                        CRITICAL,
                        f"generated output appears to contain a hardcoded credential: {match.group(0)[:40]!r}",
                    )
                )
    return findings


def _code_findings(strings: list) -> list:
    findings = []
    for location, value in strings:
        for pattern, message in _DANGEROUS_PATTERNS:
            if pattern in value:
                findings.append(
                    _make_finding(
                        SECURITY,
                        location,
                        CRITICAL,
                        f"generated output uses {pattern.rstrip('(').rstrip('.')}: {message}",
                    )
                )
    return findings


class LLMGeneratedCodeReviewService:
    """Reviews what the existing deterministic compiler (backend.compilation_execution)
    actually produced for one job, before that generated output is trusted further.

    Reuses backend.compilation_execution's own CompilerJobResult representation
    and COMPILER_STATUSES as the sole shape of "generated output" -- this
    service never redefines or reinterprets what the compiler returns. A
    non-SUCCEEDED compiler status or an empty `output` is itself a
    deterministic CRITICAL CORRECTNESS finding (there is no real generated
    code to review, so the LLM is not consulted); otherwise a static
    pattern-scan of the output's own string values covers SECURITY
    (hardcoded secrets, dangerous constructs) the same way
    backend.api_security_review does, and the LLM (same orchestration
    pipeline used throughout) is asked for CORRECTNESS/SECURITY/QUALITY/
    COMPATIBILITY issues beyond those. Every finding -- deterministic or
    LLM-proposed -- must cite a location that is either the job's own id or
    a real key path inside its own `output` dict. review() never mutates
    the CompilerJobResult, the compiler, or anything upstream of it.
    """

    def __init__(self, orchestration_service, context_service, route_request: LLMRouteRequest = None):
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="generated_code_review", required_capabilities=["chat"]
        )
        self._reviews = {}
        self._generated_output_by_job = {}
        self._request_counter = 0
        self._review_counter = 0

    @staticmethod
    def _aggregate_severity(findings: list) -> str:
        if not findings:
            return INFO
        return max((finding["severity"] for finding in findings), key=lambda severity: _SEVERITY_RANK[severity])

    def _finalize(self, job_id: str, findings: list, confidence: float) -> LLMGeneratedCodeReview:
        status = REJECTED if any(finding["severity"] == CRITICAL for finding in findings) else APPROVED

        self._review_counter += 1
        review = LLMGeneratedCodeReview(
            review_id=f"generated-code-review-{job_id}-{self._review_counter}",
            target=job_id,
            findings=findings,
            severity=self._aggregate_severity(findings),
            confidence=confidence,
            status=status,
        )
        self._reviews[review.review_id] = review
        return review

    @staticmethod
    def _build_prompt(job_id: str, output: dict, valid_locations: set) -> str:
        payload = {"job_id": job_id, "output": output, "valid_locations": sorted(valid_locations)}
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_locations: set):
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedGeneratedCodeReviewResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedGeneratedCodeReviewResponseError(
                "LLM response must be a JSON object with a 'findings' list"
            )

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedGeneratedCodeReviewResponseError("each finding must be an object")
            for key in ("category", "location", "severity", "message"):
                if key not in finding:
                    raise MalformedGeneratedCodeReviewResponseError(f"finding missing required field {key!r}")
            if finding["category"] not in CATEGORIES:
                raise MalformedGeneratedCodeReviewResponseError(
                    f"finding 'category' must be one of {sorted(CATEGORIES)}"
                )
            if finding["severity"] not in SEVERITIES:
                raise MalformedGeneratedCodeReviewResponseError(
                    f"finding 'severity' must be one of {sorted(SEVERITIES)}"
                )
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedGeneratedCodeReviewResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["location"], str) or finding["location"] not in valid_locations:
                raise MalformedGeneratedCodeReviewResponseError(
                    f"finding location {finding.get('location')!r} does not reference real generated output"
                )

        if "confidence" not in parsed:
            raise MalformedGeneratedCodeReviewResponseError("LLM response missing required field 'confidence'")
        confidence = parsed["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise MalformedGeneratedCodeReviewResponseError("'confidence' must be a number")
        if not (0.0 <= float(confidence) <= 1.0):
            raise MalformedGeneratedCodeReviewResponseError("'confidence' must be between 0.0 and 1.0")

        clean = [
            _make_finding(finding["category"], finding["location"], finding["severity"], finding["message"])
            for finding in findings
        ]
        return clean, float(confidence)

    def review(self, generated_output: CompilerJobResult) -> LLMGeneratedCodeReview:
        _validate_generated_output(generated_output)
        job_id = generated_output.job_id
        self._generated_output_by_job[job_id] = generated_output

        if generated_output.status != COMPILER_SUCCEEDED:
            findings = [
                _make_finding(
                    CORRECTNESS,
                    job_id,
                    CRITICAL,
                    f"compiler execution status is {generated_output.status!r}; there is no successfully "
                    "generated code to review",
                )
            ]
            return self._finalize(job_id, findings, confidence=1.0)

        if not generated_output.output:
            findings = [_make_finding(CORRECTNESS, job_id, CRITICAL, "compiler produced no generated output")]
            return self._finalize(job_id, findings, confidence=1.0)

        locations, strings = _inspect_output(generated_output.output)
        findings = []
        findings.extend(_secrets_findings(strings))
        findings.extend(_code_findings(strings))

        valid_locations = locations | {job_id}

        self._request_counter += 1
        request_id = f"generated-code-review-{job_id}-{self._request_counter}"

        self._context_service.create(request_id, system=GENERATED_CODE_REVIEW_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(job_id, generated_output.output, valid_locations),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedGeneratedCodeReviewResponseError(f"LLM request failed: {decision.reason}")

        llm_findings, confidence = self._parse_response(response.content, valid_locations)
        findings.extend(llm_findings)

        return self._finalize(job_id, findings, confidence)

    def _get(self, review_id: str) -> LLMGeneratedCodeReview:
        try:
            return self._reviews[review_id]
        except KeyError:
            raise UnknownReviewError(review_id)

    def findings(self, review_id: str) -> list:
        return list(self._get(review_id).findings)

    def blocking(self, review_id: str) -> bool:
        return any(finding["severity"] == CRITICAL for finding in self.findings(review_id))

    def get(self, review_id: str) -> LLMGeneratedCodeReview:
        return self._get(review_id)

    def get_generated_output(self, job_id: str) -> CompilerJobResult:
        """The exact, live CompilerJobResult a prior review() call was given for
        this job -- the only real "generated code" this codebase has, so later
        commits can locate it without a new store or file format."""
        try:
            return self._generated_output_by_job[job_id]
        except KeyError:
            raise UnknownGeneratedOutputError(job_id)
