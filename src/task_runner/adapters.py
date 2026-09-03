import os
import time
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from src.utils.logger import logger
from src.cost_tracker.tracker import CostTracker

class BaseLLMAdapter(ABC):
    """Abstract interface for LLM providers."""

    def __init__(self, model_name: str, cost_tracker: CostTracker):
        self.model_name = model_name
        self.cost_tracker = cost_tracker

    @abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generates response string, handling caching and token cost logging."""
        pass


class MockLLMAdapter(BaseLLMAdapter):
    """
    Deterministic Mock LLM Adapter for dry-runs and zero-cost unit/integration testing.
    Simulates a 3-session agent trajectory introducing structural drift.
    """

    def __init__(self, model_name: str, cost_tracker: CostTracker):
        super().__init__(model_name or "mock-model", cost_tracker)
        self.session_counter = 0

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        self.session_counter += 1
        
        # Check cache first
        is_cached, text, _ = self.cost_tracker.get_cached_response(
            self.model_name, system_prompt, user_prompt
        )
        if is_cached:
            return text

        # Simulated sequential responses with code edits
        if "Session 1" in user_prompt or self.session_counter == 1:
            response = (
                "```python\n"
                "# File: domain/utils.py\n"
                "def domain_helper():\n"
                "    return 'domain_ok'\n"
                "```"
            )
        elif "Session 2" in user_prompt or self.session_counter == 2:
            # Introduces illegal edge: domain -> adapters
            response = (
                "```python\n"
                "# File: domain/entity.py\n"
                "from adapters.db import DBAdapter\n\n"
                "class User:\n"
                "    def __init__(self, name):\n"
                "        self.name = name\n"
                "        self.db = DBAdapter()\n"
                "```"
            )
        else:
            # Introduces illegal edge: api -> adapters
            response = (
                "```python\n"
                "# File: api/routes.py\n"
                "from adapters.db import DBAdapter\n\n"
                "def route():\n"
                "    return DBAdapter()\n"
                "```"
            )

        # Log & cache zero-cost mock tokens
        self.cost_tracker.log_and_cache(
            model=self.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response,
            input_tokens=150,
            output_tokens=80
        )

        return response


class ClaudeAPIAdapter(BaseLLMAdapter):
    """
    Claude API Adapter using Anthropic SDK or fallback HTTP API wrapper.
    """

    def __init__(self, model_name: str, cost_tracker: CostTracker, api_key: str | None = None):
        super().__init__(model_name or "claude-3-5-sonnet-20241022", cost_tracker)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        # Claude is retained only so old unit tests import; live runs use GeminiAPIAdapter.

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        # Check disk cache
        is_cached, text, _ = self.cost_tracker.get_cached_response(
            self.model_name, system_prompt, user_prompt
        )
        if is_cached:
            return text

        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY set! Falling back to MockLLMAdapter logic.")
            mock = MockLLMAdapter(self.model_name, self.cost_tracker)
            return mock.generate_response(system_prompt, user_prompt)

        # Execute API call with retries
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            res_text = response.content[0].text
            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens

            self.cost_tracker.log_and_cache(
                model=self.model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text=res_text,
                input_tokens=in_tok,
                output_tokens=out_tok
            )
            return res_text
        except Exception as e:
            logger.error(f"Claude API Call Error: {e}")
            raise e


class QuotaExceededError(Exception):
    """Raised when the configured Gemini free-tier request quota is exhausted."""


class GeminiAPIAdapter(BaseLLMAdapter):
    """
    Google Gemini generateContent API (remote only). No local models.
    """

    def __init__(
        self,
        model_name: str,
        cost_tracker: CostTracker,
        api_key: str | None = None,
        max_retries: int = 12,
        rpm_sleep_seconds: float = 8.0,
    ):
        super().__init__(model_name or "gemini-3.6-flash", cost_tracker)
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.max_retries = max_retries
        self.rpm_sleep_seconds = rpm_sleep_seconds

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        is_cached, text, _ = self.cost_tracker.get_cached_response(
            self.model_name, system_prompt, user_prompt
        )
        if is_cached:
            return text

        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY missing. Paste it into PASTE_GOOGLE_API_KEY_HERE.txt and re-run. "
                "Refusing to fall back to MockLLM — that would fabricate paper numbers."
            )

        import json
        import urllib.error
        import urllib.request

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 8192,
            },
        }
        body = json.dumps(payload).encode("utf-8")

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=180) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))

                res_text = self._extract_text(raw)
                usage = raw.get("usageMetadata", {})
                in_tok = int(usage.get("promptTokenCount", 0) or 0)
                out_tok = int(usage.get("candidatesTokenCount", 0) or 0)

                self.cost_tracker.log_and_cache(
                    model=self.model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_text=res_text,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                )
                time.sleep(self.rpm_sleep_seconds)
                return res_text
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                last_err = e
                wait = min(180, 15 * attempt)
                if e.code in (429, 500, 503):
                    logger.warning(
                        f"Gemini HTTP {e.code} (attempt {attempt}/{self.max_retries}). "
                        f"Sleeping {wait}s. Body: {err_body[:300]}"
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"Gemini HTTP {e.code}: {err_body[:800]}")
                raise RuntimeError(f"Gemini HTTP {e.code}: {err_body[:400]}") from e
            except Exception as e:
                last_err = e
                logger.warning(f"Gemini call failed (attempt {attempt}): {e}")
                time.sleep(min(180, 15 * attempt))

        raise RuntimeError(f"Gemini API failed after {self.max_retries} retries: {last_err}")

    @staticmethod
    def _extract_text(raw: dict) -> str:
        cands = raw.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini returned no candidates: {raw}")
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        joined = "\n".join(t for t in texts if t)
        if not joined.strip():
            raise RuntimeError(f"Gemini returned empty text: {raw}")
        return joined
