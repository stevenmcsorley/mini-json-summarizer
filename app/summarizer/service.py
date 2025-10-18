"""Engine registry and dispatch helpers."""

from __future__ import annotations

from typing import Dict

from app.config import Settings, get_settings
from app.summarizer.engines.base import SummarizationEngine
from app.summarizer.engines.deterministic import DeterministicEngine
from app.summarizer.models import EvidenceBundle, SummarizationRequest


class EngineRegistry:
    """Simple registry allowing engines to be resolved by name."""

    def __init__(self) -> None:
        self._engines: Dict[str, SummarizationEngine] = {}
        self.register(DeterministicEngine())

    def register(self, engine: SummarizationEngine) -> None:
        self._engines[engine.name] = engine

    def resolve(self, name: str) -> SummarizationEngine:
        if name in self._engines:
            return self._engines[name]
        return self._engines["deterministic"]


registry = EngineRegistry()


def summarize(
    request: SummarizationRequest, settings: Settings | None = None
) -> EvidenceBundle:
    """Route a summarization request to the configured engine."""
    settings = settings or get_settings()
    engine_name = (
        request.engine if request.engine in registry._engines else "deterministic"
    )
    engine = registry.resolve(engine_name)
    bundle = engine.summarize(request, settings)
    return bundle
