"""A stand-in for Google's `google.genai` package, used only by the browser tests: it answers like a model that cites the first excerpt it was given, so the real server's
Gemini tutor, grounding checks and page can be exercised in a browser without a key or a network."""
import json
from types import SimpleNamespace


class _Models:
    def generate_content(self, model, contents, config):
        data = json.loads(contents)
        first = data["paper_excerpts"][0]
        return SimpleNamespace(text=json.dumps({"answer": "The paper describes it in the passage it cites.", "citations": [{"passage_id": first["passage_id"], "quote": first["text"][:50]}],
                                                "supporting_concepts": [], "suggested_followups": [], "confidence": 0.7}))


class Client:
    def __init__(self, api_key=None, http_options=None):
        self.models = _Models()
