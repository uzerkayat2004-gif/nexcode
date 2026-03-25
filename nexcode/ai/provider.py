"""
NexCode AI Provider Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified multi-provider AI engine that routes requests through LiteLLM
for consistent API access across Anthropic, OpenAI, Google, OpenRouter,
Groq, Ollama, and more.

Features:
  - Hot-swap model/provider at runtime
  - Real-time token streaming
  - Automatic model selection based on auth status
  - Exponential backoff retry on rate limits
  - Context window tracking and compaction
  - Cost estimation per request
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import litellm
from rich.text import Text

from nexcode.ai.auth import AuthManager
from nexcode.ai.models import (
    ModelInfo,
    get_model_info,
    list_models_for_provider,
)
from nexcode.config import NexCodeConfig

# Suppress LiteLLM's verbose logging.
litellm.suppress_debug_info = True
litellm.set_verbose = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A single tool/function call requested by the AI."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AIResponse:
    """Complete response from an AI provider."""

    content: str
    tool_calls: list[ToolCall] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    stop_reason: str = ""          # "end_turn", "tool_use", "max_tokens"
    cost_usd: float = 0.0         # Calculated from model pricing
    response_time_ms: int = 0     # Round-trip time

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def format_footer(self) -> Text:
        """Build the response footer line shown after each AI turn."""
        cost_str = f"${self.cost_usd:.4f}" if self.cost_usd > 0 else "free"
        time_str = f"{self.response_time_ms / 1000:.1f}s"
        tokens_str = f"{self.total_tokens:,} tokens"

        return Text.assemble(
            ("  [", "bright_black"),
            (self.model, "bold white"),
            (" | ", "bright_black"),
            (self.provider, "dim"),
            (" | ", "bright_black"),
            (tokens_str, "cyan"),
            (" | ", "bright_black"),
            (cost_str, "green" if self.cost_usd == 0 else "yellow"),
            (" | ", "bright_black"),
            (time_str, "dim"),
            ("]", "bright_black"),
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(self, message: str, *, suggestion: str = "") -> None:
        super().__init__(message)
        self.suggestion = suggestion


class AuthenticationError(AIProviderError):
    """Invalid or missing API key / token."""
    pass


class RateLimitError(AIProviderError):
    """Provider rate limit exceeded."""
    pass


class ContextWindowError(AIProviderError):
    """Input exceeds the model's context window."""
    pass


class ModelUnavailableError(AIProviderError):
    """Requested model is not available."""
    pass


# ---------------------------------------------------------------------------
# Provider-specific LiteLLM model name mapping
# ---------------------------------------------------------------------------

def _litellm_model_name(provider: str, model: str) -> str:
    """
    Map a NexCode provider/model pair to the LiteLLM model string.

    LiteLLM uses prefixes to route to the correct provider.
    """
    prefix_map: dict[str, str] = {
        "anthropic": "anthropic/",
        "openai": "openai/",
        "openrouter": "openrouter/",
        "google": "gemini/",
        "groq": "groq/",
        "ollama": "ollama/",
        "github": "github/",
        "mistral": "mistral/",
        "deepseek": "deepseek/",
    }

    prefix = prefix_map.get(provider, "")
    return f"{prefix}{model}"


# ---------------------------------------------------------------------------
# AIProvider — main engine
# ---------------------------------------------------------------------------

class AIProvider:
    """
    Multi-provider AI engine for NexCode.

    Routes all requests through LiteLLM for a unified API, with
    added features: streaming, auto-select, retry, cost tracking,
    and context management.
    """

    # Retry config.
    MAX_RETRIES: int = 3
    INITIAL_RETRY_DELAY: float = 1.0  # seconds

    # Context warning thresholds.
    CONTEXT_WARN_PERCENT: float = 0.80
    CONTEXT_CRITICAL_PERCENT: float = 0.95

    def __init__(
        self,
        config: NexCodeConfig,
        auth: AuthManager,
    ) -> None:
        self.config = config
        self.auth = auth
        self._current_provider: str = config.default_provider
        self._current_model: str = config.default_model
        self._model_info: ModelInfo | None = get_model_info(
            self._current_provider, self._current_model
        )

        # Inject API keys into LiteLLM's environment if available.
        self._configure_litellm()

    # ── Configuration ──────────────────────────────────────────────────────

    def _configure_litellm(self) -> None:
        """Push available API keys into the environment for LiteLLM."""
        import os

        provider_env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "google": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        for provider, env_var in provider_env_map.items():
            key = self.auth.get_effective_credential(provider)
            if key and not os.environ.get(env_var):
                os.environ[env_var] = key

    def switch_model(self, provider: str, model: str) -> None:
        """
        Hot-swap to a different model/provider without restarting.

        Raises ``ModelUnavailableError`` if the provider is not authenticated.
        """
        if not self.auth.is_authenticated(provider):
            raise ModelUnavailableError(
                f"Provider '{provider}' is not authenticated.",
                suggestion=f"Run: nexcode --login {provider}",
            )

        self._current_provider = provider
        self._current_model = model
        self._model_info = get_model_info(provider, model)
        self._configure_litellm()

    # ── Chat completion ────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> AIResponse:
        """
        Send a chat completion request to the current provider.

        Args:
            messages: Conversation history in OpenAI message format.
            tools: Optional tool/function definitions.
            stream: If True, returns after collecting the full streamed response.

        Returns:
            A complete ``AIResponse``.

        Raises:
            AuthenticationError: If the provider key is invalid.
            RateLimitError: After all retries are exhausted.
            ContextWindowError: If the input exceeds the context window.
            AIProviderError: For other provider errors.
        """
        litellm_model = _litellm_model_name(self._current_provider, self._current_model)
        start_time = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": 0.0,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._call_with_retry(kwargs)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return self._parse_response(response, elapsed_ms)

    async def stream_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream a response token-by-token.

        Yields partial content strings as they arrive from the provider.
        After the stream completes, the full AIResponse is available
        via ``self.last_response``.
        """
        litellm_model = _litellm_model_name(self._current_provider, self._current_model)
        start_time = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": 0.0,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        collected_content: list[str] = []
        collected_tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0
        stop_reason = ""

        try:
            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Yield content tokens.
                if delta.content:
                    collected_content.append(delta.content)
                    yield delta.content

                # Collect tool calls.
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function and tc.function.name:
                            import json
                            try:
                                args = json.loads(tc.function.arguments or "{}")
                            except json.JSONDecodeError:
                                args = {}
                            collected_tool_calls.append(
                                ToolCall(
                                    id=tc.id or "",
                                    name=tc.function.name,
                                    arguments=args,
                                )
                            )

                # Check finish reason.
                finish = chunk.choices[0].finish_reason if chunk.choices else None
                if finish:
                    stop_reason = self._normalize_stop_reason(finish)

                # Token usage (usually in the final chunk).
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0

        except Exception as exc:
            self._handle_provider_error(exc)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        cost = self._calculate_cost(input_tokens, output_tokens)

        self.last_response = AIResponse(
            content="".join(collected_content),
            tool_calls=collected_tool_calls or None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._current_model,
            provider=self._current_provider,
            stop_reason=stop_reason,
            cost_usd=cost,
            response_time_ms=elapsed_ms,
        )

    # ── Auto-select model ──────────────────────────────────────────────────

    async def auto_select_model(self) -> tuple[str, str]:
        """
        Automatically pick the best available model based on auth status.

        Priority:
          1. Anthropic (claude-opus-4-6) if key exists
          2. Google OAuth (gemini-2.0-flash) if authenticated — free
          3. OpenRouter (moonshotai/kimi-k2.5) if key exists — free
          4. Ollama (best local model)
          5. None — show setup guide

        Returns:
            Tuple of (provider, model).

        Raises:
            AuthenticationError if no providers are available.
        """
        # 1. Anthropic
        if self.auth.is_authenticated("anthropic"):
            return ("anthropic", "claude-opus-4-6")

        # 2. Google OAuth (free)
        if self.auth.is_authenticated("google"):
            return ("google", "gemini-2.0-flash")

        # 3. OpenRouter (free tier)
        if self.auth.is_authenticated("openrouter"):
            return ("openrouter", "moonshotai/kimi-k2.5")

        # 4. Groq
        if self.auth.is_authenticated("groq"):
            return ("groq", "llama-3.3-70b-versatile")

        # 5. Ollama (local)
        if self.auth.is_authenticated("ollama"):
            ollama_models = self.auth.get_ollama_models()
            if ollama_models:
                return ("ollama", ollama_models[0])

        # 6. GitHub Copilot
        if self.auth.is_authenticated("github"):
            return ("github", "gpt-4o")

        raise AuthenticationError(
            "No AI providers are configured.",
            suggestion=(
                "Run one of:\n"
                "  nexcode --login google     (free Gemini access)\n"
                "  nexcode --login anthropic  (API key)\n"
                "  nexcode --login openrouter (186+ models)\n"
                "  nexcode --login ollama     (local, offline)"
            ),
        )

    # ── Token counting & context management ────────────────────────────────

    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Estimate token count for a list of messages.

        Uses LiteLLM's built-in token counter when available,
        falls back to a rough character-based estimate.
        """
        try:
            litellm_model = _litellm_model_name(
                self._current_provider, self._current_model
            )
            return litellm.token_counter(model=litellm_model, messages=messages)
        except Exception:
            # Fallback: ~4 chars per token is a reasonable approximation.
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return total_chars // 4

    def get_context_usage_percent(self, messages: list[dict[str, Any]]) -> float:
        """
        Return the percentage of the context window currently used.

        Returns a float between 0.0 and 1.0+.
        """
        if not self._model_info:
            return 0.0
        tokens = self.count_tokens(messages)
        return tokens / self._model_info.context_window

    def check_context_warnings(self, messages: list[dict[str, Any]]) -> str | None:
        """
        Check context usage and return a warning string if thresholds
        are exceeded.  Returns ``None`` if usage is within safe limits.
        """
        usage = self.get_context_usage_percent(messages)

        if usage >= self.CONTEXT_CRITICAL_PERCENT:
            pct = int(usage * 100)
            return (
                f"🔴 CRITICAL: Context window is {pct}% full! "
                "Use /compact to summarize and free space."
            )
        elif usage >= self.CONTEXT_WARN_PERCENT:
            pct = int(usage * 100)
            return (
                f"🟡 Warning: Context window is {pct}% full. "
                "Consider using /compact soon."
            )

        return None

    # ── Model info & listing ───────────────────────────────────────────────

    def list_all_available_models(self) -> dict[str, list[str]]:
        """
        Return all available models across authenticated providers.

        Keys are provider names, values are lists of model names.
        """
        result: dict[str, list[str]] = {}

        for provider in self.auth.list_authenticated_providers():
            if provider == "ollama":
                models = self.auth.get_ollama_models()
            else:
                models = [m.name for m in list_models_for_provider(provider)]

            if models:
                result[provider] = models

        return result

    def get_model_info(self) -> ModelInfo | None:
        """Return the ``ModelInfo`` for the currently active model."""
        return self._model_info

    @property
    def current_model(self) -> str:
        return self._current_model

    @current_model.setter
    def current_model(self, value: str) -> None:
        self._current_model = value

    @property
    def current_provider(self) -> str:
        return self._current_provider

    @current_provider.setter
    def current_provider(self, value: str) -> None:
        self._current_provider = value

    # ── Internal: retry logic ──────────────────────────────────────────────

    async def _call_with_retry(self, kwargs: dict[str, Any]) -> Any:
        """
        Call LiteLLM with exponential backoff on retryable errors.
        """
        last_error: Exception | None = None
        delay = self.INITIAL_RETRY_DELAY

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await litellm.acompletion(**kwargs)
            except litellm.RateLimitError as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff.
                continue
            except litellm.AuthenticationError as exc:
                raise AuthenticationError(
                    f"Invalid API key for {self._current_provider}.",
                    suggestion=f"Run: nexcode --login {self._current_provider}",
                ) from exc
            except litellm.ContextWindowExceededError as exc:
                raise ContextWindowError(
                    "Input exceeds the model's context window.",
                    suggestion="Use /compact to summarize the conversation.",
                ) from exc
            except litellm.NotFoundError as exc:
                raise ModelUnavailableError(
                    f"Model '{self._current_model}' is not available on {self._current_provider}.",
                    suggestion="Use /models to see available models.",
                ) from exc
            except litellm.Timeout as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                continue
            except Exception as exc:
                self._handle_provider_error(exc)

        # All retries exhausted.
        if isinstance(last_error, litellm.RateLimitError):
            raise RateLimitError(
                f"Rate limit exceeded after {self.MAX_RETRIES} retries.",
                suggestion="Wait a moment and try again, or switch to a different model.",
            )
        raise AIProviderError(
            f"Request failed after {self.MAX_RETRIES} attempts: {last_error}",
        )

    # ── Internal: response parsing ─────────────────────────────────────────

    def _parse_response(self, response: Any, elapsed_ms: int) -> AIResponse:
        """Parse a LiteLLM response into an ``AIResponse``."""
        choice = response.choices[0] if response.choices else None
        content = ""
        tool_calls: list[ToolCall] | None = None
        stop_reason = ""

        if choice:
            content = choice.message.content or ""
            stop_reason = self._normalize_stop_reason(choice.finish_reason or "")

            if choice.message.tool_calls:
                import json
                tool_calls = []
                for tc in choice.message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(
                        ToolCall(id=tc.id or "", name=tc.function.name, arguments=args)
                    )

        # Extract usage.
        usage = response.usage if hasattr(response, "usage") else None
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = self._calculate_cost(input_tokens, output_tokens)

        return AIResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._current_model,
            provider=self._current_provider,
            stop_reason=stop_reason,
            cost_usd=cost,
            response_time_ms=elapsed_ms,
        )

    def _normalize_stop_reason(self, reason: str) -> str:
        """Normalize various provider-specific stop reasons."""
        reason = reason.lower()
        mapping = {
            "stop": "end_turn",
            "end_turn": "end_turn",
            "tool_calls": "tool_use",
            "tool_use": "tool_use",
            "function_call": "tool_use",
            "length": "max_tokens",
            "max_tokens": "max_tokens",
        }
        return mapping.get(reason, reason)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the USD cost based on the model's pricing."""
        if not self._model_info:
            return 0.0
        return self._model_info.estimate_cost(input_tokens, output_tokens)

    def _handle_provider_error(self, exc: Exception) -> None:
        """Convert generic exceptions to NexCode-specific errors."""
        error_msg = str(exc).lower()

        if "api key" in error_msg or "authentication" in error_msg or "401" in error_msg:
            raise AuthenticationError(
                f"Authentication failed for {self._current_provider}: {exc}",
                suggestion=f"Run: nexcode --login {self._current_provider}",
            ) from exc

        if "rate limit" in error_msg or "429" in error_msg:
            raise RateLimitError(
                f"Rate limit exceeded: {exc}",
                suggestion="Wait a moment or switch to a different model.",
            ) from exc

        if "context" in error_msg and ("window" in error_msg or "length" in error_msg):
            raise ContextWindowError(
                f"Context window exceeded: {exc}",
                suggestion="Use /compact to summarize the conversation.",
            ) from exc

        raise AIProviderError(f"Provider error: {exc}") from exc

    # ── Repr ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"AIProvider(model={self._current_model!r}, "
            f"provider={self._current_provider!r})"
        )
