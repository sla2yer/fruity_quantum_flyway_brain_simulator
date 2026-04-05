# Overengineering And Abstraction Load Review Tickets

## OVR-001 - Remove the second full resolver from `compare-analysis`
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / experiment comparison analysis

### Problem
The `make compare-analysis` path resolves the same manifest twice. `execute_experiment_comparison_workflow()` builds a full simulation plan, then asks for a separate readout-analysis plan through a helper that just rebuilds the same simulation plan and extracts one field. That extra abstraction hop does not buy a second real workflow in this repo.

### Evidence
- [src/flywire_wave/experiment_comparison_analysis.py:459](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L459) resolves `simulation_plan`, then [src/flywire_wave/experiment_comparison_analysis.py:465](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L465) resolves `analysis_plan` separately.
- [src/flywire_wave/simulation_planning.py:722](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L722) shows `resolve_manifest_readout_analysis_plan()` immediately calling [src/flywire_wave/simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) and only returning `readout_analysis_plan`.
- The public happy path is the single manifest-driven target at [Makefile:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L145), not two distinct planning backends.

### Requested Change
Resolve the manifest once in the comparison workflow and read `readout_analysis_plan` directly from that normalized simulation plan. If a helper is still wanted, make it a pure extractor from an existing plan rather than a second full resolver.

### Acceptance Criteria
- `execute_experiment_comparison_workflow()` performs one top-level manifest/config/schema/design-lock resolution.
- There is no public helper that re-runs full simulation planning solely to return `readout_analysis_plan`.
- Experiment-analysis outputs remain unchanged.

### Verification
- `make test`
- `make smoke`

## OVR-002 - Collapse duplicate CLI-runner orchestration in the review tooling
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: `agent_tickets` / `review_prompt_tickets`

### Problem
The repo carries two near-identical subprocess wrappers for Codex/Codel jobs: one for agent tickets and one for review-prompt jobs. The only real extension point here is runner selection, which is already centralized. Maintaining two staging/streaming/artifact-sync implementations adds ceremony without adding a second meaningful backend.

### Evidence
- [src/flywire_wave/agent_tickets.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L299) and [src/flywire_wave/review_prompt_tickets.py:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L154) both create temp staging dirs, build the same `runner exec --json --cd ... --sandbox ... --output-last-message ...` command, stream output through [src/flywire_wave/agent_tickets.py:224](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L224), and return the same artifact paths.
- Artifact syncing is duplicated in [src/flywire_wave/agent_tickets.py:287](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L287) and [src/flywire_wave/review_prompt_tickets.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L142).
- The review flow at [src/flywire_wave/review_prompt_tickets.py:335](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L335) exists only to run the repo’s `review-tickets` path from [Makefile:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L133), not to support a distinct job-execution platform.

### Requested Change
Introduce one shared CLI prompt-job executor and let both ticket execution and review-prompt execution compose it. Keep the specialization/review sequencing logic, but remove the duplicated subprocess/staging/artifact code.

### Acceptance Criteria
- Only one implementation owns subprocess spawning, stream handling, and artifact-sync for CLI-backed prompt jobs.
- `run_ticket()` and the review workflow still emit the same prompt/stdout/stderr/last-message artifacts and summaries.
- Existing ticket and review tests still pass.

### Verification
- `make test`
- `make smoke`

## OVR-003 - Remove the unused “partial arm plan” execution path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / simulator execution

### Problem
Execution supports a second hypothetical arm-plan shape where bundle metadata is missing and must be reconstructed from fragments. The actual repo happy path never produces that shape: the planner already materializes `result_bundle.metadata` for every arm before execution. Carrying both shapes creates unnecessary indirection and a second source of truth in the core `baseline` / `surface_wave` path.

### Evidence
- [src/flywire_wave/simulation_planning.py:674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L674), [src/flywire_wave/simulation_planning.py:686](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L686), and [src/flywire_wave/simulation_planning.py:687](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L687) always attach `result_bundle` metadata during plan construction.
- [src/flywire_wave/simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172) and [src/flywire_wave/simulator_execution.py:178](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L178) feed those normalized arm plans straight into execution.
- [src/flywire_wave/simulator_execution.py:520](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L520) still falls back to rebuilding metadata from `manifest_reference`, `arm_reference`, `determinism`, `selected_assets`, and runtime state.

### Requested Change
Make planner-produced `result_bundle.metadata` the only supported execution input. Delete the fallback metadata reconstruction path and simplify processed-results-dir resolution around that single normalized arm-plan shape.

### Acceptance Criteria
- Simulator execution requires normalized arm plans with `result_bundle.metadata`.
- Missing bundle metadata fails clearly instead of silently reconstructing a second metadata representation.
- Baseline and surface-wave bundle ids, paths, and artifacts remain unchanged for manifest-driven runs.

### Verification
- `make test`
- `make milestone9-readiness`
- `make milestone10-readiness`

## OVR-004 - Narrow the dashboard build API to the repo’s real entry path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: dashboard session planning / CLI

### Problem
Dashboard packaging is exposed as a generalized source-mode framework with manifest, experiment, and explicit per-bundle assembly modes. In this repo, the documented happy path is manifest-driven build plus open/export of an already packaged session. Keeping all three public acquisition modes makes the main local flow harder to understand and forces the planner to act like a bundle-orchestration framework the repo does not actually need.

### Evidence
- The documented workflow is manifest-driven at [Makefile:148](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L148) and [Makefile:151](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L151), with packaged-session export at [Makefile:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L154).
- The public CLI still exposes experiment and explicit bundle assembly knobs at [scripts/29_dashboard_shell.py:61](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L61) and [scripts/29_dashboard_shell.py:68](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L68).
- The planner defines three source modes at [src/flywire_wave/dashboard_session_planning.py:136](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L136) and exposes a broad multi-input public signature at [src/flywire_wave/dashboard_session_planning.py:158](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L158).
- The alternate modes are actively maintained for equivalence in [tests/test_dashboard_session_planning.py:193](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L193) and [tests/test_dashboard_session_planning.py:243](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L243).

### Requested Change
Keep one public dashboard build path centered on manifest-driven planning, plus the existing open/export operations on packaged sessions. If explicit bundle assembly is still useful for fixtures, move it behind a private helper instead of the public CLI and public planner signature.

### Acceptance Criteria
- `scripts/29_dashboard_shell.py build` and `resolve_dashboard_session_plan()` no longer advertise three equivalent acquisition modes publicly.
- `make dashboard`, `make dashboard-open`, and packaged-session export behavior remain intact.
- Fixture-only alternate assembly, if retained, is internal rather than part of the main user-facing API.

### Verification
- `make test`
- `make milestone14-readiness`