# Modularity Update

Interfaze now has a clearer boundary between the product and the vendored Hermes runtime. Product workflows no longer invoke the general-purpose Hermes CLI directly. They use the dedicated `interfaze-agent-run` entry point instead.

## What changed

- Added `server/agent_runner.py` as the product-specific agent entry point.
- Centralized each run type's allowed skill and toolsets in `server/run_types.py`.
- Limited runs to the capabilities they need, such as web access, read-only files, or no tools.
- Updated Hermes one-shot execution to preload requested skills and preserve explicitly empty toolsets.
- Added a read-only file toolset for document workflows.
- Corrected WhatsApp outreach so it loads the WhatsApp playbook.
- Updated health checks, packaging, and the product container to validate the dedicated runner.
- Added contract tests for runner restrictions, skill loading, entry points, and packaging.

## How this improves modularity

The API now depends on a small product-facing execution interface instead of the full Hermes command surface. Run policy lives in one registry, execution lives in one runner, and the generic runtime remains reusable underneath.

This separation makes responsibilities easier to understand and change:

- Product code decides which workflow is running.
- The execution profile decides which skill and tools are allowed.
- The runner translates that profile into a one-shot Hermes session.
- Hermes handles the underlying model conversation without owning product policy.

The result is a safer, easier-to-test architecture where new workflows can be added through explicit profiles without coupling the API to unrelated runtime features.
