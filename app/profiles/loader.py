"""Profile loading and registry management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from app.profiles.models import Profile, ProfileSummary

logger = logging.getLogger(__name__)


class ProfileRegistry:
    """Registry for managing loaded profiles."""

    def __init__(self) -> None:
        self._profiles: Dict[str, Profile] = {}
        self._loaded = False

    def load_from_directory(self, profiles_dir: str | Path) -> None:
        """
        Load all YAML profiles from the specified directory.

        Args:
            profiles_dir: Path to directory containing profile YAML files

        Raises:
            FileNotFoundError: If directory doesn't exist
            ValidationError: If a profile fails validation
        """
        profiles_path = Path(profiles_dir)
        if not profiles_path.exists():
            logger.warning(f"Profiles directory not found: {profiles_dir}")
            return

        if not profiles_path.is_dir():
            logger.error(f"Profiles path is not a directory: {profiles_dir}")
            return

        loaded_profiles = []
        for yaml_file in profiles_path.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    logger.warning(f"Empty profile file: {yaml_file}")
                    continue

                profile = Profile.model_validate(data)
                self._profiles[profile.id] = profile
                loaded_profiles.append(f"{profile.id}@{profile.version}")
                logger.debug(f"Loaded profile: {profile.id} from {yaml_file}")

            except yaml.YAMLError as e:
                logger.error(f"YAML parse error in {yaml_file}: {e}")
                raise
            except ValidationError as e:
                logger.error(f"Validation error in {yaml_file}: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error loading {yaml_file}: {e}")
                raise

        self._loaded = True
        if loaded_profiles:
            logger.info(f"Profiles loaded: {', '.join(loaded_profiles)}")
        else:
            logger.info("No profiles loaded")

    def get(self, profile_id: str) -> Optional[Profile]:
        """
        Get a profile by ID.

        Args:
            profile_id: Profile identifier

        Returns:
            Profile if found, None otherwise
        """
        return self._profiles.get(profile_id)

    def list_profiles(self) -> List[ProfileSummary]:
        """
        Get summary information about all loaded profiles.

        Returns:
            List of profile summaries
        """
        return [
            ProfileSummary(
                id=profile.id,
                title=profile.title,
                version=profile.version,
                description=profile.description,
            )
            for profile in self._profiles.values()
        ]

    def get_available_ids(self) -> List[str]:
        """Get list of available profile IDs."""
        return list(self._profiles.keys())

    def is_loaded(self) -> bool:
        """Check if profiles have been loaded."""
        return self._loaded

    def clear(self) -> None:
        """Clear all loaded profiles."""
        self._profiles.clear()
        self._loaded = False


# Global registry instance
_registry: Optional[ProfileRegistry] = None


def get_profile_registry() -> ProfileRegistry:
    """Get the global profile registry instance."""
    global _registry
    if _registry is None:
        _registry = ProfileRegistry()
    return _registry


def reload_profiles(profiles_dir: str | Path) -> None:
    """
    Reload profiles from directory.

    Args:
        profiles_dir: Path to profiles directory
    """
    registry = get_profile_registry()
    registry.clear()
    registry.load_from_directory(profiles_dir)
