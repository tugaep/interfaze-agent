"""The provider catalog is the single definition of every data source.

`provider-catalog.yaml` wins. Adapters take their DatasetDefinition from here
rather than carrying a second copy in code, so the two cannot drift, and the
registry reaches an adapter by the `adapter:` path each entry declares rather
than by naming source ids in Python.
"""
from __future__ import annotations

from functools import lru_cache
from importlib import import_module

import yaml

from .models import DatasetDefinition
from .sectors import REFERENCE_DIR

CATALOG_PATH = REFERENCE_DIR / "provider-catalog.yaml"


@lru_cache(maxsize=1)
def _catalog() -> tuple[DatasetDefinition, ...]:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or []
    return tuple(DatasetDefinition.model_validate(item) for item in raw)


def load_catalog() -> list[DatasetDefinition]:
    """Every catalog entry, validated. Copies, so callers may adjust them."""
    return [item.model_copy() for item in _catalog()]


def catalog_definition(source_id: str) -> DatasetDefinition:
    for item in _catalog():
        if item.source_id == source_id:
            return item.model_copy()
    raise KeyError(f"{source_id!r} is not in {CATALOG_PATH.name}")


def import_adapter(definition: DatasetDefinition) -> type:
    """Resolve the class a catalog entry names. Raises if the path is stale."""
    if definition.adapter is None:
        raise ValueError(f"{definition.source_id} names no adapter")
    module_path, class_name = definition.adapter.split(":", 1)
    module = import_module(module_path)
    adapter = getattr(module, class_name, None)
    if not isinstance(adapter, type):
        raise ValueError(
            f"{definition.source_id}: adapter {definition.adapter!r} is not a class in {module_path}"
        )
    return adapter
