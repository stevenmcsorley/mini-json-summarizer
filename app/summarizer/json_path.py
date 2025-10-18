"""Helpers for JSONPath manipulation and citation sampling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Union

import orjson

VALUE_TYPE_NUMBER = "number"
VALUE_TYPE_STRING = "string"
VALUE_TYPE_BOOLEAN = "boolean"
VALUE_TYPE_NULL = "null"
VALUE_TYPE_OBJECT = "object"
VALUE_TYPE_ARRAY = "array"
VALUE_TYPE_ORDER = [
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_STRING,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_NULL,
    VALUE_TYPE_OBJECT,
    VALUE_TYPE_ARRAY,
]


def json_value_type(value: Any) -> str:
    if value is None:
        return VALUE_TYPE_NULL
    if isinstance(value, bool):
        return VALUE_TYPE_BOOLEAN
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return VALUE_TYPE_NUMBER
    if isinstance(value, str):
        return VALUE_TYPE_STRING
    if isinstance(value, list):
        return VALUE_TYPE_ARRAY
    if isinstance(value, dict):
        return VALUE_TYPE_OBJECT
    return VALUE_TYPE_OBJECT


PathPart = Union[str, int]


def _format_key(key: str) -> str:
    if not key:
        return "['']"
    simple = all(ch.isalnum() or ch == "_" for ch in key)
    if simple and not key[0].isdigit():
        return f".{key}"
    escaped = key.replace("'", "\\'")
    # Surround with ['...'] for complex keys
    return f"['{escaped}']"


def _format_index(index: int) -> str:
    return f"[{index}]"


def join_path(parts: Iterable[PathPart]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, str):
            path += _format_key(part)
        else:
            path += _format_index(part)
    return path


def append_path(base: str, part: PathPart) -> str:
    if not base:
        base = "$"
    if isinstance(part, str):
        return base + _format_key(part)
    return base + _format_index(part)


def wildcard(path: str) -> str:
    if path.endswith("]"):
        return f"{path[:-1]}*]"
    return f"{path}[*]"


def extend_path(base: str, parts: Iterable[PathPart]) -> str:
    result = base
    for part in parts:
        result = append_path(result, part)
    return result


def path_matches(candidate: str, pattern: str) -> bool:
    """
    Lightweight helper to compare JSONPath strings using fnmatch semantics.
    Supports *, ?, and ** wildcards operating on the string representation.
    """
    from fnmatch import fnmatchcase

    normalized_pattern = pattern.replace("**", "*")
    return fnmatchcase(candidate, normalized_pattern)


@dataclass(frozen=True)
class PathToken:
    kind: str
    value: Optional[Union[str, int]] = None


def parse_json_path(path: str) -> List[PathToken]:
    if not path or not path.startswith("$"):
        raise ValueError(f"Unsupported JSONPath: {path!r}")
    tokens: List[PathToken] = []
    i = 1
    length = len(path)

    while i < length:
        char = path[i]
        if char == ".":
            i += 1
            start = i
            while i < length and path[i] not in ".[":
                i += 1
            key = path[start:i]
            if key:
                tokens.append(PathToken(kind="key", value=key))
        elif char == "[":
            i += 1
            if i >= length:
                raise ValueError(f"Malformed JSONPath segment in {path!r}")
            if path[i] == "'":
                i += 1
                buffer: List[str] = []
                while i < length:
                    if path[i] == "\\" and i + 1 < length:
                        buffer.append(path[i + 1])
                        i += 2
                        continue
                    if path[i] == "'":
                        break
                    buffer.append(path[i])
                    i += 1
                if i >= length or path[i] != "'":
                    raise ValueError(f"Unclosed quoted key in JSONPath {path!r}")
                i += 1  # skip closing quote
                if i >= length or path[i] != "]":
                    raise ValueError(f"Missing closing bracket in JSONPath {path!r}")
                key = "".join(buffer)
                tokens.append(PathToken(kind="key", value=key))
                i += 1
            else:
                start = i
                while i < length and path[i] != "]":
                    i += 1
                if i >= length:
                    raise ValueError(f"Missing closing bracket in JSONPath {path!r}")
                content = path[start:i]
                if content == "*":
                    tokens.append(PathToken(kind="wildcard"))
                else:
                    try:
                        index = int(content)
                    except ValueError as exc:
                        raise ValueError(
                            f"Unsupported JSONPath index: {content!r}"
                        ) from exc
                    tokens.append(PathToken(kind="index", value=index))
                i += 1
        else:
            raise ValueError(f"Unexpected character {char!r} in JSONPath {path!r}")
    return tokens


def _iter_next_nodes(node: Any, token: PathToken) -> Iterator[Any]:
    if token.kind == "key":
        if isinstance(node, dict) and token.value in node:
            yield node[token.value]
    elif token.kind == "index":
        if isinstance(node, list):
            index = token.value
            if isinstance(index, int) and 0 <= index < len(node):
                yield node[index]
    elif token.kind == "wildcard":
        if isinstance(node, list):
            for item in node:
                yield item
        elif isinstance(node, dict):
            for item in node.values():
                yield item


def iter_path_values(
    payload: Any, tokens: Sequence[PathToken], limit: Optional[int] = None
) -> Iterator[Any]:
    current_nodes = [payload]

    for token in tokens:
        next_nodes: List[Any] = []
        for node in current_nodes:
            next_nodes.extend(_iter_next_nodes(node, token))
        if not next_nodes:
            return
        current_nodes = next_nodes

    count = 0
    for node in current_nodes:
        yield node
        count += 1
        if limit is not None and count >= limit:
            break


def _normalise_value(value: Any) -> Any:
    try:
        return orjson.loads(orjson.dumps(value))
    except orjson.JSONEncodeError:
        return value


def iter_values_by_path(
    payload: Any, path: str, limit: Optional[int] = None
) -> Iterator[Any]:
    tokens = parse_json_path(path)
    yield from iter_path_values(payload, tokens, limit=limit)


def collect_citation_examples(payload: Any, path: str, limit: int = 3) -> List[Any]:
    """
    Collect up to `limit` concrete JSON-compatible examples for the supplied path.
    """
    try:
        values = list(iter_values_by_path(payload, path, limit=limit))
    except ValueError:
        return []

    return [_normalise_value(value) for value in values]


def collect_typed_examples(
    payload: Any, path: str, limit_per_type: int = 3, sample_cap: int = 300
) -> List[Dict[str, Any]]:
    try:
        values_iter = iter_values_by_path(payload, path)
    except ValueError:
        return []

    examples: Dict[str, List[Any]] = {}
    for idx, value in enumerate(values_iter):
        if idx >= sample_cap:
            break
        value_type = json_value_type(value)
        bucket = examples.setdefault(value_type, [])
        if len(bucket) < limit_per_type:
            bucket.append(_normalise_value(value))

    typed_examples: List[Dict[str, Any]] = []
    for value_type in VALUE_TYPE_ORDER:
        bucket = examples.get(value_type, [])
        if bucket:
            typed_examples.append({"type": value_type, "examples": bucket})
    return typed_examples


def path_exists(payload: Any, path: str) -> bool:
    try:
        iterator = iter_values_by_path(payload, path, limit=1)
    except ValueError:
        return False
    return next(iterator, None) is not None
