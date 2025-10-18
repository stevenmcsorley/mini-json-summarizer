from __future__ import annotations

"""Domain models shared across summarization engines."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


LengthOption = Literal["short", "medium", "long"]
StyleOption = Literal["bullets", "narrative", "kpi-block", "mixed"]
EngineOption = Literal["deterministic", "llm", "hybrid"]


@dataclass(slots=True)
class Citation:
    path: str
    value_preview: List[Any] = field(default_factory=list)
    value_preview_typed: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class SummaryBullet:
    text: str
    citations: List[Citation] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceBundle:
    bullets: List[SummaryBullet]
    engine: EngineOption
    focus: List[str]
    redactions_applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SummarizationRequest:
    payload: Any
    focus: List[str] = field(default_factory=list)
    engine: EngineOption = "hybrid"
    length: LengthOption = "medium"
    style: StyleOption = "bullets"
    template: Optional[str] = None
    baseline_payload: Optional[Any] = None
    include_root_summary: bool = False
