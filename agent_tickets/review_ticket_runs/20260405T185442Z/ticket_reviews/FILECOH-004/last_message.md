## FILECOH-004 - Separate experiment comparison discovery, core scoring, and analysis-bundle packaging behind a stable facade
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: experiment comparison workflow

### Problem
`experiment_comparison_analysis.py` is still a monolithic public entrypoint that mixes three distinct responsibilities: simulator bundle discovery and plan-alignment validation, core experiment comparison scoring or null-test evaluation, and analysis-bundle packaging for UI or offline report artifacts. The file has also become an integration surface for other workflows, so the refactor now needs to preserve the current import facade instead of treating this as a purely internal move.

### Evidence
The module is still 2,998 lines long and pulls in packaging dependencies at import time through [experiment_comparison_analysis.py:13](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L13) and [experiment_comparison_analysis.py:27](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L27). It defines bundle discovery at [experiment_comparison_analysis.py:87](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L87), core summary computation at [experiment_comparison_analysis.py:260](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L260), workflow coordination at [experiment_comparison_analysis.py:456](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L456), bundle packaging at [experiment_comparison_analysis.py:521](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L521), UI payload assembly at [experiment_comparison_analysis.py:871](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L871), bundle-vs-plan validation helpers starting at [experiment_comparison_analysis.py:1297](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L1297), null-test evaluation at [experiment_comparison_analysis.py:2300](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2300), task scoring at [experiment_comparison_analysis.py:2614](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2614), and output-summary assembly at [experiment_comparison_analysis.py:2771](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2771).

This module is also imported directly by downstream code, so callers currently depend on its public surface: the CLI at [20_experiment_comparison_analysis.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/20_experiment_comparison_analysis.py#L16), planning code at [validation_planning.py:17](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_planning.py#L17) and [dashboard_session_planning.py:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L88), validation code at [validation_circuit.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_circuit.py#L16), and suite execution at [experiment_suite_execution.py:651](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L651) and [experiment_suite_execution.py:741](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L741). Current tests also lock in packaging behavior and workflow reuse at [test_experiment_comparison_analysis.py:120](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L120), [test_experiment_comparison_analysis.py:195](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L195), and [test_experiment_comparison_analysis.py:346](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L346).

### Requested Change
Keep `experiment_comparison_analysis.py` as the stable public facade, but move its implementation seams into focused modules:
- a discovery module for bundle-set discovery, condition inference, and bundle-vs-plan validation
- a core comparison module for metric aggregation, null tests, task scoring, and output-summary assembly
- a packaging module for bundle metadata writing, export payload builders, visualization catalog assembly, UI payload assembly, and offline report handoff

`execute_experiment_comparison_workflow` should remain a thin coordinator over those modules, and existing public imports should continue to work for current callers.

### Acceptance Criteria
`discover_experiment_bundle_set` and its helper stack no longer live in the same implementation file as packaging or UI export builders.

`compute_experiment_comparison_summary` lives in a core analysis module that does not import report-generation or experiment-analysis bundle packaging helpers at module import time.

Packaging code consumes normalized summary or bundle inputs and owns export writing, UI payload generation, visualization catalog generation, and offline report packaging without re-owning comparison math.

`experiment_comparison_analysis.py` remains a compatibility facade exposing the current public entrypoints used by scripts, validation flows, dashboard planning, and suite execution.

Existing workflow behavior remains intact, including package generation, offline report regeneration from local artifacts, and accepting pre-resolved plans.

### Verification
`make test`
`make smoke`