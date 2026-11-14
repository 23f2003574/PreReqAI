"""Gemini through Google's `google-genai` SDK (not the deprecated `google-generativeai`). The package is optional and imported only when Gemini is used;
the credential is read from GEMINI_API_KEY (or passed in), is handed to the SDK and is never logged, stored or put in a message."""
import importlib
import os

from .tutor_provider import ProviderError, TutorProvider


class GeminiTutorProvider(TutorProvider):
    name = "gemini"

    def __init__(self, model, timeout_seconds, max_output_tokens, api_key=None, client=None):
        self.model, self.timeout_seconds, self.max_output_tokens = model, timeout_seconds, max_output_tokens
        self._api_key, self._client = api_key, client  # a client can be injected (tests use a fake: no network, no key)

    def _get_client(self):
        if self._client is None:
            key = (self._api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
            if not key:
                raise ProviderError("not_configured", "GEMINI_API_KEY is not set.")
            try:  # an optional package, so it is imported by name when first needed (and is deliberately not in requirements.txt)
                genai = importlib.import_module("google.genai")
            except ImportError as error:
                raise ProviderError("not_configured", "the google-genai package is not installed (pip install google-genai).") from error
            self._client = genai.Client(api_key=key, http_options={"timeout": int(self.timeout_seconds * 1000)})  # the SDK's timeout is in milliseconds
        return self._client

    def generate(self, system_prompt, user_prompt):
        client = self._get_client()
        try:
            response = client.models.generate_content(
                model=self.model, contents=user_prompt,
                config={"system_instruction": system_prompt, "max_output_tokens": self.max_output_tokens, "temperature": 0.2,
                        "response_mime_type": "application/json"},  # no tools, no function calling
            )
            text = getattr(response, "text", None)
        except ProviderError:
            raise
        except Exception as error:  # the SDK raises its own types; only the kind and status are kept, never the raw message
            raise self._classify(error) from None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("bad_response", "Gemini returned no text (the answer may have been blocked or cut off).")
        return text

    @staticmethod
    def _classify(error):
        code = getattr(error, "code", None) or getattr(error, "status_code", None)
        name = type(error).__name__
        if code == 429 or "ResourceExhausted" in name or "RateLimit" in name:
            return ProviderError("rate_limit", "Gemini is rate limiting requests (HTTP 429); try again later.")
        if code in (401, 403) or "Permission" in name or "Unauthenticated" in name:
            return ProviderError("auth", f"Gemini refused the credential (HTTP {code or 'auth'}); check GEMINI_API_KEY and its access.")
        if code in (408, 504) or isinstance(error, TimeoutError) or "Timeout" in name or "DeadlineExceeded" in name:
            return ProviderError("timeout", "Gemini did not answer in time.")
        return ProviderError("provider", f"Gemini failed ({name}{f', HTTP {code}' if isinstance(code, int) else ''}).")
