**Changed**

Added the canonical Milestone 14 session planner and packager in [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py). The new surface resolves local config plus manifest, experiment ID, or explicit bundle metadata into one normalized dashboard session plan, validates arm/bundle/timebase/overlay/morphology compatibility, and packages a deterministic session bundle with `dashboard_session.json`, `dashboard_session_payload.json`, `session_state.json`, and a placeholder `app/index.html`.

Added fixture-backed regression coverage in [test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py), exported the module from [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py), and wrote the design note at [FW-M14-002_rationale.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/ui_dashboard_notes/FW-M14-002_rationale.md).

**Verified**

Ran `./.venv/bin/python -m unittest tests.test_dashboard_session_planning -v` and all 5 new dashboard-session tests passed. They cover deterministic manifest assembly, experiment vs explicit-bundle convergence, explicit override precedence, missing wave-only diagnostics, insufficient morphology metadata, and mismatched paired timebases.

Ran `make test`; the full suite passed: `Ran 201 tests in 147.397s, OK`. The run printed the existing non-fatal `Failed to load DB for data version 783: No module named 'codex.data.connections_v2'` message before tests, but it did not affect the result.