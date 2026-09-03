import hashlib
import json
import time
from datetime import date
from pathlib import Path
from typing import Dict, Any, Tuple
from src.utils.logger import logger

class BudgetExceededError(Exception):
    """Raised when API spending exceeds configured maximum cost threshold."""
    pass


class QuotaExceededError(Exception):
    """Raised when free-tier request quota is exhausted."""
    pass

class CostTracker:
    """
    Logs API token counts, calculates costs, caches LLM calls to disk,
    and enforces hard budget limits.
    """

    def __init__(self, config: Dict[str, Any]):
        budget_cfg = config.get("budget", {})
        quota_cfg = config.get("quota", {})
        self.max_cost_usd = float(budget_cfg.get("max_cost_usd", 0.0))
        self.hard_stop = bool(budget_cfg.get("hard_stop_on_overbudget", False))
        self.cache_dir = Path(quota_cfg.get("cache_dir") or budget_cfg.get("cache_dir", ".cache/api_calls"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_rpm = int(quota_cfg.get("max_requests_per_minute", 8))
        self.max_rpd = int(quota_cfg.get("max_requests_per_day", 200))
        self.hard_stop_quota = bool(quota_cfg.get("hard_stop_on_quota", True))
        self._request_times: list[float] = []
        self.requests_today = 0
        self._quota_day = str(date.today())

        self.pricing = config.get("pricing_per_1m", {})
        self.cumulative_cost_usd = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_history = []

    def _hash_prompt(self, model: str, system_prompt: str, user_prompt: str) -> str:
        data = f"{model}:{system_prompt}:{user_prompt}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def get_cached_response(self, model: str, system_prompt: str, user_prompt: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Checks disk cache for existing response.
        Returns (is_cached, response_text, meta_info).
        """
        cache_key = self._hash_prompt(model, system_prompt, user_prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                logger.info(f"[CACHE HIT] Returning cached response for prompt key {cache_key[:8]}")
                return True, data["response"], data["meta"]
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        return False, "", {}

    def log_and_cache(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Logs API call token counts, calculates USD cost, caches response to disk,
        and checks budget limits.
        """
        # Free-tier quota (RPM / daily requests), not a dollar budget.
        if self.hard_stop_quota:
            today = str(date.today())
            if today != self._quota_day:
                self._quota_day = today
                self.requests_today = 0
                self._request_times = []
            now = time.time()
            self._request_times = [t for t in self._request_times if now - t < 60.0]
            if len(self._request_times) >= self.max_rpm:
                sleep_for = 60.0 - (now - self._request_times[0]) + 0.5
                logger.info(f"[QUOTA] RPM cap {self.max_rpm} reached; sleeping {sleep_for:.1f}s")
                time.sleep(max(0.0, sleep_for))
                now = time.time()
                self._request_times = [t for t in self._request_times if now - t < 60.0]
            if self.requests_today >= self.max_rpd:
                raise QuotaExceededError(
                    f"Daily Gemini request quota exhausted ({self.requests_today}/{self.max_rpd}). "
                    "Checkpointed work is on disk; resume tomorrow after quota reset."
                )
            self._request_times.append(now)
            self.requests_today += 1

        # Calculate cost (free-tier Gemini is $0; still logged for Fig 6 tokens)
        model_rates = self.pricing.get(model, {"input_usd": 0.0, "output_usd": 0.0})
        input_cost = (input_tokens / 1_000_000.0) * model_rates["input_usd"]
        output_cost = (output_tokens / 1_000_000.0) * model_rates["output_usd"]
        call_cost = input_cost + output_cost

        # Check budget limit BEFORE accepting cost
        if self.hard_stop and (self.cumulative_cost_usd + call_cost > self.max_cost_usd):
            err_msg = (
                f"Budget Limit Exceeded! Current: ${self.cumulative_cost_usd:.4f}, "
                f"Call Cost: ${call_cost:.4f}, Limit: ${self.max_cost_usd:.2f}"
            )
            logger.error(err_msg)
            raise BudgetExceededError(err_msg)

        self.cumulative_cost_usd += call_cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        meta = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": call_cost,
            "cumulative_cost_usd": self.cumulative_cost_usd
        }

        self.call_history.append(meta)

        # Cache response to disk
        cache_key = self._hash_prompt(model, system_prompt, user_prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            cache_file.write_text(
                json.dumps({"response": response_text, "meta": meta}, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed writing cache file {cache_key}: {e}")

        logger.info(
            f"[API CALL] Model: {model} | In: {input_tokens} tok | Out: {output_tokens} tok | "
            f"RPD: {self.requests_today}/{self.max_rpd} | "
            f"USD (should be 0 on free tier): ${call_cost:.4f}"
        )

        return call_cost

    def export_summary(self, export_path: Path):
        """Exports JSON summary of token usage and API costs."""
        summary = {
            "cumulative_cost_usd": self.cumulative_cost_usd,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "max_cost_usd": self.max_cost_usd,
            "requests_today": self.requests_today,
            "max_requests_per_day": self.max_rpd,
            "max_requests_per_minute": self.max_rpm,
            "quota_day": self._quota_day,
            "backend": "google-gemini-free-tier",
            "total_calls": len(self.call_history),
            "call_history": self.call_history
        }
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
