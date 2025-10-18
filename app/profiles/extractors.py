"""Profile-specific extractors for targeted data extraction."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from app.summarizer.json_path import iter_path_values
from app.summarizer.models import Citation, SummaryBullet

logger = logging.getLogger(__name__)


def _iter_all_field_values(payload: Any, parent_path: str = "$") -> Iterator[Tuple[str, Any]]:
    """
    Recursively iterate over all fields in a JSON payload.

    Yields:
        (path, value) tuples for every field in the JSON structure
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            field_path = f"{parent_path}.{key}"
            yield (field_path, value)
            # Recurse into nested structures
            yield from _iter_all_field_values(value, field_path)
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            item_path = f"{parent_path}[{idx}]"
            # Recurse into list items
            yield from _iter_all_field_values(item, item_path)


class ProfileExtractor:
    """Base class for profile-specific extractors."""

    def __init__(
        self, extractor_spec: str, payload: Any, baseline: Optional[Any] = None
    ):
        """
        Initialize extractor.

        Args:
            extractor_spec: Extractor specification (e.g., "categorical:level")
            payload: JSON payload to extract from
            baseline: Optional baseline payload for diff operations
        """
        self.extractor_spec = extractor_spec
        self.payload = payload
        self.baseline = baseline
        self.parts = extractor_spec.split(":", maxsplit=2)
        self.extractor_type = self.parts[0]
        self.field_name = self.parts[1] if len(self.parts) > 1 else None

    def extract(self) -> List[SummaryBullet]:
        """
        Extract bullets from payload.

        Returns:
            List of summary bullets with citations
        """
        raise NotImplementedError


class CategoricalExtractor(ProfileExtractor):
    """Extract categorical/string field distributions."""

    def extract(self) -> List[SummaryBullet]:
        """Extract categorical distribution for a specific field."""
        if not self.field_name:
            return []

        # Find all values for this field
        values = []
        paths = []

        for path, value in _iter_all_field_values(self.payload):
            # Match field name at end of path
            if path.endswith(f".{self.field_name}"):
                if isinstance(value, (str, int, bool)):
                    values.append(str(value))
                    paths.append(path)

        if not values:
            return []

        # Count frequencies
        freq = defaultdict(int)
        for v in values:
            freq[v] += 1

        # Sort by frequency
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        # Filter low counts (suppress if max count < 2)
        if sorted_freq and sorted_freq[0][1] < 2:
            return []

        # Build top-K summary
        top_items = sorted_freq[:5]  # Top 5
        total_count = len(values)

        if len(sorted_freq) > 10:  # High cardinality
            text = f"{self.field_name}: high-cardinality ({len(sorted_freq)} unique values), no dominant values"
        else:
            items_str = ", ".join([f'"{k}" ({v})' for k, v in top_items])
            text = f"{self.field_name}: {items_str} | total: {total_count}"

        # Create unique citations
        unique_paths = list(set(paths))[:3]  # Limit to 3 example paths
        citations = [Citation(path=p) for p in unique_paths]

        evidence = {
            "field": self.field_name,
            "total_count": total_count,
            "unique_values": len(sorted_freq),
            "top": [[k, v] for k, v in top_items],
        }

        return [SummaryBullet(text=text, citations=citations, evidence=evidence)]


class NumericExtractor(ProfileExtractor):
    """Extract numeric field statistics."""

    NUMERIC_DOMINANCE_THRESHOLD = 0.8

    def extract(self) -> List[SummaryBullet]:
        """Extract numeric statistics for a specific field."""
        if not self.field_name:
            return []

        # Find all values for this field
        values = []
        paths = []
        non_numeric_count = 0

        for path, value in _iter_all_field_values(self.payload):
            if path.endswith(f".{self.field_name}"):
                # Strict numeric type checking - no bool→int coercion
                if isinstance(value, bool):
                    non_numeric_count += 1
                elif isinstance(value, (int, float)):
                    values.append(float(value))
                    paths.append(path)
                else:
                    non_numeric_count += 1

        if not values:
            return []

        # Check numeric dominance
        total = len(values) + non_numeric_count
        if total > 0 and (len(values) / total) < self.NUMERIC_DOMINANCE_THRESHOLD:
            logger.debug(
                f"Field {self.field_name} has mixed types, skipping numeric extraction"
            )
            return []

        # Calculate statistics
        count = len(values)
        total_sum = sum(values)
        mean = total_sum / count
        min_val = min(values)
        max_val = max(values)

        text = f"{self.field_name}: count={count}, mean={mean:.2f}, min={min_val:.2f}, max={max_val:.2f}, sum={total_sum:.2f}"

        # Create unique citations
        unique_paths = list(set(paths))[:3]
        citations = [Citation(path=p) for p in unique_paths]

        evidence = {
            "field": self.field_name,
            "count": count,
            "sum": total_sum,
            "mean": mean,
            "min": min_val,
            "max": max_val,
        }

        return [SummaryBullet(text=text, citations=citations, evidence=evidence)]


class TimebucketExtractor(ProfileExtractor):
    """Extract time-based buckets and distributions."""

    def extract(self) -> List[SummaryBullet]:
        """Extract time bucket distribution."""
        if len(self.parts) < 3:
            return []

        field_name = self.parts[1]
        bucket_size = self.parts[2]  # minute, hour, day

        # Find all timestamp values
        timestamps = []
        paths = []

        for path, value in _iter_all_field_values(self.payload):
            if path.endswith(f".{field_name}"):
                if isinstance(value, str):
                    try:
                        # Try parsing ISO format timestamps
                        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        timestamps.append(dt)
                        paths.append(path)
                    except (ValueError, AttributeError):
                        pass

        if not timestamps:
            return []

        # Bucket timestamps
        buckets = defaultdict(int)
        for ts in timestamps:
            if bucket_size == "minute":
                bucket_key = ts.strftime("%Y-%m-%d %H:%M")
            elif bucket_size == "hour":
                bucket_key = ts.strftime("%Y-%m-%d %H:00")
            elif bucket_size == "day":
                bucket_key = ts.strftime("%Y-%m-%d")
            else:
                bucket_key = ts.strftime("%Y-%m-%d %H:%M")

            buckets[bucket_key] += 1

        # Get top buckets
        sorted_buckets = sorted(buckets.items(), key=lambda x: x[1], reverse=True)
        top_buckets = sorted_buckets[:5]

        buckets_str = ", ".join([f"{k} ({v})" for k, v in top_buckets])
        text = f"{field_name} ({bucket_size} buckets): {buckets_str} | total events: {len(timestamps)}"

        unique_paths = list(set(paths))[:3]
        citations = [Citation(path=p) for p in unique_paths]

        evidence = {
            "field": field_name,
            "bucket_size": bucket_size,
            "total_events": len(timestamps),
            "unique_buckets": len(buckets),
            "top_buckets": [[k, v] for k, v in top_buckets],
        }

        return [SummaryBullet(text=text, citations=citations, evidence=evidence)]


class DiffExtractor(ProfileExtractor):
    """Extract differences between payload and baseline."""

    def extract(self) -> List[SummaryBullet]:
        """Extract diff between payload and baseline."""
        if not self.baseline:
            return []

        # Simple diff: compare keys at root level
        def get_keys(obj: Any, prefix: str = "$") -> Set[str]:
            """Get all keys/paths in object."""
            keys = set()
            if isinstance(obj, dict):
                for k, v in obj.items():
                    path = f"{prefix}.{k}"
                    keys.add(path)
                    keys.update(get_keys(v, path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    path = f"{prefix}[{i}]"
                    keys.update(get_keys(item, path))
            return keys

        current_keys = get_keys(self.payload)
        baseline_keys = get_keys(self.baseline)

        added = current_keys - baseline_keys
        removed = baseline_keys - current_keys

        if not added and not removed:
            text = "No changes detected from baseline"
            citations = []
            evidence = {"added": 0, "removed": 0}
        else:
            added_sample = list(added)[:3]
            removed_sample = list(removed)[:3]

            text_parts = []
            if added:
                text_parts.append(
                    f"added {len(added)} paths (e.g., {', '.join(added_sample)})"
                )
            if removed:
                text_parts.append(
                    f"removed {len(removed)} paths (e.g., {', '.join(removed_sample)})"
                )

            text = f"Baseline diff: {'; '.join(text_parts)}"

            citations = [Citation(path=p) for p in (added_sample + removed_sample)]

            evidence = {
                "added": len(added),
                "removed": len(removed),
                "added_paths": list(added)[:10],
                "removed_paths": list(removed)[:10],
            }

        return [SummaryBullet(text=text, citations=citations, evidence=evidence)]


def extract_with_profile_extractors(
    extractors: List[str],
    payload: Any,
    baseline: Optional[Any] = None,
) -> List[SummaryBullet]:
    """
    Run profile-specific extractors on payload.

    Args:
        extractors: List of extractor specifications
        payload: JSON payload
        baseline: Optional baseline for diff

    Returns:
        List of summary bullets from all extractors
    """
    bullets = []

    for extractor_spec in extractors:
        try:
            parts = extractor_spec.split(":", 1)
            extractor_type = parts[0]

            if extractor_type == "categorical":
                extractor = CategoricalExtractor(extractor_spec, payload, baseline)
            elif extractor_type == "numeric":
                extractor = NumericExtractor(extractor_spec, payload, baseline)
            elif extractor_type == "timebucket":
                extractor = TimebucketExtractor(extractor_spec, payload, baseline)
            elif extractor_type == "diff":
                extractor = DiffExtractor(extractor_spec, payload, baseline)
            else:
                logger.warning(f"Unknown extractor type: {extractor_type}")
                continue

            extractor_bullets = extractor.extract()
            bullets.extend(extractor_bullets)

        except Exception as e:
            logger.error(f"Error in extractor {extractor_spec}: {e}", exc_info=True)
            continue

    return bullets
