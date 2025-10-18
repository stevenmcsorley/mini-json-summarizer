from functools import lru_cache
from typing import List, Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Centralized application settings leveraging environment overrides.
    """

    app_name: str = "Mini JSON Summarizer"
    environment: str = Field("local", validation_alias="ENVIRONMENT")
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    max_payload_bytes: int = Field(20 * 1024 * 1024, ge=1024)  # 20 MB soft limit
    pii_redaction_enabled: bool = True
    pii_email_regex: str = r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"
    pii_phone_regex: str = (
        r"(?<!\d)(?:\+?\d{1,2}\s?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}(?!\d)"
    )
    pii_credit_card_regex: str = r"(?<!\d)(?:\d[ -]*?){13,16}(?!\d)"
    redact_token: str = "[REDACTED]"
    redaction_path_denylist: List[str] = Field(
        default_factory=lambda: ["$.access_token", "$..password", "$..secret"]
    )
    deterministic_topk: int = Field(3, ge=1)
    deterministic_numeric_fields_limit: int = Field(15, ge=1)
    deterministic_string_cardinality_limit: int = Field(15, ge=1)
    streaming_chunk_delay_ms: int = Field(100, ge=0)
    evidence_schema_url: Optional[HttpUrl] = None
    max_json_depth: int = Field(64, ge=1)

    # LLM settings
    llm_provider: str = Field("none", description="LLM provider: none, openai, anthropic")
    llm_model: Optional[str] = Field(None, description="Model name for LLM provider")
    openai_api_key: Optional[str] = Field(None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, validation_alias="ANTHROPIC_API_KEY")
    llm_max_tokens: int = Field(1500, ge=100, le=4000)
    llm_temperature: float = Field(0.1, ge=0.0, le=2.0)
    llm_fallback_to_deterministic: bool = Field(True, description="Fallback on LLM failure")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
