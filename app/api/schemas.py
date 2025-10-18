# app/api/schemas.py
from typing import Any, Dict, List, Literal, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
    AliasChoices,  # <-- add this
)

EngineLiteral = Literal["deterministic", "llm", "hybrid"]
LengthLiteral = Literal["short", "medium", "long"]
StyleLiteral = Literal["bullets", "narrative", "kpi-block", "mixed"]


class SummarizeRequestModel(BaseModel):
    # keep ONE model_config
    model_config = ConfigDict(
        protected_namespaces=(), populate_by_name=True, extra="forbid"
    )

    # inline payload accepted as "json"
    payload: Optional[Any] = Field(
        default=None, alias="json", description="Inline JSON payload."
    )

    # accept BOTH "json_url" and "url" on input; serialize as "json_url"
    payload_url: Optional[HttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("json_url", "url"),
        serialization_alias="json_url",
        description="Remote JSON resource URL.",
    )

    focus: List[str] = Field(
        default_factory=list, description="Focus instructions or JSON paths."
    )
    engine: EngineLiteral = Field(
        default="deterministic"
    )  # <-- set to deterministic if that's current
    length: LengthLiteral = Field(default="medium")
    style: StyleLiteral = Field(default="bullets")
    template: Optional[str] = Field(default=None)

    # baseline (diff) support; accept both "baseline_url" and "baseline_json_url" if you like
    baseline_json: Optional[Any] = Field(default=None)
    baseline_url: Optional[HttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("baseline_url", "baseline_json_url"),
        serialization_alias="baseline_url",
    )

    stream: bool = Field(default=True, description="Emit Server-Sent Events when true.")
    disable_redaction: bool = Field(default=False)
    include_root_summary: bool = Field(default=False)

    @model_validator(mode="after")
    def ensure_payload_source(self) -> "SummarizeRequestModel":
        if self.payload is None and self.payload_url is None:
            raise ValueError(
                "Either `json` (inline) or `json_url`/`url` must be provided."
            )
        return self

    @field_validator("focus", mode="before")
    @classmethod
    def normalize_focus(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]


class CitationModel(BaseModel):
    path: str
    value_preview: List[Any] = Field(default_factory=list)
    value_preview_typed: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, citation) -> "CitationModel":
        return cls(
            path=citation.path,
            value_preview=list(citation.value_preview),
            value_preview_typed=list(citation.value_preview_typed),
        )


class SummaryBulletModel(BaseModel):
    text: str
    citations: List[CitationModel] = Field(default_factory=list)
    evidence: Any = None

    @classmethod
    def from_domain(cls, bullet) -> "SummaryBulletModel":
        return cls(
            text=bullet.text,
            citations=[CitationModel.from_domain(c) for c in bullet.citations],
            evidence=bullet.evidence,
        )


class SummaryResponseModel(BaseModel):
    engine: str
    focus: List[str]
    redactions_applied: bool
    bullets: List[SummaryBulletModel]
    evidence_stats: Dict[str, int]


class ChatMessageModel(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequestModel(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(), populate_by_name=True, extra="forbid"
    )

    messages: List[ChatMessageModel]

    # inline JSON as "json"
    payload: Optional[Any] = Field(default=None, alias="json")

    # accept BOTH "json_url" and "url"
    payload_url: Optional[HttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("json_url", "url"),
        serialization_alias="json_url",
    )

    focus: List[str] = Field(default_factory=list)
    engine: EngineLiteral = Field(default="deterministic")
    length: LengthLiteral = Field(default="medium")
    style: StyleLiteral = Field(default="mixed")
    template: Optional[str] = None
    include_root_summary: bool = Field(default=False)

    @field_validator("focus", mode="before")
    @classmethod
    def normalize_focus(cls, value: Any) -> List[str]:
        return SummarizeRequestModel.normalize_focus(value)

    @model_validator(mode="after")
    def ensure_messages(self) -> "ChatRequestModel":
        if not self.messages:
            raise ValueError("At least one message is required.")
        return self


class ChatResponseModel(BaseModel):
    reply: str
    engine: str
    bullets: List[SummaryBulletModel]
    evidence_stats: Dict[str, int]
