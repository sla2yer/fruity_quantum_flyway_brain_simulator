## OVR-001 - Close stale duplicate resolver cleanup for `compare-analysis`
- Status: closed
- Priority: low
- Source: overengineering_and_abstraction_load review
- Area: experiment comparison analysis / simulation planning

### Problem
In the current workspace state, `compare-analysis` no longer has the duplicate manifest-resolution path this ticket described. `execute_experiment_comparison_workflow()` resolves `simulation_plan` once and reads `readout_analysis_plan` directly from that plan. The remaining `resolve_manifest_readout_analysis_plan()` helper is still present as a shared planning shim, but removing that helper repo-wide would be a different cleanup than the original `compare-analysis` bug.

### Evidence
- [src/flywire_wave/experiment_comparison_analysis.py#L36](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L36) resolves `simulation_plan` once, and [src/flywire_wave/experiment_comparison_analysis.py#L46](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L46) extracts `readout_analysis_plan` from `resolved_simulation_plan` instead of calling a second resolver.
- [Makefile#L150](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L150) routes `compare-analysis` through [scripts/20_experiment_comparison_analysis.py#L43](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/20_experiment_comparison_analysis.py#L43), which directly invokes `execute_experiment_comparison_workflow()`.
- [src/flywire_wave/simulation_planning.py#L729](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L729) still defines `resolve_manifest_readout_analysis_plan()`, but the current comparison workflow no longer uses it.
- [tests/test_experiment_comparison_analysis.py#L368](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L368) covers the no-replanning path for a pre-resolved `simulation_plan`; `.venv/bin/python -m pytest -q tests/test_experiment_comparison_analysis.py` passes in the current workspace.

### Requested Change
No implementation work is needed under `OVR-001`. Close this ticket as already satisfied by the current `compare-analysis` workflow. If the team still wants to retire `resolve_manifest_readout_analysis_plan()` from shared APIs, that should be tracked separately rather than reopening this ticket.

### Acceptance Criteria
- `make compare-analysis` continues to execute through a single top-level simulation-plan resolution in `execute_experiment_comparison_workflow()`.
- `readout_analysis_plan` continues to be read from the resolved simulation plan rather than obtained by a second full resolver pass.
- `OVR-001` is closed with no code change required.

### Verification
- `.venv/bin/python -m pytest -q tests/test_experiment_comparison_analysis.py`
