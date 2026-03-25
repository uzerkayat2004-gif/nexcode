"""
NexCode Model Registry & Pricing Database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive database of all supported AI models across providers,
including context windows, capabilities, and per-token pricing.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Model info dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelInfo:
    """Immutable metadata for a single AI model."""

    name: str
    provider: str
    context_window: int
    supports_tools: bool
    input_cost_per_1m: float   # USD per 1M input tokens
    output_cost_per_1m: float  # USD per 1M output tokens
    description: str
    is_free: bool = False
    requires_oauth: bool = False

    @property
    def input_cost_per_token(self) -> float:
        """Cost in USD for a single input token."""
        return self.input_cost_per_1m / 1_000_000

    @property
    def output_cost_per_token(self) -> float:
        """Cost in USD for a single output token."""
        return self.output_cost_per_1m / 1_000_000

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate total cost for a given token usage."""
        return (
            input_tokens * self.input_cost_per_token
            + output_tokens * self.output_cost_per_token
        )


# ---------------------------------------------------------------------------
# Model registry — full pricing database
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, dict[str, ModelInfo]] = {

    # ── ANTHROPIC (direct API) ─────────────────────────────────────────────
    "anthropic": {
        "claude-opus-4-6": ModelInfo(
            name="claude-opus-4-6",
            provider="anthropic",
            context_window=200_000,
            supports_tools=True,
            input_cost_per_1m=15.00,
            output_cost_per_1m=75.00,
            description="Most powerful Claude model",
        ),
        "claude-sonnet-4-6": ModelInfo(
            name="claude-sonnet-4-6",
            provider="anthropic",
            context_window=200_000,
            supports_tools=True,
            input_cost_per_1m=3.00,
            output_cost_per_1m=15.00,
            description="Balanced speed and intelligence",
        ),
    },

    # ── OPENROUTER (186+ models via single key) ────────────────────────────
    "openrouter": {
        # FREE models
        "moonshotai/kimi-k2.5": ModelInfo(
            name="moonshotai/kimi-k2.5",
            provider="openrouter",
            context_window=262_144,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free — agentic coding, tool use, reasoning",
            is_free=True,
        ),
        "arcee-ai/trinity-large-preview": ModelInfo(
            name="arcee-ai/trinity-large-preview",
            provider="openrouter",
            context_window=131_072,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free — 400B MoE, built for agentic coding",
            is_free=True,
        ),
        "minimax/minimax-m2": ModelInfo(
            name="minimax/minimax-m2",
            provider="openrouter",
            context_window=131_072,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free — strong general purpose model",
            is_free=True,
        ),
        "z-ai/glm-4.7": ModelInfo(
            name="z-ai/glm-4.7",
            provider="openrouter",
            context_window=128_000,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free — agent-centric applications",
            is_free=True,
        ),
        "qwen/qwen3-coder": ModelInfo(
            name="qwen/qwen3-coder",
            provider="openrouter",
            context_window=262_144,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free — optimized for coding and function calling",
            is_free=True,
        ),
        # PAID (cheap)
        "minimax/minimax-m2.5": ModelInfo(
            name="minimax/minimax-m2.5",
            provider="openrouter",
            context_window=131_072,
            supports_tools=True,
            input_cost_per_1m=0.255,
            output_cost_per_1m=1.00,
            description="Paid — 80.2% SWE-Bench, extremely cheap",
        ),
        "deepseek/deepseek-coder-v3": ModelInfo(
            name="deepseek/deepseek-coder-v3",
            provider="openrouter",
            context_window=128_000,
            supports_tools=True,
            input_cost_per_1m=0.27,
            output_cost_per_1m=1.10,
            description="Paid — top coding model, very affordable",
        ),
    },

    # ── GOOGLE (OAuth = free, or API key) ──────────────────────────────────
    "google": {
        "gemini-2.0-flash": ModelInfo(
            name="gemini-2.0-flash",
            provider="google",
            context_window=1_048_576,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free via OAuth — 1M context, fast",
            is_free=True,
            requires_oauth=True,
        ),
        "gemini-1.5-pro": ModelInfo(
            name="gemini-1.5-pro",
            provider="google",
            context_window=2_097_152,
            supports_tools=True,
            input_cost_per_1m=1.25,
            output_cost_per_1m=5.00,
            description="2M context window — largest available",
        ),
    },

    # ── GROQ (ultra-fast inference) ────────────────────────────────────────
    "groq": {
        "llama-3.3-70b-versatile": ModelInfo(
            name="llama-3.3-70b-versatile",
            provider="groq",
            context_window=131_072,
            supports_tools=True,
            input_cost_per_1m=0.59,
            output_cost_per_1m=0.79,
            description="Ultra fast — best for quick tasks",
        ),
    },

    # ── GITHUB COPILOT (OAuth login) ───────────────────────────────────────
    "github": {
        "gpt-4o": ModelInfo(
            name="gpt-4o",
            provider="github",
            context_window=128_000,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free via Copilot subscription",
            is_free=True,
            requires_oauth=True,
        ),
        "claude-sonnet-4-6": ModelInfo(
            name="claude-sonnet-4-6",
            provider="github",
            context_window=200_000,
            supports_tools=True,
            input_cost_per_1m=0.00,
            output_cost_per_1m=0.00,
            description="Free Claude via Copilot subscription",
            is_free=True,
            requires_oauth=True,
        ),
    },

    # ── OLLAMA (local, free, no internet) ──────────────────────────────────
    # Ollama models are detected dynamically at runtime.
    # This entry serves as a provider-level marker.
    "ollama": {},
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_model_info(provider: str, model: str) -> ModelInfo | None:
    """
    Look up a model's info by provider and model name.

    Returns ``None`` if the provider or model is not in the registry.
    """
    provider_models = MODEL_REGISTRY.get(provider, {})
    return provider_models.get(model)


def list_models_for_provider(provider: str) -> list[ModelInfo]:
    """Return all registered models for a given provider."""
    return list(MODEL_REGISTRY.get(provider, {}).values())


def list_all_providers() -> list[str]:
    """Return all known provider names."""
    return list(MODEL_REGISTRY.keys())


def find_model(model_name: str) -> ModelInfo | None:
    """
    Search for a model across all providers by name.

    Returns the first match found, or ``None``.
    """
    for provider_models in MODEL_REGISTRY.values():
        if model_name in provider_models:
            return provider_models[model_name]
    return None


def list_free_models() -> list[ModelInfo]:
    """Return all models that are free to use."""
    free: list[ModelInfo] = []
    for provider_models in MODEL_REGISTRY.values():
        for model in provider_models.values():
            if model.is_free:
                free.append(model)
    return free


def get_cheapest_model(provider: str | None = None) -> ModelInfo | None:
    """
    Return the cheapest non-free model, optionally filtered by provider.
    """
    candidates: list[ModelInfo] = []
    providers = [provider] if provider else list(MODEL_REGISTRY.keys())

    for p in providers:
        for model in MODEL_REGISTRY.get(p, {}).values():
            if not model.is_free:
                candidates.append(model)

    if not candidates:
        return None
    return min(candidates, key=lambda m: m.input_cost_per_1m + m.output_cost_per_1m)
