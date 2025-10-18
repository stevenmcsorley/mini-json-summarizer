"""Profile system for Mini JSON Summarizer."""

from app.profiles.loader import ProfileRegistry, get_profile_registry
from app.profiles.models import Profile, ProfileSummary

__all__ = ["Profile", "ProfileSummary", "ProfileRegistry", "get_profile_registry"]
