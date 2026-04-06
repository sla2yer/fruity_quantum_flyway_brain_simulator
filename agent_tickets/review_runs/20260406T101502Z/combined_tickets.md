# Combined Review Tickets

## package_structure_and_module_placement

# Package Structure And Module Placement Review Tickets

## PKGSTR-001 - Create A Review-Surfaces Namespace For Dashboard, Showcase, And Whole-Brain Context
- Status: open
- Priority: high
- Source: package_structure_and_module_placement review
- Area: review surfaces

### Problem
The repo's downstream review surfaces have become a real subsystem, but they are still scattered as root-level sibling modules. `dashboard_*`, `showcase_*`, `whole_brain_context_*`, and `review_surface_artifacts.py` now behave like one ownership cluster with multiple internal layers, yet the flat package hides that boundary and makes downstream UI/report work look interchangeable with unrelated pipeline code.

### Evidence
`src/flywire_wave/dashboard_session_planning.py` imports dashboard UI assembly, replay, morphology, scene/circuit context, experiment analysis, validation, simulator results, and whole-brain context metadata from one root-level module family. `src/flywire_wave/showcase_session_packaging.py` and `src/flywire_wave/whole_brain_context_packaging.py` both import `package_dashboard_session`, which shows dashboard packaging is already the shared downstream surface that showcase and whole-brain context build on. `src/flywire_wave/showcase_session_sources.py` reaches across dashboard, experiment-suite, validation, and review-surface helpers from one file. `src/flywire_wave/__init__.py` exports dashboard, showcase, and whole-brain-context modules directly beside simulation, validation, and preprocessing modules, which reinforces the flat grab-bag layout instead of the actual review-surface boundary.

### Requested Change
Introduce an explicit review-surface namespace, for example `src/flywire_wave/review_surfaces/` with subpackages such as `dashboard/`, `showcase/`, and `whole_brain_context/`, plus a shared helper module for packaged artifact alignment. Move each family's contract/planning/packaging/runtime helpers under its own subpackage and keep `scripts/29_dashboard_shell.py`, `scripts/35_showcase_session.py`, and `scripts/36_whole_brain_context_session.py` as thin wrappers over those new package entrypoints.

### Acceptance Criteria
Dashboard, showcase, and whole-brain-context modules no longer live as unrelated top-level siblings in `src/flywire_wave/`. Shared review-surface helpers are colocated with those packages instead of sitting at the root. The CLI wrappers for dashboard, showcase, and whole-brain context import stable entrypoints from the new package layout. Future review-surface work can stay inside the review-surface namespace without pulling more downstream UI/report modules into the root package.

### Verification
make test
make smoke

## PKGSTR-002 - Move Simulator Planning, Runtime, And Model Execution Into A Simulation Package
- Status: open
- Priority: high
- Source: package_structure_and_module_placement review
- Area: simulation runtime

### Problem
The runtime stack is organized by filename prefix instead of ownership boundary. `simulation_*`, `simulator_*`, `surface_wave_*`, `baseline_*`, and related runtime helpers all live at the package root even though they collectively implement one simulation subsystem with clear internal layers: planning, model-specific runtime, execution, packaging, and CLI entrypoints.

### Evidence
`src/flywire_wave/simulation_planning.py` is a large planning/orchestration module that imports coupling, geometry, hybrid morphology, manifest validation, mixed-fidelity policy, retinal flow, readout analysis, selection, simulator contracts, and stimulus handling from across the repo. `src/flywire_wave/simulator_execution.py` then composes baseline execution, hybrid runtime, planning, packaging, result contracts, and simulator runtime from more root-level siblings. `src/flywire_wave/surface_wave_execution.py` depends on simulator runtime, surface-wave solver/contracts, coupling, and synapse mapping, but still sits beside dashboard, validation, and showcase modules. `scripts/run_simulation.py` is already a thin wrapper around one simulation entrypoint, which is a strong signal that the library beneath it should expose a real `simulation` package boundary rather than a flat list of root modules.

### Requested Change
Create a dedicated simulation namespace such as `src/flywire_wave/simulation/` and move planning, runtime, execution, packaging, and CLI-facing helpers under it. Within that package, give model-specific code an internal home, for example `models/baseline.py`, `models/surface_wave/`, and a colocated runtime layer for morphology and timebase concerns. The goal is not a pure file shuffle; it is to make the simulation subsystem navigable as one package with explicit internal ownership.

### Acceptance Criteria
Simulation entrypoints no longer depend on a root package crowded with `simulation_*`, `simulator_*`, `surface_wave_*`, and model-specific runtime modules. Planning, execution, runtime, packaging, and model-specific code are package-local neighbors. `scripts/run_simulation.py` continues to act as a thin wrapper, but it now imports from the new simulation namespace instead of the flat root package. Import paths for manifest-driven simulation and surface-wave execution remain stable after the move.

### Verification
make test
make validate-manifest
make smoke

## PKGSTR-003 - Give Validation And Milestone Readiness Their Own Packages
- Status: open
- Priority: high
- Source: package_structure_and_module_placement review
- Area: validation and readiness

### Problem
Validation and readiness are now major release-gating subsystems, but they are still represented as many root-level files. The flat layout obscures the fact that `validation_*`, `validation_contract.py`, `validation_reporting.py`, `validation_ladder_smoke.py`, `readiness_contract.py`, and `milestone*_readiness.py` form a cohesive ladder-and-gate area with internal boundaries of their own.

### Evidence
`src/flywire_wave/validation_planning.py` pulls together experiment analysis, mixed-fidelity inspection, operator QA, simulation planning, surface-wave inspection, and validation contracts from across the repo, which shows validation is a cross-cutting workflow rather than an isolated helper. `src/flywire_wave/milestone13_readiness.py` imports simulation planning, stimulus packaging, validation layers, validation reporting, and readiness contracts in one milestone gate module. The root package currently includes a long run of `milestone6_readiness.py` through `milestone17_readiness.py`, all beside unrelated simulation, showcase, and preprocessing modules. `scripts/27_validation_ladder.py` and `scripts/28_milestone13_readiness.py` already expose validation and readiness as distinct CLI workflows, but the library layout beneath them still looks flat.

### Requested Change
Create a `src/flywire_wave/validation/` package for contracts, layer planners, validators, reporting, and smoke/package flows. Create a `src/flywire_wave/readiness/` package for milestone gates and shared readiness helpers, or nest readiness under `validation/` if that better matches ownership. Keep the numbered scripts as thin wrappers over the new package entrypoints instead of letting root-level milestone modules continue to accumulate.

### Acceptance Criteria
The root package no longer contains the milestone readiness modules as standalone siblings. Validation planning, layer execution, reporting, and smoke/package helpers are discoverable within a validation namespace. Readiness entrypoints import from a stable readiness package rather than reaching into many root-level modules. The new structure makes it obvious which files own layer validation versus milestone gating.

### Verification
make test
make smoke

## PKGSTR-004 - Consolidate Experiment Suite And Comparison Orchestration Under One Namespace
- Status: open
- Priority: medium
- Source: package_structure_and_module_placement review
- Area: experiments and analysis orchestration

### Problem
Experiment-suite orchestration, comparison logic, and downstream analysis/report packaging are spread across root-level siblings even though they form one domain boundary. That flat layout makes it hard to tell where experiment orchestration ends and where general simulation or UI code begins.

### Evidence
`src/flywire_wave/experiment_suite_planning.py` imports suite contracts alongside dashboard-session, experiment-analysis, simulation-planning, simulator-result, stimulus, and validation contracts, which is a strong sign that the suite planner is acting as a domain hub. `src/flywire_wave/experiment_suite_packaging.py` loads dashboard session metadata, experiment analysis metadata, simulator result metadata, validation metadata, and validation reporting from one packaging layer. `src/flywire_wave/experiment_comparison_core.py` stitches shared readout analysis, task-decoder analysis, and wave diagnostics into one comparison core, yet those modules all remain scattered at the root. `scripts/31_run_experiment_suite.py` is already a thin wrapper around suite execution, so the library beneath it can support a cleaner domain namespace.

### Requested Change
Create an experiment-orchestration namespace such as `src/flywire_wave/experiments/` or `src/flywire_wave/analysis/experiments/`. Move suite planning/execution/aggregation/packaging/reporting and comparison discovery/core/packaging under that namespace, together with the contracts they primarily own. If shared readout, task-decoder, or wave-diagnostic analysis code remains separate, give it a clear subpackage relationship instead of leaving the suite and comparison flows as root-level siblings.

### Acceptance Criteria
Experiment suite and comparison modules no longer appear as a scattered block of root-level files. Suite planning, execution, packaging, aggregation, and reporting live together under one package boundary, and comparison logic lives beside them in a way that makes ownership obvious. Downstream consumers such as dashboard and showcase pull from a stable experiment namespace rather than a mix of root-level modules.

### Verification
make test
make validate-manifest
make smoke
