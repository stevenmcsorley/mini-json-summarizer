"""Profile-aware summarization engine."""

import logging
from typing import Optional

from app.config import Settings
from app.profiles.extractors import extract_with_profile_extractors
from app.profiles.loader import get_profile_registry
from app.profiles.models import Profile
from app.summarizer.engines.base import SummarizationEngine
from app.summarizer.models import EvidenceBundle, SummarizationRequest

logger = logging.getLogger(__name__)


class ProfileEngine(SummarizationEngine):
    """Engine that applies profile-specific extractors before deterministic fallback."""

    name = "profile"

    def __init__(self, profile: Profile, deterministic_engine: SummarizationEngine):
        self.profile = profile
        self.deterministic_engine = deterministic_engine

    def summarize(
        self, request: SummarizationRequest, settings: Settings
    ) -> EvidenceBundle:
        """
        Summarize with profile extractors first, then deterministic backfill.

        Args:
            request: Summarization request
            settings: Application settings

        Returns:
            Evidence bundle with profile bullets first, then generic bullets
        """
        # Run profile extractors FIRST
        profile_bullets = []
        if self.profile.extractors:
            try:
                profile_bullets = extract_with_profile_extractors(
                    self.profile.extractors,
                    request.payload,
                    request.baseline_payload,
                )
                logger.debug(
                    f"Profile '{self.profile.id}' extracted {len(profile_bullets)} bullets"
                )
            except Exception as e:
                logger.error(f"Profile extractor error: {e}", exc_info=True)

        # Run generic deterministic as backfill
        generic_bundle = self.deterministic_engine.summarize(request, settings)

        # Combine: profile bullets FIRST, then generic
        combined_bullets = profile_bullets + generic_bundle.bullets

        return EvidenceBundle(
            bullets=combined_bullets,
            engine=f"profile:{self.profile.id}",
            focus=request.focus,
            redactions_applied=generic_bundle.redactions_applied,
            metadata={
                "profile": self.profile.id,
                "profile_bullets": len(profile_bullets),
            },
        )


def get_engine_for_profile(
    profile_id: Optional[str], base_engine: SummarizationEngine
) -> SummarizationEngine:
    """
    Get appropriate engine based on profile.

    Args:
        profile_id: Profile ID or None
        base_engine: Base engine to use if no profile

    Returns:
        ProfileEngine if profile found, otherwise base_engine
    """
    if not profile_id:
        return base_engine

    registry = get_profile_registry()
    profile = registry.get(profile_id)

    if not profile:
        return base_engine

    # Use the provided base_engine for backfill (supports llm, hybrid, etc.)
    return ProfileEngine(profile, base_engine)
