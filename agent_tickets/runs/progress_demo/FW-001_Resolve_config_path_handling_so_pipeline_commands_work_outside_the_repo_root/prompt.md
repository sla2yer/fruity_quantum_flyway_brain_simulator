Work ticket FW-001: Resolve config path handling so pipeline commands work outside the repo root.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: repo review 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The pipeline currently interprets relative paths from YAML against the caller's current working directory instead of the config file location or the repository root. That makes the commands brittle in automation, editor tasks, and any shell session that is not already sitting at the repo root.

Requested Change:
Introduce a single path-resolution strategy for config-driven paths and apply it consistently across the pipeline commands. Relative paths should resolve deterministically from the config file location or an explicitly chosen project root. Keep the implementation centralized rather than fixing each script ad hoc.

Acceptance Criteria:
- Running `scripts/build_registry.py`, `scripts/01_select_subset.py`, `scripts/02_fetch_meshes.py`, and `scripts/03_build_wave_assets.py` with an absolute config path works even when the caller's current working directory is outside the repo root.
- Existing repo-root usage keeps working.
- The code path that resolves config paths is covered by regression tests.
- README or inline help reflects the supported path behavior.

Verification:
- `make test`
- A regression test or scripted repro that launches at least one pipeline command from a non-root working directory
