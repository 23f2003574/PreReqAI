import json
from datetime import datetime, timezone
from types import MappingProxyType

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import LLMInputSchemaService, UnknownSchemaError
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.output_schema import LLMOutputSchemaService, UnknownOutputSchemaError

from .models import ENDPOINT_METHODS, LLMCompilationPlan


class MissingSchemaError(ValueError):
    """Raised when a candidate has no fully-inferred input/output schema."""


class UnresolvableDependencyError(ValueError):
    """Raised when a dependency edge's node can no longer be resolved against the analysis."""


class EndpointCandidateError(ValueError):
    """Raised when an endpoint references a candidate not in the plan."""


class MalformedPlanError(ValueError):
    """Raised when the LLM's endpoint response isn't well-formed, or coverage is incomplete."""


class UnknownPlanError(KeyError):
    """Raised when looking up a plan_id that was never built."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API design assistant. Given a list of API candidates (each "
    "already has an id, function name, inputs, and outputs), assign each "
    "one a REST endpoint. Respond with ONLY a single JSON object -- no "
    "prose, no markdown fencing -- of the form {\"endpoints\": [...]}. There "
    "must be exactly one entry per candidate, each an object with: "
    "'candidate_id' (must exactly match one of the given candidate ids), "
    "'method' (one of GET, POST, PUT, PATCH, DELETE), and 'path' (a URL "
    "path starting with '/')."
)


class LLMCompilationPlanningService:
    """Combines already-validated analysis outputs into one immutable, compiler-ready plan.

    Reuses Commit #3's candidates, Commit #4/#5's schemas, and Commit #2's
    dependency graph as-is -- build() never re-derives or second-guesses
    them, it only checks that they're complete and consistent. The only new
    LLM call (via the same orchestration pipeline used throughout) assigns a
    REST endpoint to each candidate; everything else in the plan is a direct
    combination of prior commits' already-validated records.
    """

    def __init__(
        self,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        dependency_service: LLMNotebookDependencyService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._dependency_service = dependency_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="compilation_planning", required_capabilities=["chat"]
        )
        self._plans = {}
        self._request_counter = 0
        self._plan_counter = 0

    @staticmethod
    def _check_dependencies_resolvable(dependencies, analysis, notebook_id: str) -> None:
        valid_cells = {cell.index for cell in analysis.cells}
        valid_imports = set(range(len(analysis.imports)))
        valid_functions = {fn["name"] for fn in analysis.functions}
        prefix = f"{notebook_id}::"

        for dep in dependencies:
            for qualified in (dep.source, dep.target):
                if not qualified.startswith(prefix):
                    raise UnresolvableDependencyError(
                        f"dependency {dep.dependency_id!r} node {qualified!r} does not "
                        f"belong to notebook {notebook_id!r}"
                    )
                local_id = qualified[len(prefix):]
                kind, _, rest = local_id.partition(":")

                if kind == "cell":
                    if not rest.isdigit() or int(rest) not in valid_cells:
                        raise UnresolvableDependencyError(
                            f"dependency {dep.dependency_id!r} references a missing cell: {qualified!r}"
                        )
                elif kind == "import":
                    if not rest.isdigit() or int(rest) not in valid_imports:
                        raise UnresolvableDependencyError(
                            f"dependency {dep.dependency_id!r} references a missing import: {qualified!r}"
                        )
                elif kind == "function":
                    if rest not in valid_functions:
                        raise UnresolvableDependencyError(
                            f"dependency {dep.dependency_id!r} references a missing function: {qualified!r}"
                        )
                elif kind not in ("data", "model"):
                    raise UnresolvableDependencyError(
                        f"dependency {dep.dependency_id!r} has an unrecognized node: {qualified!r}"
                    )

    @staticmethod
    def _build_prompt(candidates) -> str:
        payload = {
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "function_name": candidate.function_name,
                    "inputs": candidate.inputs,
                    "outputs": candidate.outputs,
                }
                for candidate in candidates
            ]
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_endpoints(raw_content: str, candidate_ids: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedPlanError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("endpoints"), list):
            raise MalformedPlanError("LLM response must be a JSON object with an 'endpoints' list")

        endpoints = parsed["endpoints"]
        seen = set()
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                raise MalformedPlanError("each endpoint must be an object")

            for key in ("candidate_id", "method", "path"):
                if key not in endpoint:
                    raise MalformedPlanError(f"endpoint missing required field {key!r}")

            if endpoint["candidate_id"] not in candidate_ids:
                raise EndpointCandidateError(
                    f"endpoint references candidate_id {endpoint['candidate_id']!r}, "
                    "which is not part of this plan"
                )
            if endpoint["method"] not in ENDPOINT_METHODS:
                raise MalformedPlanError(
                    f"endpoint method {endpoint['method']!r} must be one of {sorted(ENDPOINT_METHODS)}"
                )
            if not isinstance(endpoint["path"], str) or not endpoint["path"].startswith("/"):
                raise MalformedPlanError("endpoint 'path' must be a string starting with '/'")

            seen.add(endpoint["candidate_id"])

        missing = candidate_ids - seen
        if missing:
            raise MalformedPlanError(f"response is missing endpoints for candidates: {sorted(missing)}")

        return endpoints

    def _collect_schemas(self, candidates) -> dict:
        schemas = {}
        for candidate in candidates:
            try:
                input_schema = self._input_schema_service.get(candidate.candidate_id)
                output_schema = self._output_schema_service.get(candidate.candidate_id)
            except (UnknownSchemaError, UnknownOutputSchemaError) as exc:
                raise MissingSchemaError(
                    f"candidate {candidate.candidate_id!r} has no fully-inferred input/output schema"
                ) from exc
            schemas[candidate.candidate_id] = {"input": input_schema, "output": output_schema}
        return schemas

    def build(self, notebook_id: str) -> LLMCompilationPlan:
        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        candidates = self._api_candidate_service.candidates(notebook_id)
        if not candidates:
            raise MissingSchemaError(f"no API candidates found for notebook_id {notebook_id!r}")

        schemas = self._collect_schemas(candidates)

        dependencies = tuple(self._dependency_service.dependencies(notebook_id))
        self._check_dependencies_resolvable(dependencies, analysis, notebook_id)

        candidate_ids = {candidate.candidate_id for candidate in candidates}

        self._request_counter += 1
        request_id = f"compilation-plan-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(candidates), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedPlanError(f"LLM request failed: {decision.reason}")

        raw_endpoints = self._parse_endpoints(response.content, candidate_ids)
        endpoints = tuple(
            {"candidate_id": e["candidate_id"], "method": e["method"], "path": e["path"]}
            for e in raw_endpoints
        )

        validations = {
            candidate.candidate_id: {
                "has_input_schema": True,
                "has_output_schema": True,
                "has_endpoint": any(e["candidate_id"] == candidate.candidate_id for e in endpoints),
            }
            for candidate in candidates
        }

        self._plan_counter += 1
        plan = LLMCompilationPlan(
            plan_id=f"plan-{notebook_id}-{self._plan_counter}",
            notebook_id=notebook_id,
            candidates=tuple(candidates),
            schemas=MappingProxyType(schemas),
            dependencies=dependencies,
            endpoints=endpoints,
            validations=MappingProxyType(validations),
            generated_at=datetime.now(timezone.utc),
        )
        self._plans[plan.plan_id] = plan
        return plan

    def _get(self, plan_id: str) -> LLMCompilationPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise UnknownPlanError(plan_id)

    def validate(self, plan_id: str) -> bool:
        plan = self._get(plan_id)
        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)

        current_candidate_ids = {
            candidate.candidate_id for candidate in self._api_candidate_service.candidates(plan.notebook_id)
        }
        plan_candidate_ids = {candidate.candidate_id for candidate in plan.candidates}
        if not plan_candidate_ids <= current_candidate_ids:
            raise MissingSchemaError(
                f"plan {plan_id!r} references a candidate that no longer exists"
            )

        self._collect_schemas(plan.candidates)
        self._check_dependencies_resolvable(plan.dependencies, analysis, plan.notebook_id)

        endpoint_candidate_ids = {endpoint["candidate_id"] for endpoint in plan.endpoints}
        unknown = endpoint_candidate_ids - plan_candidate_ids
        if unknown:
            raise EndpointCandidateError(
                f"plan {plan_id!r} has endpoints referencing unknown candidates: {sorted(unknown)}"
            )
        missing = plan_candidate_ids - endpoint_candidate_ids
        if missing:
            raise MalformedPlanError(f"plan {plan_id!r} is missing endpoints for candidates: {sorted(missing)}")

        return True

    def endpoints(self, plan_id: str) -> tuple:
        return self._get(plan_id).endpoints

    def dependencies(self, plan_id: str) -> tuple:
        return self._get(plan_id).dependencies
