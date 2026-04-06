## OVR-004 - Close: dashboard build API already reflects the repo’s supported multi-entry planning surface
- Status: closed
- Priority: low
- Source: overengineering_and_abstraction_load review
- Area: dashboard session planning / CLI / downstream integration

### Problem
The original ticket is no longer accurate for the repo’s current state. It assumes manifest-driven dashboard packaging is the only real public entry path and treats experiment-driven or metadata-driven planning as accidental abstraction. In the current repository, manifest-driven build is still the default `make` workflow, but the broader dashboard planning surface is now a documented, regression-tested, and downstream-used part of the shipped API.

### Evidence
- The default operator path is still manifest-driven via [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L153) and [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L156), but that is only the default entrypoint, not the full supported surface.
- The public CLI intentionally exposes manifest, experiment, and explicit metadata inputs at [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L62), [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L68), and [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L70).
- The planner still defines three source modes and already includes a manifest-specific wrapper, so a narrow manifest helper exists without removing the broader API at [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L137), [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L142), and [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L159).
- The current pipeline notes explicitly define `scripts/29_dashboard_shell.py build` as the canonical CLI for manifest-, experiment-, or bundle-driven inputs at [docs/pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L651).
- The shipped Milestone 14 readiness audit deliberately compares manifest-driven and experiment-driven planning through the public API at [src/flywire_wave/milestone14_readiness.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone14_readiness.py#L325).
- Downstream flows rely on these alternate modes: showcase planning resolves dashboard context from `experiment_id` at [src/flywire_wave/showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L511), and suite dashboard packaging injects packaged analysis and validation metadata paths into the planner at [src/flywire_wave/experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L924).
- Tests still lock in experiment/explicit convergence and precedence as supported behavior at [tests/test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L193) and [tests/test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L243).

### Requested Change
Close this ticket without implementation. Keep manifest-driven `make dashboard` and `make dashboard-open` as the default repo workflow, but do not narrow the public dashboard CLI or planner surface unless a future design change first removes multi-entry planning from the documented contract, readiness audit, downstream call sites, and regression tests.

### Acceptance Criteria
- The ticket is closed because the current repository intentionally supports manifest-, experiment-, and metadata-driven dashboard planning.
- Any future narrowing starts with a design and contract decision, followed by coordinated updates to docs, readiness coverage, downstream integrations, and tests.

### Verification
- Review current Make targets, CLI parser, planner API, pipeline notes, readiness audit, downstream dashboard consumers, and dashboard planning tests.
