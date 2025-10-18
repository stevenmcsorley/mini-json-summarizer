"""Deterministic summarization engine implementation."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.config import Settings
from app.summarizer.engines.base import SummarizationEngine
from app.summarizer.json_path import (
    VALUE_TYPE_ARRAY,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_NULL,
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_OBJECT,
    VALUE_TYPE_ORDER,
    VALUE_TYPE_STRING,
    append_path,
    collect_citation_examples,
    collect_typed_examples,
    json_value_type,
)
from app.summarizer.models import (
    Citation,
    EvidenceBundle,
    SummaryBullet,
    SummarizationRequest,
)
from app.summarizer.redaction import apply_redactions


MAX_BULLETS_BY_LENGTH = {"short": 4, "medium": 8, "long": 12}

NUMERIC_DOMINANCE_THRESHOLD = 0.8
BOOL_AS_NUMERIC = False


def plural(count: int, noun: str) -> str:
    """Return a pluralized string for the given count and noun."""
    suffix = noun if count == 1 else f"{noun}s"
    return f"{count} {suffix}"


def _format_sum(value: float) -> str:
    if not math.isfinite(value):
        return "0"
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.1f}"


def _format_avg(value: float) -> str:
    if not math.isfinite(value):
        return "0.00"
    return f"{value:.2f}"


def _format_extreme(value: float) -> str:
    if not math.isfinite(value):
        return "0"
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.1f}"


def _tokenize(text: str) -> List[str]:
    return [token for token in text.lower().replace("_", " ").split() if token]


@dataclass(slots=True)
class FocusScoredBullet:
    bullet: SummaryBullet
    focus_score: int = 0
    priority: int = 0


@dataclass(slots=True)
class NumericAccumulator:
    count: int = 0
    total: float = 0.0
    minimum: float = field(default_factory=lambda: math.inf)
    maximum: float = field(default_factory=lambda: -math.inf)

    def ingest(self, value: float) -> None:
        self.count += 1
        self.total += value
        if value < self.minimum:
            self.minimum = value
        if value > self.maximum:
            self.maximum = value

    def render(self) -> Dict[str, float]:
        average = self.total / self.count if self.count else 0.0
        return {
            "count": self.count,
            "sum": self.total,
            "min": self.minimum if self.minimum != math.inf else 0.0,
            "max": self.maximum if self.maximum != -math.inf else 0.0,
            "avg": average,
        }


@dataclass(slots=True)
class FieldSummary:
    inline_text: str
    detail_lines: List[str]
    evidence: Dict[str, Any]
    citation_paths: List[str]


class FieldAggregator:
    def __init__(self, field_name: str, settings: Settings) -> None:
        self.field_name = field_name
        self.settings = settings
        self.type_counts: Counter[str] = Counter()
        self.numeric_acc = NumericAccumulator()
        self.string_counter: Counter[str] = Counter()
        self.boolean_counts: Dict[str, int] = {"true": 0, "false": 0}

    def ingest(self, value: Any) -> None:
        value_type = json_value_type(value)
        self.type_counts[value_type] += 1
        if value_type == VALUE_TYPE_NUMBER:
            self.numeric_acc.ingest(float(value))
        elif value_type == VALUE_TYPE_STRING:
            self.string_counter[str(value)] += 1
        elif value_type == VALUE_TYPE_BOOLEAN:
            if bool(value):
                self.boolean_counts["true"] += 1
            else:
                self.boolean_counts["false"] += 1

    def has_values(self) -> bool:
        return any(self.type_counts.values())

    def build_summary(self, array_path: str, length: str) -> FieldSummary:
        type_counts_ordered = {
            value_type: self.type_counts[value_type]
            for value_type in VALUE_TYPE_ORDER
            if self.type_counts.get(value_type)
        }
        non_null_types = [
            VALUE_TYPE_NUMBER,
            VALUE_TYPE_STRING,
            VALUE_TYPE_BOOLEAN,
            VALUE_TYPE_OBJECT,
            VALUE_TYPE_ARRAY,
        ]
        non_null_total = sum(
            self.type_counts.get(value_type, 0) for value_type in non_null_types
        )
        number_count = self.type_counts.get(VALUE_TYPE_NUMBER, 0)
        string_count = self.type_counts.get(VALUE_TYPE_STRING, 0)
        boolean_count = self.type_counts.get(VALUE_TYPE_BOOLEAN, 0)
        object_count = self.type_counts.get(VALUE_TYPE_OBJECT, 0)
        array_count = self.type_counts.get(VALUE_TYPE_ARRAY, 0)
        null_count = self.type_counts.get(VALUE_TYPE_NULL, 0)

        field_evidence: Dict[str, Any] = {"type_counts": type_counts_ordered}
        detail_lines: List[str] = []
        field_path = append_path(array_path, self.field_name)
        citation_paths: set[str] = set()

        numeric_mode = (
            number_count > 0
            and non_null_total > 0
            and number_count / non_null_total >= NUMERIC_DOMINANCE_THRESHOLD
            and string_count == 0
            and object_count == 0
            and array_count == 0
            and (BOOL_AS_NUMERIC or boolean_count == 0)
        )

        observed_non_null = [
            value_type
            for value_type in non_null_types
            if self.type_counts.get(value_type, 0) > 0
        ]

        if numeric_mode:
            stats = self.numeric_acc.render()
            inline_text = (
                f"{self.field_name}: sum {_format_sum(stats['sum'])}, "
                f"avg {_format_avg(stats['avg'])}, "
                f"min {_format_extreme(stats['min'])}, "
                f"max {_format_extreme(stats['max'])}"
            )
            field_evidence["number"] = stats
            if null_count:
                field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        if (
            string_count > 0
            and not number_count
            and not boolean_count
            and not object_count
            and not array_count
        ):
            top = self.string_counter.most_common(self.settings.deterministic_topk)
            formatted = ", ".join(
                f"{json.dumps(value)} ({count})" for value, count in top
            )
            inline_text = f"{self.field_name}: {formatted or '�'}"
            field_evidence["string"] = {"top": top}
            if null_count:
                field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        if (
            boolean_count > 0
            and not number_count
            and not string_count
            and not object_count
            and not array_count
        ):
            inline_text = (
                f"{self.field_name}: true ({self.boolean_counts['true']}), "
                f"false ({self.boolean_counts['false']})"
            )
            field_evidence["boolean"] = {
                "true": self.boolean_counts["true"],
                "false": self.boolean_counts["false"],
            }
            if null_count:
                field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        if not observed_non_null:
            inline_text = f"{self.field_name}: null ({null_count})"
            field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        if len(observed_non_null) == 1 and observed_non_null[0] == VALUE_TYPE_OBJECT:
            inline_text = f"{self.field_name}: object ({object_count})"
            if null_count:
                field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        if len(observed_non_null) == 1 and observed_non_null[0] == VALUE_TYPE_ARRAY:
            inline_text = f"{self.field_name}: array ({array_count})"
            if null_count:
                field_evidence["null"] = {"count": null_count}
            return FieldSummary(
                inline_text, detail_lines, field_evidence, citation_paths
            )

        counts_summary_parts = [
            f"{value_type}({type_counts_ordered[value_type]})"
            for value_type in VALUE_TYPE_ORDER
            if value_type in type_counts_ordered and value_type != VALUE_TYPE_NULL
        ]
        if null_count:
            counts_summary_parts.append(f"null({null_count})")
        counts_summary = ", ".join(counts_summary_parts)
        inline_text = (
            f"{self.field_name} - mixed types detected: {counts_summary or 'n/a'}"
        )

        if number_count:
            stats = self.numeric_acc.render()
            field_evidence["number"] = stats
            detail_lines.append(
                "- numbers: "
                f"sum {_format_sum(stats['sum'])}, "
                f"avg {_format_avg(stats['avg'])}, "
                f"min {_format_extreme(stats['min'])}, "
                f"max {_format_extreme(stats['max'])}"
            )
        if string_count:
            top = self.string_counter.most_common(self.settings.deterministic_topk)
            field_evidence["string"] = {"top": top}
            detail_lines.append(
                "- strings: "
                + ", ".join(f"{json.dumps(value)} ({count})" for value, count in top)
            )
        if boolean_count:
            field_evidence["boolean"] = {
                "true": self.boolean_counts["true"],
                "false": self.boolean_counts["false"],
            }
            detail_lines.append(
                "- booleans: "
                f"true ({self.boolean_counts['true']}), "
                f"false ({self.boolean_counts['false']})"
            )
        if null_count:
            field_evidence["null"] = {"count": null_count}
            detail_lines.append(f"- null: {null_count}")
        if object_count:
            detail_lines.append(f"- objects: {object_count}")
        if array_count:
            detail_lines.append(f"- arrays: {array_count}")

        return FieldSummary(inline_text, detail_lines, field_evidence, citation_paths)


class ArrayOfObjectsAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.count = 0
        self.field_aggregators: Dict[str, FieldAggregator] = {}

    def ingest(self, record: Dict[str, Any]) -> None:
        self.count += 1
        for key, value in record.items():
            aggregator = self.field_aggregators.setdefault(
                key, FieldAggregator(key, self.settings)
            )
            aggregator.ingest(value)

    def has_data(self) -> bool:
        return self.count > 0

    def render(
        self,
        title: str,
        array_path: str,
        length: str,
        focus_tokens: List[str],
    ) -> FocusScoredBullet:
        inline_parts = [f"{title}: {plural(self.count, 'record')}"]
        detail_lines: List[str] = []
        evidence: Dict[str, Any] = {"records": self.count}
        base_path = array_path[:-3] if array_path.endswith("[*]") else array_path
        citation_paths: set[str] = set()

        for field_name in sorted(self.field_aggregators):
            aggregator = self.field_aggregators[field_name]
            if not aggregator.has_values():
                continue
            summary = aggregator.build_summary(array_path, length)
            if summary.inline_text:
                inline_parts.append(summary.inline_text)
            if summary.detail_lines:
                detail_lines.extend(summary.detail_lines)
            if summary.evidence:
                evidence[field_name] = summary.evidence
            citation_paths.update(summary.citation_paths)

        bullet_text = "; ".join(inline_parts)
        if detail_lines:
            bullet_text += "\n  " + "\n  ".join(detail_lines)

        bullet = SummaryBullet(
            text=bullet_text,
            citations=[Citation(path=path) for path in sorted(citation_paths)],
            evidence=evidence,
        )
        focus_score = _score_focus(bullet.text, focus_tokens, title)
        return FocusScoredBullet(bullet=bullet, focus_score=focus_score)


def _score_focus(
    text: str, focus_tokens: List[str], title: Optional[str] = None
) -> int:
    if not focus_tokens:
        return 0
    tokens = _tokenize(text)
    if title:
        tokens.extend(_tokenize(title))
    text_set = set(tokens)
    return sum(1 for token in focus_tokens if token in text_set)


class DeterministicSummarizer:
    def __init__(
        self,
        settings: Settings,
        length: str,
        focus_tokens: List[str],
        include_root_summary: bool,
    ) -> None:
        self.settings = settings
        self.length = length if length in MAX_BULLETS_BY_LENGTH else "medium"
        self.focus_tokens = focus_tokens
        self.candidate_bullets: List[FocusScoredBullet] = []
        self.include_root_summary = include_root_summary

    def summarize(
        self, value: Any, path: str = "$", title: Optional[str] = None
    ) -> None:
        if isinstance(value, dict):
            self._summarize_dict(value, path, title)
        elif isinstance(value, list):
            self._summarize_list(value, path, title)
        else:
            self._summarize_scalar(value, path, title)

    def _summarize_dict(
        self, node: Dict[str, Any], path: str, title: Optional[str]
    ) -> None:
        title = title or ("Root object" if path == "$" else path.split(".")[-1])
        keys = list(node.keys())
        evidence = {"keys": keys}
        bullet_text = f"{title}: object with {len(keys)} keys"
        if keys:
            key_preview = ", ".join(keys[: self.settings.deterministic_topk])
            if len(keys) > self.settings.deterministic_topk:
                key_preview += ", ..."
            bullet_text += f" (sample: {key_preview})"
        if path != "$" or self.include_root_summary:
            bullet = SummaryBullet(
                text=bullet_text,
                citations=[Citation(path=path)],
                evidence=evidence,
            )
            focus_score = _score_focus(bullet.text, self.focus_tokens, title)
            self.candidate_bullets.append(
                FocusScoredBullet(bullet=bullet, focus_score=focus_score)
            )

        for key, value in node.items():
            child_path = append_path(path, key)
            self.summarize(value, child_path, title=key)

    def _summarize_list(self, node: List[Any], path: str, title: Optional[str]) -> None:
        title = title or ("Root array" if path == "$" else path.split(".")[-1])
        bullet_intro = f"{title}: array with {plural(len(node), 'item')}"
        citations = [Citation(path=path)]
        evidence = {"count": len(node)}

        if not node:
            bullet = SummaryBullet(
                text=bullet_intro, citations=citations, evidence=evidence
            )
            focus_score = _score_focus(bullet.text, self.focus_tokens, title)
            self.candidate_bullets.append(
                FocusScoredBullet(bullet=bullet, focus_score=focus_score)
            )
            return

        if all(isinstance(item, dict) for item in node):
            analyzer = ArrayOfObjectsAnalyzer(self.settings)
            for record in node:
                analyzer.ingest(record)
            if analyzer.has_data():
                array_path = f"{path}[*]"
                focus_bullet = analyzer.render(
                    title, array_path, self.length, self.focus_tokens
                )
                self.candidate_bullets.append(focus_bullet)
                return

        sample_values = node[: self.settings.deterministic_topk]
        preview = ", ".join(repr(value)[:60] for value in sample_values)
        if len(node) > self.settings.deterministic_topk:
            preview += ", ..."
        bullet_text = f"{bullet_intro} (sample: {preview})"
        bullet = SummaryBullet(text=bullet_text, citations=citations, evidence=evidence)
        focus_score = _score_focus(bullet.text, self.focus_tokens, title)
        self.candidate_bullets.append(
            FocusScoredBullet(bullet=bullet, focus_score=focus_score)
        )

        for index, value in enumerate(node):
            child_path = append_path(path, index)
            self.summarize(value, child_path, title=f"{title}[{index}]")

    def _summarize_scalar(self, value: Any, path: str, title: Optional[str]) -> None:
        title = title or path
        bullet_text = f"{title}: {value!r}"
        bullet = SummaryBullet(
            text=bullet_text,
            citations=[Citation(path=path)],
            evidence={"value": value},
        )
        focus_score = _score_focus(bullet_text, self.focus_tokens, title)
        self.candidate_bullets.append(
            FocusScoredBullet(bullet=bullet, focus_score=focus_score)
        )

    def render(self) -> List[SummaryBullet]:
        max_bullets = MAX_BULLETS_BY_LENGTH.get(
            self.length, MAX_BULLETS_BY_LENGTH["medium"]
        )
        sorted_bullets = sorted(
            self.candidate_bullets,
            key=lambda candidate: (-candidate.focus_score, len(candidate.bullet.text)),
        )
        top_bullets = sorted_bullets[:max_bullets]
        return [candidate.bullet for candidate in top_bullets]


class DeltaSummarizer:
    def __init__(self, settings: Settings, focus_tokens: List[str]) -> None:
        self.settings = settings
        self.focus_tokens = focus_tokens

    def summarize(self, baseline: Any, current: Any) -> Optional[SummaryBullet]:
        if isinstance(baseline, dict) and isinstance(current, dict):
            return self._summarize_dict_delta(baseline, current)
        if isinstance(baseline, list) and isinstance(current, list):
            return self._summarize_list_delta(baseline, current)
        if baseline != current:
            text = f"Root changed from {baseline!r} to {current!r}"
            bullet = SummaryBullet(
                text=text,
                citations=[Citation(path="$")],
                evidence={"baseline": baseline, "current": current},
            )
            return bullet
        return None

    def _summarize_dict_delta(
        self, baseline: Dict[str, Any], current: Dict[str, Any]
    ) -> Optional[SummaryBullet]:
        added = sorted(set(current.keys()) - set(baseline.keys()))
        removed = sorted(set(baseline.keys()) - set(current.keys()))
        intersecting = set(current.keys()) & set(baseline.keys())
        changed = []
        for key in intersecting:
            if baseline[key] != current[key]:
                changed.append(key)

        if not any([added, removed, changed]):
            return None

        segments = []
        if added:
            segments.append(
                f"added keys: {', '.join(added[: self.settings.deterministic_topk])}"
            )
        if removed:
            segments.append(
                f"removed keys: {', '.join(removed[: self.settings.deterministic_topk])}"
            )
        if changed:
            segments.append(
                f"modified keys: {', '.join(changed[: self.settings.deterministic_topk])}"
            )

        bullet = SummaryBullet(
            text="Delta: " + "; ".join(segments),
            citations=[Citation(path="$")],
            evidence={
                "added": added,
                "removed": removed,
                "changed": changed,
            },
        )
        return bullet

    def _summarize_list_delta(
        self, baseline: List[Any], current: List[Any]
    ) -> Optional[SummaryBullet]:
        if len(baseline) == len(current) and baseline == current:
            return None
        added = len(current) - len(baseline)
        evidence = {
            "baseline_length": len(baseline),
            "current_length": len(current),
        }
        text = f"Delta: array length changed from {len(baseline)} to {len(current)}"
        if added > 0:
            text += f" (+{added})"
        elif added < 0:
            text += f" ({added})"
        bullet = SummaryBullet(
            text=text,
            citations=[Citation(path="$")],
            evidence=evidence,
        )
        return bullet


class DeterministicEngine(SummarizationEngine):
    name = "deterministic"

    def summarize(
        self, request: SummarizationRequest, settings: Settings
    ) -> EvidenceBundle:
        redacted_paths: List[str] = []
        sanitized_payload, redactions_applied, payload_redacted_paths = (
            apply_redactions(request.payload, settings)
        )
        redacted_paths.extend(payload_redacted_paths)

        baseline_payload = None
        if request.baseline_payload is not None:
            baseline_payload, baseline_redactions, baseline_redacted_paths = (
                apply_redactions(request.baseline_payload, settings)
            )
            redactions_applied = redactions_applied or baseline_redactions
            redacted_paths.extend(baseline_redacted_paths)
        focus_tokens = self._normalize_focus(request.focus)
        summarizer = DeterministicSummarizer(
            settings,
            request.length,
            focus_tokens,
            request.include_root_summary,
        )
        summarizer.summarize(sanitized_payload, path="$")
        bullets = summarizer.render()

        if request.baseline_payload is not None:
            delta = DeltaSummarizer(settings, focus_tokens)
            delta_bullet = delta.summarize(baseline_payload, sanitized_payload)
            if delta_bullet:
                bullets.append(delta_bullet)

        if redactions_applied:
            unique_paths = list(dict.fromkeys(redacted_paths))
            bullets.append(
                SummaryBullet(
                    text=f"{len(redacted_paths)} sensitive value(s) redacted prior to summarization.",
                    citations=[
                        Citation(path=path, value_preview=[settings.redact_token])
                        for path in unique_paths[:3]
                    ],
                    evidence={"redacted_paths": redacted_paths},
                )
            )

        payload_sources: List[Any] = [sanitized_payload]
        if baseline_payload is not None:
            payload_sources.append(baseline_payload)
        _attach_citation_previews(bullets, payload_sources)

        metadata = {
            "payload": sanitized_payload,
            "baseline": baseline_payload,
        }

        return EvidenceBundle(
            bullets=bullets,
            engine="deterministic",
            focus=request.focus,
            redactions_applied=redactions_applied,
            metadata=metadata,
        )

    @staticmethod
    def _normalize_focus(focus: Iterable[str]) -> List[str]:
        tokens: List[str] = []
        for item in focus:
            tokens.extend(_tokenize(item))
        return tokens


def _attach_citation_previews(
    bullets: List[SummaryBullet], payloads: List[Any]
) -> None:
    for bullet in bullets:
        unique: Dict[str, Citation] = {}
        for citation in bullet.citations:
            unique.setdefault(citation.path, citation)
        bullet.citations = list(unique.values())
        for citation in bullet.citations:
            if not citation.value_preview:
                for payload in payloads:
                    preview = collect_citation_examples(payload, citation.path, limit=3)
                    if preview:
                        citation.value_preview = preview
                        break
            if not citation.value_preview_typed:
                for payload in payloads:
                    typed_preview = collect_typed_examples(payload, citation.path)
                    if typed_preview:
                        citation.value_preview_typed = typed_preview
                        break
