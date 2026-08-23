import re
from typing import Any

import pytest
from syrupy.extensions.json import JSONSnapshotExtension
from syrupy.matchers import path_type

PathTypeMap = dict[str, tuple[type, ...]]


@pytest.fixture
def snapshot_json(snapshot):
    """`snapshot` fixture pinned to `JSONSnapshotExtension` — every
    `.json` snapshot in this suite goes through this fixture so the
    extension choice lives in one place."""
    return snapshot.use_extension(JSONSnapshotExtension)


def _collect_paths(data: Any, prefix: str = "") -> list[str]:
    """Flattens a nested dict/list into its dotted paths (list indices
    included), so a wildcard pattern like `payload.questions.*.id` can be
    matched against the paths that actually exist in `data`."""
    paths: list[str] = []

    if isinstance(data, dict):
        items = data.items()
    elif isinstance(data, list):
        items = enumerate(data)
    else:
        return paths

    for key, value in items:
        full_path = f"{prefix}.{key}" if prefix else str(key)
        paths.append(full_path)
        paths.extend(_collect_paths(value, full_path))

    return paths


def _expand_wildcards(path_types: PathTypeMap, data: Any) -> PathTypeMap:
    """Resolves every `*` segment in `path_types` against `data`'s actual
    paths (computed once, not per pattern) — `payload.questions.*.id`
    becomes one concrete entry per question actually present."""
    concrete_paths = None  # computed lazily, only if a wildcard is present
    expanded: PathTypeMap = {}

    for pattern, types in path_types.items():
        if "*" not in pattern:
            expanded[pattern] = types
            continue

        if concrete_paths is None:
            concrete_paths = _collect_paths(data)

        regex = re.compile(f"^{re.escape(pattern).replace(r'\*', r'[^.]+')}$")
        expanded.update({path: types for path in concrete_paths if regex.match(path)})

    return expanded


@pytest.fixture
def snapshot_json_matcher(snapshot):
    """Builds a `snapshot_json`-equivalent that replaces the values at
    `path_types`' paths with a type check instead of an exact-value match
    — for fields that are legitimately non-deterministic per run (UUIDs,
    timestamps) but whose *type* is still worth pinning. `path_types`
    supports a `*` wildcard for one path segment (list index or dict key),
    expanded against `data` when given.

    Usage:
        def test_x(snapshot_json_matcher):
            snapshot = snapshot_json_matcher({"payload.id": (str,)}, data=response)
            assert response == snapshot
    """

    def build(path_types: PathTypeMap, data: Any = None) -> Any:
        if data is not None and any("*" in path for path in path_types):
            path_types = _expand_wildcards(path_types, data)

        return snapshot.with_defaults(
            matcher=path_type(path_types),
            extension_class=JSONSnapshotExtension,
        )

    return build
