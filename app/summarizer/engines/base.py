"""Abstract base class for summarization engines."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import Settings
from app.summarizer.models import EvidenceBundle, SummarizationRequest


class SummarizationEngine(ABC):
    name: str

    @abstractmethod
    def summarize(
        self, request: SummarizationRequest, settings: Settings
    ) -> EvidenceBundle:
        """Produce an evidence bundle for the supplied request."""

    def supports_focus(self) -> bool:
        return True
