import json

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import (
    InvalidNotebookError,
    LLMNotebookAnalysisService,
    MalformedAnalysisError,
    UnknownAnalysisError,
)


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_service(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider(script)},
    )

    return LLMNotebookAnalysisService(orchestration_service, context_service)


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "import numpy as np\nimport pandas as pd"},
        {"cell_type": "markdown", "source": "## Helper"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}

WELL_FORMED_RESPONSE = json.dumps(
    {
        "imports": ["import numpy as np", "import pandas as pd"],
        "functions": [{"name": "add", "cell_index": 3}],
        "dependencies": ["numpy", "pandas"],
    }
)


def test_cell_extraction_preserves_order_and_type():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    analysis = service.analyze(NOTEBOOK)

    assert [c.index for c in analysis.cells] == [0, 1, 2, 3]
    assert [c.cell_type for c in analysis.cells] == ["markdown", "code", "markdown", "code"]
    assert analysis.cells[1].source == "import numpy as np\nimport pandas as pd"

    summary = service.summary(analysis.analysis_id)
    assert summary["cell_count"] == 4
    assert summary["code_cell_count"] == 2
    assert summary["markdown_cell_count"] == 2


def test_function_detection():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    analysis = service.analyze(NOTEBOOK)

    assert analysis.functions == [{"name": "add", "cell_index": 3}]
    assert service.functions(analysis.analysis_id) == [{"name": "add", "cell_index": 3}]


def test_import_detection():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    analysis = service.analyze(NOTEBOOK)

    assert analysis.imports == ["import numpy as np", "import pandas as pd"]


def test_dependency_detection():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    analysis = service.analyze(NOTEBOOK)

    assert analysis.dependencies == ["numpy", "pandas"]
    assert service.dependencies(analysis.analysis_id) == ["numpy", "pandas"]


@pytest.mark.parametrize(
    "raw_content",
    [
        "here is your analysis: numpy and pandas are imported",
        json.dumps({"imports": ["import numpy"], "functions": []}),
        json.dumps({"imports": "import numpy", "functions": [], "dependencies": []}),
        json.dumps({"imports": [], "functions": [{"cell_index": 1}], "dependencies": []}),
        json.dumps({"imports": [], "functions": [{"name": "add", "cell_index": "3"}], "dependencies": []}),
    ],
)
def test_malformed_response_is_rejected(raw_content):
    service = build_service([make_response(raw_content)])

    with pytest.raises(MalformedAnalysisError):
        service.analyze(NOTEBOOK)


def test_malformed_notebook_input_is_rejected():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    with pytest.raises(InvalidNotebookError):
        service.analyze({"notebook_id": "nb-2", "cells": []})

    with pytest.raises(InvalidNotebookError):
        service.analyze({"notebook_id": "nb-3", "cells": [{"cell_type": "sql", "source": "x"}]})


def test_deterministic_structure():
    service = build_service([make_response(WELL_FORMED_RESPONSE)])

    analysis = service.analyze(NOTEBOOK)

    summary_a = service.summary(analysis.analysis_id)
    summary_b = service.summary(analysis.analysis_id)
    assert summary_a == summary_b

    assert service.functions(analysis.analysis_id) == service.functions(analysis.analysis_id)
    assert service.dependencies(analysis.analysis_id) == service.dependencies(analysis.analysis_id)

    with pytest.raises(UnknownAnalysisError):
        service.summary("does-not-exist")
