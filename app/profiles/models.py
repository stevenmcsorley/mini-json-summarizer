"""Profile data models for Mini JSON Summarizer."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import re


class ProfileRedactionRegex(BaseModel):
    """Custom redaction regex pattern."""

    name: str = Field(..., description="Name of the redaction pattern")
    pattern: str = Field(..., description="Regex pattern to match")

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate that the pattern is a valid regex."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        return v


class ProfileRedaction(BaseModel):
    """Redaction configuration for a profile."""

    allow_paths: Optional[List[str]] = Field(
        default=None, description="JSONPath patterns to allow (override deny)"
    )
    deny_paths: Optional[List[str]] = Field(
        default=None, description="JSONPath patterns to deny"
    )
    extra_regexes: Optional[List[ProfileRedactionRegex]] = Field(
        default=None, description="Additional regex patterns for redaction"
    )


class ProfileLimits(BaseModel):
    """Limits configuration for a profile."""

    topk: Optional[int] = Field(default=None, ge=1, le=100)
    numeric_fields_limit: Optional[int] = Field(default=None, ge=1, le=100)
    string_cardinality_limit: Optional[int] = Field(default=None, ge=1, le=100)


class ProfileTime(BaseModel):
    """Time configuration for a profile."""

    timezone: str = Field(default="UTC", description="IANA timezone or UTC")
    timebucket_default: Literal["minute", "hour", "day"] = Field(default="minute")


class ProfileLLMHints(BaseModel):
    """LLM hints for profile-specific prompt customization."""

    system_suffix: Optional[str] = Field(
        default=None, description="Additional text to append to system prompt"
    )
    bullet_prefix: Optional[str] = Field(
        default=None, description="Prefix for each bullet point"
    )
    narrative_tone: Optional[Literal["neutral", "urgent", "compliance"]] = Field(
        default=None, description="Tone for narrative style"
    )


class ProfileDefaults(BaseModel):
    """Default settings for a profile."""

    focus: List[str] = Field(default_factory=list, description="Default focus areas")
    style: Literal["bullets", "narrative", "kpi-block", "mixed"] = Field(
        default="bullets"
    )
    length: Literal["short", "medium", "long"] = Field(default="medium")


class Profile(BaseModel):
    """Complete profile specification."""

    id: str = Field(..., description="Unique profile identifier")
    version: str = Field(default="1.0.0", description="Semantic version")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Profile description")
    defaults: ProfileDefaults = Field(
        default_factory=ProfileDefaults, description="Default request settings"
    )
    extractors: List[str] = Field(
        default_factory=list,
        description="List of extractor keys to apply (e.g., 'categorical:level', 'numeric:latency_ms')",
    )
    llm_hints: Optional[ProfileLLMHints] = Field(
        default=None, description="LLM-specific hints"
    )
    redaction: Optional[ProfileRedaction] = Field(
        default=None, description="Redaction rules"
    )
    limits: Optional[ProfileLimits] = Field(
        default=None, description="Processing limits"
    )
    time: Optional[ProfileTime] = Field(
        default=None, description="Time-related settings"
    )

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        """Validate semantic versioning format."""
        semver_pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?$"
        if not re.match(semver_pattern, v):
            raise ValueError(f"Invalid semantic version: {v}")
        return v

    @field_validator("extractors")
    @classmethod
    def validate_extractors(cls, v: List[str]) -> List[str]:
        """Validate extractor format."""
        valid_types = {
            "categorical",
            "numeric",
            "timebucket",
            "diff",
            "string",
            "boolean",
        }
        for extractor in v:
            parts = extractor.split(":", 1)
            if len(parts) < 1:
                raise ValueError(f"Invalid extractor format: {extractor}")
            if parts[0] not in valid_types:
                raise ValueError(
                    f"Unknown extractor type: {parts[0]}. Valid types: {valid_types}"
                )
        return v


class ProfileSummary(BaseModel):
    """Summary information about a profile for discovery."""

    id: str
    title: str
    version: str
    description: str
