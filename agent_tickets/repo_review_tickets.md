# Repo Review Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-001 - Resolve config path handling so pipeline commands work outside the repo root
- Status: open
- Priority: high
- Source: repo review 2026-03-21
- Area: config / CLI ergonomics

### Problem
The pipeline currently interprets relative paths from YAML against the caller's current working directory instead of the config file location or the repository root. That makes the commands brittle in automation, editor tasks, and any shell session that is not already sitting at the repo root.

### Requested Change
Introduce a single path-resolution strategy for config-driven paths and apply it consistently across the pipeline commands. Relative paths should resolve deterministically from the config file location or an explicitly chosen project root. Keep the implementation centralized rather than fixing each script ad hoc.

### Acceptance Criteria
- Running `scripts/build_registry.py`, `scripts/01_select_subset.py`, `scripts/02_fetch_meshes.py`, and `scripts/03_build_wave_assets.py` with an absolute config path works even when the caller's current working directory is outside the repo root.
- Existing repo-root usage keeps working.
- The code path that resolves config paths is covered by regression tests.
- README or inline help reflects the supported path behavior.

### Verification
- `make test`
- A regression test or scripted repro that launches at least one pipeline command from a non-root working directory

## FW-002 - Fail fast when optional registry source overrides point at missing files
- Status: open
- Priority: high
- Source: repo review 2026-03-21
- Area: registry / provenance

### Problem
If a user explicitly sets an override such as `paths.connections_csv` and the file does not exist, the registry builder silently treats the source as absent and continues. That can quietly produce an incomplete registry and empty connectivity outputs even though the config was clearly asking for that input.

### Requested Change
Update registry source resolution so explicit override paths are validated strictly. If the user provided an override and the file is missing, raise a clear configuration error instead of silently downgrading to a missing optional source. Keep auto-discovery behavior for genuinely optional, non-overridden inputs.

### Acceptance Criteria
- Explicit override paths for optional inputs fail with a clear error when the target file is missing.
- Auto-discovery still works for optional sources when no override is provided.
- Regression coverage exercises both the failing override case and the still-valid auto-discovery case.
- Error text names the config key and the missing file path.

### Verification
- `make test`
- A focused unit test for optional override validation in registry source resolution

## FW-003 - Enforce registry membership before building processed wave assets
- Status: open
- Priority: medium
- Source: repo review 2026-03-21
- Area: asset pipeline / provenance

### Problem
`scripts/03_build_wave_assets.py` currently allows selected root IDs that are absent from the neuron registry. The command succeeds and writes assets whose manifest metadata fields are blank, which weakens provenance and breaks the assumption that selected IDs were validated upstream.

### Requested Change
Make the processed-asset builder enforce the same registry-membership contract as the mesh-fetch step. If any selected root ID is missing from the registry, fail early with a precise error message instead of emitting incomplete metadata.

### Acceptance Criteria
- The asset build step errors clearly when any selected root ID is not present in the neuron registry.
- The error reports how many root IDs are missing and includes a small sample.
- Happy-path asset building with fully registered root IDs still works.
- Regression coverage exists for both the failure case and the happy path.

### Verification
- `make test`
- A unit or integration-style test that reproduces the current silent-success case and asserts it now fails
