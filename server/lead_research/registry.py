"""Declarative provider catalog and tenant lifecycle state."""
from __future__ import annotations

from ..config import Settings
from .catalog import CATALOG_PATH, import_adapter, load_catalog
from .models import DatasetDefinition, SourceCapability
from .providers.base import CatalogProvider, Provider
from .providers.base import CandidateSource, StructuredFactSource

__all__ = ["CATALOG_PATH", "ProviderRegistry", "build_registry"]


class ProviderRegistry:
    def __init__(self, definitions: list[DatasetDefinition], providers: dict[str, Provider] | None = None):
        self.definitions = {item.source_id: item for item in definitions}
        if len(self.definitions) != len(definitions):
            raise ValueError("provider source ids must be unique")
        supplied = providers or {}
        self.providers = {
            source_id: supplied.get(source_id, CatalogProvider(definition))
            for source_id, definition in self.definitions.items()
        }

    def get(self, source_id: str) -> Provider:
        try:
            return self.providers[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown research source: {source_id}") from exc

    def list(self) -> list[DatasetDefinition]:
        return sorted(self.definitions.values(), key=lambda item: item.display_name.lower())

    def source_capabilities(
        self,
        source_ids: list[str] | None = None,
        provider_overrides: dict | None = None,
    ) -> list[SourceCapability]:
        selected = set(source_ids or self.definitions)
        result: list[SourceCapability] = []
        for definition in self.list():
            if definition.source_id not in selected:
                continue
            provider = (provider_overrides or {}).get(
                definition.source_id, self.get(definition.source_id),
            )
            access_class = {
                "customer_upload": "customer_upload",
                "licensed": "licensed",
                "credentialed_public": "credentialed",
            }.get(definition.access_tier, "public")
            authority = (
                "customer" if access_class == "customer_upload"
                else "licensed" if access_class == "licensed"
                else "registry" if "authoritative_registry" in definition.capabilities
                else "credible"
            )
            result.append(SourceCapability(
                source_id=definition.source_id,
                candidate_discovery=isinstance(provider, CandidateSource),
                emitted_fields=frozenset(definition.emits),
                countries=frozenset(definition.countries),
                sector_ids=frozenset(definition.sector_ids),
                access_class=access_class,
                freshness_days={field: definition.freshness_days for field in definition.emits},
                max_concurrency=definition.max_concurrency,
                authority=authority,
                redistributable=definition.access_tier in {"public", "credentialed_public"},
                executable=callable(getattr(provider, "research_fields", None)),
            ))
        return result

    def customer_catalog(self) -> list[dict]:
        result = []
        for definition in self.list():
            provider = self.get(definition.source_id)
            executable = isinstance(provider, (CandidateSource, StructuredFactSource)) or callable(
                getattr(provider, "verify", None)
            )
            health = provider.health()
            if not executable or health.status not in {"active", "degraded"}:
                continue
            result.append({
                "id": definition.source_id,
                "display_name": definition.display_name,
                "runnable": True,
                "capabilities": list(definition.capabilities),
            })
        return result

    def admin_setup_catalog(self) -> list[dict]:
        runnable = {item["id"] for item in self.customer_catalog()}
        return [{
            "id": definition.source_id,
            "display_name": definition.display_name,
            "runnable": definition.source_id in runnable,
            "adapter_mode": definition.adapter_mode,
        } for definition in self.list()]

    def ensure_tenant(self, db, company_id: str, stamp: float) -> None:
        from ..db import json_dump
        # A source dropped from the catalog leaves a tenant row behind, and
        # catalog() resolves every row through the registry — so without this
        # the whole Data Sources page raises KeyError on the stale one. Evidence
        # and partitions keep their source_id; nothing here touches history.
        known = set(self.definitions)
        stale = [
            row["source_id"] for row in db.all(
                "SELECT source_id FROM dataset_definitions WHERE company_id=?", (company_id,)
            ) if row["source_id"] not in known
        ]
        for source_id in stale:
            db.execute(
                "DELETE FROM dataset_definitions WHERE company_id=? AND source_id=?",
                (company_id, source_id),
            )
        for definition in self.list():
            payload = json_dump(definition.model_dump(mode="json"))
            exists = db.one(
                "SELECT source_id FROM dataset_definitions WHERE company_id=? AND source_id=?",
                (company_id, definition.source_id),
            )
            if exists:
                # The definition is catalog-owned and the row caches a copy, so
                # a catalog edit — a new adapter_mode, a retirement — would
                # otherwise never reach a tenant that had already been seeded.
                # installed/enabled are the tenant's and are left alone.
                db.execute(
                    "UPDATE dataset_definitions SET definition=?,health=? "
                    "WHERE company_id=? AND source_id=?",
                    (payload, definition.health, company_id, definition.source_id),
                )
                continue
            db.execute(
                "INSERT INTO dataset_definitions VALUES(?,?,?,?,?,?,?,?)",
                (company_id, definition.source_id, 1, int(definition.default_enabled),
                 payload, definition.health, None, stamp),
            )


def build_registry(
    settings: Settings | None = None,
    providers: dict[str, Provider] | None = None,
) -> ProviderRegistry:
    """Instantiate every adapter the catalog names.

    No source id appears here. An entry without an `adapter:` stays a
    CatalogProvider and renders as unavailable; one whose adapter_mode is
    credential_required is built through the adapter's own `from_settings`,
    which returns a gated stand-in when the deployment has not enabled it or
    supplied the key. Tenants still opt in per source.
    """
    definitions = load_catalog()
    supplied = dict(providers or {})
    for definition in definitions:
        if definition.source_id in supplied or definition.adapter is None:
            continue
        adapter = import_adapter(definition)
        if definition.adapter_mode == "credential_required":
            from_settings = getattr(adapter, "from_settings", None)
            if not callable(from_settings):
                raise ValueError(
                    f"{definition.source_id}: adapter {definition.adapter} is credential_required "
                    "but has no from_settings(definition, settings) constructor"
                )
            settings = settings or Settings.load()
            supplied[definition.source_id] = from_settings(definition, settings)
        else:
            supplied[definition.source_id] = adapter(definition=definition)
    return ProviderRegistry(definitions, supplied)
