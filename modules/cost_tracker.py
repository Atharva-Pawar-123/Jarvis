"""
cost_tracker.py — JARVIS Token Cost & Budgeting Engine
========================================================
Inspired by the claude-code cost-tracker architecture.

Tracks token usage and estimated USD cost across Gemini API calls.
Persists session totals to a JSON file so JARVIS can report spending
across restarts. Provides a formatted summary JARVIS can speak aloud.

Gemini 2.0 Flash pricing (as of Jun 2025):
  - Input:  $0.075 / 1M tokens  (≤128k context)
  - Output: $0.30  / 1M tokens
  - Input:  $0.15  / 1M tokens  (>128k context)
  Note: Ollama (local) is always $0.00.
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def calculate_usd_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate USD cost for an LLM call.
    Returns estimated cost for cloud models, and 0.0 for local Ollama models.
    """
    model_lower = model.lower()
    if any(m in model_lower for m in ["ollama", "qwen", "llama", "deepseek", "mistral", "nomic"]):
        return 0.0
    # Cloud model pricing estimate (e.g. Gemini)
    input_rate = 0.075 / 1_000_000
    output_rate = 0.30 / 1_000_000
    return (input_tokens * input_rate) + (output_tokens * output_rate)


# ---------------------------------------------------------------------------
# CostTracker — the main singleton
# ---------------------------------------------------------------------------

@dataclass
class SessionStats:
    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_calls: int = 0
    model_breakdown: Dict[str, dict] = field(default_factory=dict)
    date: str = field(default_factory=lambda: str(date.today()))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class ModelUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    call_count: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


COST_DB_PATH = config.DATA_DIR / "cost_tracker.json"


class CostTracker:
    """
    Singleton that accumulates token usage across all LLM calls in a session.

    Usage:
        CostTracker.get().record(model, input_tokens, output_tokens)
        CostTracker.get().format_summary()
    """

    _instance: Optional["CostTracker"] = None
    _lock = threading.Lock()

    def __init__(self, session_id: str) -> None:
        self._session = SessionStats(session_id=session_id)
        self._all_time: Optional[SessionStats] = None
        self._model_usages: Dict[str, ModelUsage] = {}
        self._rlock = threading.Lock()
        self._load_persistent()

    # -- Singleton accessor --------------------------------------------------

    @classmethod
    def get(cls) -> "CostTracker":
        """Return the singleton CostTracker, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    cls._instance = cls(session_id=session_id)
        return cls._instance

    # -- Recording -----------------------------------------------------------

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        backend: str = "gemini",
    ) -> float:
        """
        Record a single LLM call's token usage.

        Args:
            model:         The model name (e.g. "gemini-2.0-flash").
            input_tokens:  Number of prompt/input tokens consumed.
            output_tokens: Number of completion/output tokens generated.
            backend:       "gemini" or "ollama" (ollama cost is always $0).

        Returns:
            The USD cost of this single call.
        """
        if backend == "ollama":
            cost = 0.0
        else:
            cost = calculate_usd_cost(model, input_tokens, output_tokens)

        with self._rlock:
            # Update per-model breakdown
            if model not in self._model_usages:
                self._model_usages[model] = ModelUsage(model=model)
            mu = self._model_usages[model]
            mu.input_tokens += input_tokens
            mu.output_tokens += output_tokens
            mu.cost_usd += cost
            mu.call_count += 1

            # Update session totals
            self._session.total_input_tokens += input_tokens
            self._session.total_output_tokens += output_tokens
            self._session.total_cost_usd += cost
            self._session.total_calls += 1
            self._session.model_breakdown[model] = mu.to_dict()

        logger.debug(
            f"[CostTracker] {model} | in={input_tokens} out={output_tokens} "
            f"cost=${cost:.6f} | session_total=${self._session.total_cost_usd:.4f}"
        )
        return cost

    # -- Getters -------------------------------------------------------------

    @property
    def session(self) -> SessionStats:
        return self._session

    def get_session_cost(self) -> float:
        return self._session.total_cost_usd

    def get_session_tokens(self) -> Tuple[int, int]:
        """Returns (total_input_tokens, total_output_tokens) for the session."""
        return self._session.total_input_tokens, self._session.total_output_tokens

    def get_all_time_cost(self) -> float:
        if self._all_time is None:
            return self._session.total_cost_usd
        return self._all_time.total_cost_usd + self._session.total_cost_usd

    # -- Formatting ----------------------------------------------------------

    def format_summary(self, verbose: bool = False) -> str:
        """
        Returns a plain-text cost summary JARVIS can log or speak aloud.

        Example (brief):
            Session cost: $0.0023 | 4,821 tokens in | 312 tokens out | 7 calls

        Example (verbose):
            Session cost: $0.0023 | 4,821 tokens in | 312 tokens out | 7 calls
              gemini-2.0-flash: 4,200 in / 280 out — $0.0021 (5 calls)
              llama3.2:1b:      621 in  / 32 out  — $0.0000 (2 calls, local)
        """
        s = self._session
        brief = (
            f"Session cost: ${s.total_cost_usd:.4f} | "
            f"{s.total_input_tokens:,} tokens in | "
            f"{s.total_output_tokens:,} tokens out | "
            f"{s.total_calls} calls"
        )

        if not verbose:
            return brief

        lines = [brief]
        for model_name, mu_dict in s.model_breakdown.items():
            mu = ModelUsage.from_dict(mu_dict)
            local_tag = " (local)" if mu.cost_usd == 0.0 else ""
            lines.append(
                f"  {model_name}: {mu.input_tokens:,} in / {mu.output_tokens:,} out "
                f"— ${mu.cost_usd:.4f} ({mu.call_count} calls{local_tag})"
            )

        if self._all_time is not None:
            all_time_total = self._all_time.total_cost_usd + s.total_cost_usd
            lines.append(f"All-time cumulative cost: ${all_time_total:.4f}")

        return "\n".join(lines)

    def format_voice_summary(self) -> str:
        """
        A concise, natural summary JARVIS can speak aloud.
        E.g.: 'This session has used approximately 5,100 tokens at a cost of less than half a cent, sir.'
        """
        s = self._session
        total_tokens = s.total_input_tokens + s.total_output_tokens
        cost = s.total_cost_usd

        if cost < 0.001:
            cost_str = "less than a tenth of a cent"
        elif cost < 0.01:
            cost_str = f"{cost * 100:.2f} cents"
        else:
            cost_str = f"${cost:.3f}"

        return (
            f"This session has consumed {total_tokens:,} tokens across "
            f"{s.total_calls} API calls, at an estimated cost of {cost_str}, sir."
        )

    # -- Budget checking -----------------------------------------------------

    def get_today_cost(self) -> float:
        """Returns the cumulative cost for today across all sessions."""
        if self._all_time and self._all_time.date == str(date.today()):
            return self._all_time.total_cost_usd + self._session.total_cost_usd
        return self._session.total_cost_usd

    def check_budget(self, daily_limit_usd: float) -> Optional[str]:
        """
        Returns a warning string if today's cumulative cost exceeds the daily limit.
        Returns None if within budget.
        """
        today_cost = self.get_today_cost()

        if today_cost >= daily_limit_usd:
            return (
                f"Sir, the daily API budget of ${daily_limit_usd:.2f} has been reached. "
                f"Today's total Gemini spend is ${today_cost:.4f}. "
                "I am switching to the local Ollama engine to conserve resources."
            )
        if today_cost >= daily_limit_usd * 0.8:
            return (
                f"Sir, we are at {today_cost / daily_limit_usd * 100:.0f}% of the daily "
                f"API budget (${today_cost:.4f} of ${daily_limit_usd:.2f}). "
                "I recommend switching to local inference soon."
            )
        return None

    # -- Persistence ---------------------------------------------------------

    def save(self) -> None:
        """Persist session totals to disk. Call on JARVIS shutdown."""
        try:
            COST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            db = self._load_db()

            # Accumulate into all-time record
            all_time_key = "all_time"
            if all_time_key not in db:
                db[all_time_key] = SessionStats(session_id="all_time").to_dict()

            at = SessionStats.from_dict(db[all_time_key])
            at.total_input_tokens += self._session.total_input_tokens
            at.total_output_tokens += self._session.total_output_tokens
            at.total_cost_usd += self._session.total_cost_usd
            at.total_calls += self._session.total_calls
            at.date = str(date.today())

            db[all_time_key] = at.to_dict()
            db[self._session.session_id] = self._session.to_dict()

            with open(COST_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2)

            logger.info(
                f"[CostTracker] Session saved. "
                f"Session cost: ${self._session.total_cost_usd:.4f} | "
                f"All-time: ${at.total_cost_usd:.4f}"
            )
        except Exception as e:
            logger.warning(f"[CostTracker] Failed to save cost data: {e}")

    def _load_persistent(self) -> None:
        """Load all-time totals from disk on startup."""
        try:
            db = self._load_db()
            if "all_time" in db:
                self._all_time = SessionStats.from_dict(db["all_time"])
                logger.info(
                    f"[CostTracker] Loaded all-time cost: "
                    f"${self._all_time.total_cost_usd:.4f} | "
                    f"{self._all_time.total_input_tokens:,} tokens"
                )
        except Exception as e:
            logger.debug(f"[CostTracker] No prior cost data found: {e}")
            self._all_time = None

    @staticmethod
    def _load_db() -> dict:
        """Load the raw cost JSON database from disk."""
        if COST_DB_PATH.exists():
            with open(COST_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
