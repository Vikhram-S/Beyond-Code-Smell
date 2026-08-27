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
