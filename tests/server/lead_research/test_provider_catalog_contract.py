"""Every catalog entry must be valid, reach a real adapter, and speak the engine's vocabulary.

provider-catalog.yaml is the only definition of each data source. Nothing at
import time checks that an entry validates, that the adapter path it names
still exists, or that the claim fields it emits are ones the engine consumes.
Each of those goes wrong silently: a stale adapter path fails at first boot,
and a mistyped emits field leaves a scoring dimension permanently unanswered
with no signal. These tests move those failures to CI, the way
tests/sales_skills/test_skill_registry_contract.py does for run types.
"""
from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from server.lead_research.catalog import CATALOG_PATH, catalog_definition, import_adapter, load_catalog
from server.lead_research.models import DatasetDefinition
from server.lead_research.providers.base import CatalogProvider
from server.lead_research.providers.bright_data import bright_data_definition
from server.lead_research.providers.corpus import corpus_definition
from server.lead_research.providers.ted import ted_definition
from server.lead_research.scoring import CLAIM_FIELDS

RAW_ENTRIES = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or []
SOURCE_IDS = [entry["source_id"] for entry in RAW_ENTRIES]


def test_catalog_is_not_empty() -> None:
    assert RAW_ENTRIES, f"{CATALOG_PATH.name} declares no sources"


@pytest.mark.parametrize("entry", RAW_ENTRIES, ids=SOURCE_IDS)
def test_every_catalog_entry_validates(entry: dict) -> None:
    DatasetDefinition.model_validate(entry)


def test_catalog_source_ids_are_unique() -> None:
    assert len(set(SOURCE_IDS)) == len(SOURCE_IDS), SOURCE_IDS


@pytest.mark.parametrize("definition", load_catalog(), ids=lambda d: d.source_id)
def test_every_shipped_source_names_an_importable_adapter(definition: DatasetDefinition) -> None:
    """An entry with no adapter renders as permanently unavailable; see the catalog header."""
    assert definition.adapter, f"{definition.source_id} names no adapter"
    adapter = import_adapter(definition)
    assert issubclass(adapter, CatalogProvider), (
        f"{definition.source_id}: {definition.adapter} is not a CatalogProvider"
    )


@pytest.mark.parametrize("definition", load_catalog(), ids=lambda d: d.source_id)
def test_credentialed_adapters_build_from_settings(definition: DatasetDefinition) -> None:
    """build_registry gates a credentialed source through the adapter, not an if."""
    if definition.adapter_mode != "credential_required":
        pytest.skip("no credential to gate")
    assert callable(getattr(import_adapter(definition), "from_settings", None))


@pytest.mark.parametrize("definition", load_catalog(), ids=lambda d: d.source_id)
def test_every_emitted_field_is_one_the_engine_consumes(definition: DatasetDefinition) -> None:
    unknown = sorted(set(definition.emits) - CLAIM_FIELDS)
    assert unknown == [], f"{definition.source_id} emits fields nothing scores: {unknown}"


@pytest.mark.parametrize("definition", load_catalog(), ids=lambda d: d.source_id)
def test_declared_candidate_discovery_matches_the_adapter(definition: DatasetDefinition) -> None:
    """`candidate_discovery` in the catalog must mean the adapter can discover.

    The engine never reads this capability: discovery.py asks
    `isinstance(provider, CandidateSource)`, i.e. whether the adapter implements
    `discover_candidates`. The web UI, however, does read it, to decide whether
    a search can find new companies at all. Nothing else ties the two together,
    so a source that declared discovery without implementing it would let a
    tenant start a search the engine then refuses, and one that implemented
    without declaring would be told it cannot search when it can.

    Checked against the adapter class the entry names, not the built instance:
    credential gating swaps in an Unavailable stand-in that answers neither.
    """
    declares = "candidate_discovery" in definition.capabilities
    implements = callable(getattr(import_adapter(definition), "discover_candidates", None))
    assert declares == implements, (
        f"{definition.source_id}: capabilities {'declare' if declares else 'omit'} "
        f"candidate_discovery but {definition.adapter} "
        f"{'implements' if implements else 'does not implement'} discover_candidates"
    )


def test_a_mistyped_emits_field_is_rejected_at_validation() -> None:
    entry = dict(RAW_ENTRIES[0], emits=["employee_counts"])
    with pytest.raises(ValidationError, match="employee_counts"):
        DatasetDefinition.model_validate(entry)


def test_a_stale_adapter_path_fails_by_name() -> None:
    definition = load_catalog()[0].model_copy(
        update={"adapter": "server.lead_research.providers.ted:RenamedVerifier"},
    )
    with pytest.raises(ValueError, match="RenamedVerifier"):
        import_adapter(definition)


@pytest.mark.parametrize(
    ("source_id", "code_definition"),
    [
        ("ted", ted_definition),
        ("customer-list-corpus", corpus_definition),
        ("brightdata-web", bright_data_definition),
    ],
)
def test_adapter_definitions_are_the_catalog_entry(source_id, code_definition) -> None:
    """The in-code definition functions read the catalog; they cannot drift from it."""
    assert code_definition() == catalog_definition(source_id)


def test_unknown_source_is_rejected_by_name() -> None:
    with pytest.raises(KeyError, match="companies-house"):
        catalog_definition("companies-house")
