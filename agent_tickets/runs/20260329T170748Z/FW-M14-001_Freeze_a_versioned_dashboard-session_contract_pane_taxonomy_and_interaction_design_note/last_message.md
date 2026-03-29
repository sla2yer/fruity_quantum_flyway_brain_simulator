**Changed**

Added the canonical Milestone 14 dashboard contract in [dashboard_session_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_contract.py). It freezes `dashboard_session.v1`, the five pane IDs, global interaction state, overlay categories, comparison modes, export target IDs, deterministic session bundle paths, artifact-hook roles for simulator/analysis/validation inputs, and deterministic session metadata serialization/discovery. I also exposed the module in [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).

Documented the UI model and boundaries in [ui_dashboard_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/ui_dashboard_design.md), added the required rationale note at [FW-M14-001_rationale.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/ui_dashboard_notes/FW-M14-001_rationale.md), and updated [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md) so the dashboard contract now sits alongside the existing simulator, analysis, and validation bundle contracts.

Added regression coverage in [test_dashboard_session_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_contract.py) for deterministic contract/session serialization, stable pane and overlay discovery, and normalization of representative fixture dashboard-session metadata.

**Verified**

Ran `python3 -m unittest tests.test_dashboard_session_contract -v` and it passed.

Ran `make test` and the full suite passed: `196` tests total. The suite still prints the existing Codex DB warning at startup, but it is non-fatal and the run completed successfully.