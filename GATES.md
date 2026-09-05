# Gates: Hermes product slimming and modularization

Scope: Reduce the vendored Hermes footprint used by Interfaze and improve module boundaries while preserving every supported product path.

- [ ] G0: the completion ledger contains meaningful, executable outcomes
  CHECK: node /Users/ibz/.agents/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: pending

- [ ] G1: one-shot execution loads every explicitly requested skill and rejects an entirely missing skill set
  CHECK: rtk pytest -q tests/test_oneshot.py
  EXPECT: passed in
  EVIDENCE: pending

- [ ] G2: Interfaze agent runs use the dedicated runner and a run-type-specific restricted tool profile
  CHECK: rtk pytest -q tests/server/test_agent_runner.py tests/server/test_run_harness.py tests/sales_skills/test_skill_registry_contract.py
  EXPECT: passed in
  EVIDENCE: pending

- [ ] G3: product and lead-engine regression tests pass
  CHECK: rtk pytest -q tests/server tests/sales_skills
  EXPECT: passed in
  EVIDENCE: pending

- [ ] G4: the complete repository test suite passes
  CHECK: rtk pytest -q tests
  EXPECT: passed in
  EVIDENCE: pending

- [ ] G5: the wheel exposes both public entry points and the product container validates only its dedicated agent runner
  CHECK: rtk pytest -q tests/server/test_agent_runner.py tests/test_packaging.py
  EXPECT: passed in
  EVIDENCE: pending
