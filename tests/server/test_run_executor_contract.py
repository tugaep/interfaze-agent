"""Every executor raises rather than returning an unusable run result.

The runner exits 0 when the agent fails: "No LLM provider configured" and an
HTTP 401 both arrive as a successful process with the reason on stdout. That
judgement -- no answer is a failure, and the error says why -- used to live
only inside HermesProcessExecutor, so a second executor would have had to
reimplement it. It now lives in BaseRunExecutor.execute, and these tests hold
every executor to it, the way test_skill_registry_contract.py holds every run
type to its skill.

The distinction these tests protect: a run that found nothing is a success
that names its reason; only the absence of an answer raises.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Imported for their BaseRunExecutor subclasses, so runtime discovery sees the
# test doubles as well as the two shipped executors.
import tests.server.test_company_research_profile  # noqa: F401
import tests.server.test_run_harness  # noqa: F401
from server.agent_service import BaseRunExecutor, HermesProcessExecutor, StubRunExecutor

REPO = Path(__file__).resolve().parents[2]
RUN = {"id": "run_1", "run_type": "lead_scan", "company_id": "cmp_1"}


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _subclasses(sub)
    return found


EXECUTORS = sorted(_subclasses(BaseRunExecutor), key=lambda c: c.__name__)


def _declared_executors() -> list[tuple[Path, ast.ClassDef]]:
    """Every executor in the tree, found by reading source rather than imports.

    `__subclasses__()` only sees what the current session happened to import,
    so running this file alone covers fewer executors than a full run -- which
    is exactly how RefreshExecutor and ContractRunExecutor, both subclasses of
    StubRunExecutor rather than of BaseRunExecutor, went unnoticed. This scan
    does not depend on import order, and follows the subclass chain to a
    fixpoint so an executor is caught however indirectly it inherits.
    """
    classes: list[tuple[Path, ast.ClassDef]] = []
    for path in sorted(REPO.glob("server/**/*.py")) + sorted(REPO.glob("tests/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes.extend(
            (path.relative_to(REPO), node)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        )
    known = {"BaseRunExecutor"}
    found: dict[str, tuple[Path, ast.ClassDef]] = {}
    while True:
        new = {
            node.name: (path, node)
            for path, node in classes
            if node.name not in found
            and any(isinstance(b, ast.Name) and b.id in known for b in node.bases)
        }
        if not new:
            return sorted(found.values(), key=lambda item: item[1].name)
        found.update(new)
        known |= set(new)


DECLARED = _declared_executors()


class _Returns(BaseRunExecutor):
    """Drives the contract directly: whatever it is handed is what it returns."""

    def __init__(self, output):
        self.output = output

    def _execute_run(self, service, run):
        return self.output


def test_discovery_found_the_shipped_executors() -> None:
    """Guards the parametrised tests below from passing vacuously."""
    assert {StubRunExecutor, HermesProcessExecutor} <= set(EXECUTORS)


@pytest.mark.parametrize("executor", EXECUTORS, ids=lambda c: c.__name__)
def test_no_executor_overrides_the_enforcement_point(executor: type) -> None:
    """`execute` is the guard; subclasses implement `_execute_run` instead.

    An executor that overrode `execute` would silently opt out of the contract
    and nothing else would notice.
    """
    assert "execute" not in vars(executor), (
        f"{executor.__name__} overrides execute(), bypassing the no-usable-output "
        "guard in BaseRunExecutor; implement _execute_run() instead"
    )


@pytest.mark.parametrize("executor", EXECUTORS, ids=lambda c: c.__name__)
def test_every_executor_implements_the_hook(executor: type) -> None:
    assert "_execute_run" in vars(executor), (
        f"{executor.__name__} implements neither execute() nor _execute_run()"
    )


@pytest.mark.parametrize(
    ("path", "node"), DECLARED, ids=[node.name for _, node in DECLARED],
)
def test_no_executor_in_the_tree_defines_execute(path: Path, node: ast.ClassDef) -> None:
    """The import-independent form of the check above.

    Catches an executor in a module this session never imported, and one that
    inherits through another executor rather than from BaseRunExecutor.
    """
    defined = {child.name for child in node.body if isinstance(child, ast.FunctionDef)}
    assert "execute" not in defined, (
        f"{path}:{node.lineno} {node.name} defines execute(), bypassing the "
        "no-usable-output guard; implement _execute_run() instead"
    )


def test_the_source_scan_sees_the_indirect_executors() -> None:
    """Guards the fixpoint: a StubRunExecutor subclass must be reached."""
    names = {node.name for _, node in DECLARED}
    assert {"StubRunExecutor", "HermesProcessExecutor"} <= names
    assert {"RefreshExecutor", "ContractRunExecutor"} <= names, (
        f"fixpoint stopped early; found {sorted(names)}"
    )


@pytest.mark.parametrize("empty", [None, {}, [], "", 0, [{"leads": []}]], ids=repr)
def test_no_usable_output_raises(empty) -> None:
    with pytest.raises(RuntimeError, match="no usable output"):
        _Returns(empty).execute(None, RUN)


def test_the_error_names_the_executor_and_the_run() -> None:
    """A failed run is read by an operator, not a debugger."""
    with pytest.raises(RuntimeError) as excinfo:
        _Returns(None).execute(None, RUN)
    message = str(excinfo.value)
    assert "_Returns" in message
    assert "lead_scan" in message
    assert "run_1" in message


def test_diagnostics_are_carried_into_the_error() -> None:
    """The transcript tail is why an operator can tell 401 from a bad prompt."""
    executor = _Returns(None)
    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        executor._require_output(None, RUN, "No LLM provider configured")


def test_a_zero_result_run_is_not_a_failure() -> None:
    """The invariant this guard must not break: found-nothing names its reason."""
    output = {"leads": [], "stop_reason": "source_exhausted"}
    assert _Returns(output).execute(None, RUN) == output


def test_a_base_executor_without_a_hook_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        BaseRunExecutor().execute(None, RUN)
