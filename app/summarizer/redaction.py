"""Redaction utilities applied prior to summarization."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable, List, Tuple

from .json_path import append_path, path_matches
from app.config import Settings


RegexPattern = re.Pattern[str]


@lru_cache
def _compile_regex(pattern: str) -> RegexPattern:
    return re.compile(pattern)


def _compile_patterns(patterns: Iterable[str]) -> List[RegexPattern]:
    return [_compile_regex(pattern) for pattern in patterns if pattern]


def apply_redactions(payload: Any, settings: Settings) -> Tuple[Any, bool, List[str]]:
    """
    Redacts sensitive values from the payload according to regex and JSONPath policies.
    Returns a tuple of (sanitized_payload, redactions_applied, paths_redacted).
    """

    if not settings.pii_redaction_enabled:
        return payload, False, []

    regex_patterns = _compile_patterns(
        [
            settings.pii_email_regex,
            settings.pii_phone_regex,
            settings.pii_credit_card_regex,
        ]
    )
    denylist = tuple(settings.redaction_path_denylist)

    redacted_paths: List[str] = []

    def _sanitize(value: Any, path: str) -> Any:
        nonlocal redacted_paths

        for deny in denylist:
            if path_matches(path, deny):
                redacted_paths.append(path)
                return settings.redact_token

        if isinstance(value, str):
            for pattern in regex_patterns:
                if pattern.search(value):
                    redacted_paths.append(path)
                    return settings.redact_token
            return value

        if isinstance(value, list):
            result = []
            for index, item in enumerate(value):
                child_path = append_path(path, index)
                result.append(_sanitize(item, child_path))
            return result

        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                child_path = append_path(path, key)
                result[key] = _sanitize(item, child_path)
            return result

        return value

    sanitized = _sanitize(payload, "$")
    return sanitized, bool(redacted_paths), redacted_paths
