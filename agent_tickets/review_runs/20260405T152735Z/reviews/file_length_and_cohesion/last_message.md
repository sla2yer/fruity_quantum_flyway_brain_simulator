# File Length And Cohesion Review Tickets

## FILECOH-001 - Split simulation manifest planning from analysis and asset/runtime resolution
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: simulation planning

### Problem
`simulation_planning.py` has become the catch-all owner for manifest validation, runtime normalization, readout-analysis planning, circuit asset discovery, and surface-wave mixed-fidelity execution planning. That makes routine changes to one planning seam pull several unrelated subsystems into the same file and review surface.

### Evidence
[simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) resolves the manifest, validates it, normalizes runtime config, resolves inputs, and calls circuit asset discovery in the same top-level path. The file then shifts into readout-analysis planning at [simulation_planning.py:743](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L743), local geometry/coupling readiness checks at [simulation_planning.py:2950](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2950), surface-wave execution plan assembly at [simulation_planning.py:3406](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3406), and mixed-fidelity/operator routing at [simulation_planning.py:3667](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3667). The test surface mirrors that spillover: [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56) and [test_experiment_suite_aggregation.py:37](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_aggregation.py#L37) import fixture builders from [test_simulation_planning.py:931](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L931) and [test_simulation_planning.py:1070](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1070).

### Requested Change
Keep `resolve_manifest_simulation_plan` as the orchestration entrypoint, but move readout-analysis planning under an analysis-planning boundary, move geometry/coupling asset resolution under an asset-readiness boundary, and move surface-wave or mixed-fidelity execution-plan construction under an execution-runtime planning boundary.

### Acceptance Criteria
`simulation_planning.py` is reduced to manifest-level orchestration and shared normalization, while readout-analysis helpers, circuit asset discovery or validation, and surface-wave mixed-fidelity planning live in narrower modules with explicit imports. Shared test fixture writers are moved out of `test_simulation_planning.py` into a dedicated test utility module instead of remaining trapped in the planner test file.

### Verification
`make test`
`make validate-manifest`
`make smoke`

## FILECOH-002 - Separate showcase session source resolution, narrative authoring, validation, and packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: showcase session planning

### Problem
`showcase_session_planning.py` mixes upstream artifact resolution, narrative and preset authoring, rehearsal/dashboard patch validation, and bundle packaging in one file. The current shape makes story-level edits risky because they sit beside packaging and low-level UI validation rules.

### Evidence
[showcase_session_planning.py:288](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L288) resolves suite, dashboard, analysis, and validation inputs, then immediately assembles presets, steps, script payloads, preset catalogs, and export manifests before returning a plan; packaging is in the same module at [showcase_session_planning.py:540](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L540). The file also owns long presentation-specific builders at [showcase_session_planning.py:1982](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1982) and [showcase_session_planning.py:3341](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3341), export assembly at [showcase_session_planning.py:4019](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4019) and [showcase_session_planning.py:4128](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4128), and deep rehearsal metadata validation at [showcase_session_planning.py:4479](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4479). The tests already depend on peer-module fixture builders at [test_showcase_session_planning.py:70](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L70), which is a sign that ownership is blurred across review surfaces.

### Requested Change
Split this module along real showcase seams: source and upstream artifact resolution, narrative or preset construction, presentation-state validation, and package or export writing. The planning entrypoint should compose those pieces instead of owning all four concerns directly.

### Acceptance Criteria
A top-level showcase planner remains, but preset or step generation lives outside the packaging code path, rehearsal or dashboard state validation lives in a validation-focused module, and export-manifest or bundle writing lives in a packaging-focused module. Showcase tests no longer need to reach through multiple peer test files to materialize reusable fixtures.

### Verification
`make test`
`make smoke`

## FILECOH-003 - Move whole-brain context query execution and packaging out of the planning catch-all
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: whole-brain context planning

### Problem
`whole_brain_context_planning.py` is nominally a planner, but it also executes whole-brain queries, generates preset executions, applies downstream handoffs, builds view payload or state, and packages artifacts. That collapses planning, query execution, and local review packaging into one module.

### Evidence
[whole_brain_context_planning.py:188](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L188) resolves source context, merges artifact references, builds query inputs, and directly calls `execute_whole_brain_context_query` at [whole_brain_context_planning.py:330](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L330). The same file executes preset queries again inside the preset library builder at [whole_brain_context_planning.py:1921](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1921) and [whole_brain_context_planning.py:2018](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2018), then switches to downstream handoff mutation and catalog or view assembly around [whole_brain_context_planning.py:2450](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2450) and packages bundles at [whole_brain_context_planning.py:448](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L448). Test setup also crosses planning modules at [test_whole_brain_context_planning.py:48](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L48).

### Requested Change
Keep source and contract resolution in the planning module, but move query execution or preset hydration behind the `whole_brain_context_query` family and move bundle payload or state packaging behind a packaging-oriented module. Downstream handoff enrichment should sit with the query or presentation layer it belongs to, not inside the top-level planner.

### Acceptance Criteria
`resolve_whole_brain_context_session_plan` becomes an orchestrator that consumes source context and query results instead of executing queries inline. Query execution, preset execution, and package payload or state builders are owned by narrower modules whose names match those responsibilities.

### Verification
`make test`
`make validate-manifest`
`make smoke`

## FILECOH-004 - Split experiment comparison discovery, scoring, and export packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: experiment comparison analysis

### Problem
`experiment_comparison_analysis.py` mixes filesystem bundle discovery, bundle-vs-plan validation, core comparison rollups, null-test evaluation, workflow orchestration, and UI or export packaging. That makes metric or null-test changes harder to review because the same file also owns report generation and artifact writing.

### Evidence
The file begins with bundle discovery at [experiment_comparison_analysis.py:84](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L84), computes the main summary at [experiment_comparison_analysis.py:255](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L255), orchestrates the full workflow at [experiment_comparison_analysis.py:451](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L451), packages bundle artifacts at [experiment_comparison_analysis.py:503](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L503), builds UI payloads at [experiment_comparison_analysis.py:853](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L853), evaluates null tests at [experiment_comparison_analysis.py:2142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2142), and assembles output summaries at [experiment_comparison_analysis.py:2613](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2613). Those are separate seams in this repo: discovery or validation, analysis, and packaging or export.

### Requested Change
Split the module into a bundle discovery or validation module, a core comparison computation module, and a packaging or export module for UI payloads and report artifacts. `execute_experiment_comparison_workflow` should remain as a thin coordinator across those boundaries.

### Acceptance Criteria
Bundle discovery and plan-alignment validation no longer live in the same file as null-test scoring and export payload builders. The analysis summary can be computed without importing packaging helpers, and the packaging path consumes a normalized summary object rather than re-owning analysis logic.

### Verification
`make test`
`make smoke`

## FILECOH-005 - Remove CLI and UI/export packaging concerns from simulator execution
- Status: open
- Priority: medium
- Source: file_length_and_cohesion review
- Area: simulator execution

### Problem
`simulator_execution.py` mixes a library workflow API, an argparse CLI entrypoint, baseline and surface-wave execution, bundle writing, provenance generation, and UI comparison payload assembly. That blurs the boundary between execution/runtime code and packaging or presentation code, and it leaves `scripts/run_simulation.py` as a trivial shim instead of the actual CLI surface.

### Evidence
[scripts/run_simulation.py:1](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_simulation.py#L1) only imports `main` from the library, while [simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) exposes the reusable execution workflow and [simulator_execution.py:221](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L221) still owns argparse parsing. The same module writes bundle artifacts in [simulator_execution.py:285](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L285) and [simulator_execution.py:354](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L354), then switches to provenance and UI payload shaping at [simulator_execution.py:1582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1582) and [simulator_execution.py:1635](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1635). The tests also depend on simulation-planning fixture writers at [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56), which shows execution and planning surfaces are already too entangled.

### Requested Change
Move the CLI parser into `scripts/run_simulation.py` or a dedicated CLI wrapper, and move result-bundle packaging or UI payload generation behind a simulator packaging boundary. Keep the execution module focused on resolving runnable arm plans, invoking runtimes, and returning structured execution results.

### Acceptance Criteria
`src/flywire_wave/simulator_execution.py` no longer contains argparse handling or UI/export payload builders, and `scripts/run_simulation.py` becomes the real CLI entrypoint instead of a pass-through import. Execution helpers can be imported without pulling in packaging or presentation concerns.

### Verification
`make test`
`make smoke`