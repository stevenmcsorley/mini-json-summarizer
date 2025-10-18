"""Engine registry and dispatch helpers."""

from __future__ import annotations

from typing import Dict, Optional
import logging

from app.config import Settings, get_settings
from app.summarizer.engines.base import SummarizationEngine
from app.summarizer.engines.deterministic import DeterministicEngine
from app.summarizer.models import EvidenceBundle, SummarizationRequest

logger = logging.getLogger(__name__)


class EngineRegistry:
    """Simple registry allowing engines to be resolved by name."""

    def __init__(self) -> None:
        self._engines: Dict[str, SummarizationEngine] = {}
        self._settings: Optional[Settings] = None
        self.register(DeterministicEngine())

    def _initialize_llm_engines(self, settings: Settings) -> None:
        """Initialize LLM engines based on configuration."""
        if settings.llm_provider == "none":
            return

        try:
            from app.summarizer.engines.llm import (
                LLMEngine,
                HybridEngine,
                OpenAIProvider,
                AnthropicProvider,
                OllamaProvider,
            )

            deterministic = self._engines["deterministic"]

            # Create LLM provider
            if settings.llm_provider == "openai":
                if not settings.openai_api_key:
                    logger.warning("OpenAI API key not configured, skipping LLM engine")
                    return

                model = settings.llm_model or "gpt-4o-mini"
                provider = OpenAIProvider(api_key=settings.openai_api_key, model=model)
                logger.info(f"Initialized OpenAI provider with model: {model}")

            elif settings.llm_provider == "anthropic":
                if not settings.anthropic_api_key:
                    logger.warning(
                        "Anthropic API key not configured, skipping LLM engine"
                    )
                    return

                model = settings.llm_model or "claude-3-haiku-20240307"
                provider = AnthropicProvider(
                    api_key=settings.anthropic_api_key, model=model
                )
                logger.info(f"Initialized Anthropic provider with model: {model}")

            elif settings.llm_provider == "ollama":
                model = settings.llm_model or "llama3.2"
                base_url = settings.ollama_base_url or "http://localhost:11434"
                provider = OllamaProvider(model=model, base_url=base_url)
                logger.info(
                    f"Initialized Ollama provider with model: {model} at {base_url}"
                )

            else:
                logger.warning(f"Unknown LLM provider: {settings.llm_provider}")
                return

            # Register LLM and Hybrid engines
            llm_engine = LLMEngine(provider, deterministic)
            hybrid_engine = HybridEngine(deterministic, provider)

            self.register(llm_engine)
            self.register(hybrid_engine)

            logger.info("LLM and Hybrid engines registered successfully")

        except ImportError as e:
            logger.error(f"Failed to import LLM engines: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM engines: {e}")

    def register(self, engine: SummarizationEngine) -> None:
        self._engines[engine.name] = engine

    def resolve(
        self, name: str, settings: Optional[Settings] = None
    ) -> SummarizationEngine:
        # Initialize LLM engines on first request if configured
        if settings and not self._settings:
            self._settings = settings
            self._initialize_llm_engines(settings)

        if name in self._engines:
            return self._engines[name]
        return self._engines["deterministic"]


registry = EngineRegistry()


async def summarize(
    request: SummarizationRequest, settings: Settings | None = None
) -> EvidenceBundle:
    """Route a summarization request to the configured engine."""
    settings = settings or get_settings()
    # Let resolve() handle engine lookup and initialization
    engine = registry.resolve(request.engine, settings)

    # Check if engine has async summarize method
    if hasattr(engine, "summarize_async"):
        bundle = await engine.summarize_async(request, settings)
    else:
        # Fallback to sync method for deterministic engine
        bundle = engine.summarize(request, settings)
    return bundle
