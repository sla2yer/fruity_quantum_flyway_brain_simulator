# Package Structure And Module Placement Review Prompt

You are performing a focused code review for the `flywire-wave` repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where package layout, directory structure, module placement, or ownership boundaries are making this repo harder to navigate, extend, or maintain safely.

This repo now spans much more than the original preprocessing pipeline. `README.md` and `src/flywire_wave/` show one mostly flat Python package that covers preprocessing, stimulus and retinal inputs, geometry and coupling assets, simulation planning and execution, experiment analysis and suite orchestration, validation and readiness reporting, local review surfaces, and agent-ticket tooling. Your job is to decide where that flat layout is no longer matching real subsystem ownership.

## Repo Context

Inspect at least:

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/flywire_wave/`
- `scripts/`
- `tests/`

Treat `src/flywire_wave/` as the primary review surface. Use `scripts/` and `tests/` mainly to understand ownership boundaries, dependency direction, and whether thin wrappers or test helpers are masking a missing package boundary.

## Focus

Pay particular attention to whether these filename families are still just sibling modules or have become real subpackage candidates:

- Core pipeline and shared foundations: `config.py`, `auth.py`, `io_utils.py`, `manifests.py`, `registry.py`, `selection.py`, `mesh_pipeline.py`
- Geometry, operators, and coupling: `geometry_*`, `surface_operators.py`, `synapse_mapping.py`, `coupling_*`, `operator_qa.py`
- Stimulus and retinal input flow: `stimulus_*`, `retinal_*`, `scene_playback.py`
- Simulation and runtime flow: `baseline_*`, `simulation_*`, `simulator_*`, `hybrid_morphology_*`, `mixed_fidelity_*`
- Surface-wave execution and inspection: `surface_wave_*`, `wave_structure_analysis.py`
- Analysis and experiment orchestration: `shared_readout_analysis.py`, `readout_analysis_contract.py`, `task_decoder_analysis.py`, `experiment_analysis_*`, `experiment_comparison_*`, `experiment_suite_*`
- Validation and milestone readiness: `validation_*`, `readiness_contract.py`, `milestone*_readiness.py`
- Review surfaces and packaging flows: `dashboard_*`, `showcase_*`, `whole_brain_context_*`, `review_surface_artifacts.py`
- Agent review tooling: `agent_tickets.py`, `review_prompt_tickets.py`, `review_ticket_backlog.py`

For each family, reason explicitly about whether it should remain a set of files in one flat package or become a true directory boundary such as `flywire_wave/dashboard/`, `flywire_wave/showcase/`, `flywire_wave/validation/`, `flywire_wave/experiment_suite/`, `flywire_wave/stimulus/`, `flywire_wave/retinal/`, `flywire_wave/simulation/`, or `flywire_wave/review/`. Do not assume those names are correct; justify any proposed boundary from the current code layout.

## Distinguish File Splits From Package Moves

Only emit a ticket when package or directory ownership is the primary problem.

In scope:

- A prefix-heavy family has grown contract, planning, execution, packaging, and UI modules that would be easier to own as a subpackage.
- Related modules live beside unrelated peers, obscuring dependency direction or review surface boundaries.
- Test support or CLI support placement is hiding a missing shared ownership boundary.

Out of scope:

- A module is large and should be split internally, but the correct ownership still stays in the same package.
- A rename or move would mostly reshuffle imports without clarifying subsystem ownership.
- The complaint is really about local cohesion inside one file rather than directory or package placement.
- The numbered order of scripts in `scripts/` looks messy, but the library ownership beneath them is still sound.

## Repo-Specific Heuristics

- `src/flywire_wave/` is currently very flat. Treat repeated prefixes as a signal to investigate, not as automatic proof that a subpackage is needed.
- The `dashboard_*`, `showcase_*`, `whole_brain_context_*`, `experiment_suite_*`, `experiment_comparison_*`, `validation_*`, `surface_wave_*`, `retinal_*`, and mixed `simulation_*` plus `simulator_*` families are the most likely places where directory boundaries may now lag the architecture.
- `scripts/` are mostly thin CLI wrappers around library modules. Do not create package-structure tickets driven only by wrapper naming, milestone numbering, or CLI argument shape.
- `tests/` is also flat. Only file a test-structure ticket if helpers such as `tests/cli_startup_test_utils.py`, `tests/simulation_planning_test_support.py`, or `tests/showcase_test_support.py` are clearly in the wrong shared support location or if domain test ownership is materially obscured.
- If you recommend moving dashboard-related Python modules, distinguish that from the shipped static assets in `src/flywire_wave/dashboard_assets/`. Static asset packaging alone is not a package-structure issue.
- If you recommend a new subpackage, prefer boundaries that make dependency direction clearer, for example keeping CLI wrappers in `scripts/`, keeping downstream review surfaces from becoming a grab bag of unrelated modules, and avoiding circular ownership between preprocessing, simulation, analysis, and UI/report packaging.

## Exclude

Do not create package-structure tickets based on:

- `flywire_codex/`, which is an upstream vendored submodule
- `data/raw/codex/`, `data/interim/`, or `data/processed/`, which are source snapshots or generated outputs
- `src/flywire_wave.egg-info/` and any `__pycache__/` directories
- `config/`, `manifests/`, `schemas/`, and `docs/` unless they directly reveal a mismatched Python ownership boundary
- `tests/fixtures/` by itself
- `src/flywire_wave/dashboard_assets/` by itself

## Review Process

1. Identify the repo's major subsystem families from `README.md`, `Makefile`, `src/flywire_wave/`, `scripts/`, and `tests/`.
2. Map where the code already has real ownership clusters versus where it is only grouped by filename prefix inside one flat package.
3. Look for cases where a true subpackage or directory boundary would improve navigation, dependency clarity, review surface isolation, or future refactoring safety.
4. Separate file-level cleanup from package-boundary changes. Only emit a ticket when the directory or package move is the main architectural payoff.
5. For each proposed ticket, name the current files involved and the target ownership boundary or subpackage shape.
6. If no strong package-boundary issues are present, say no tickets are recommended.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with the prefix `PKGSTR`, for example `PKGSTR-001`.
- Cite concrete files and explain the ownership-boundary problem, not just that the package feels flat.
- State why the issue is a package-structure problem rather than a local file-splitting problem.
- Recommend a target package, directory boundary, or ownership grouping.
- Prefer tickets that would make future work safer across major subsystem families, not just neater on disk.

## Verification Expectations

When proposing verification steps, use repo-safe commands that are documented and do not require FlyWire credentials:

- `make test`
- `make validate-manifest`
- `make smoke`

Use `make validate-manifest` when the proposed restructure would affect manifest, config, or planning/import paths that participate in that validation flow.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Package Structure And Module Placement Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: package_structure_and_module_placement review
- Area: <package / subsystem>

### Problem
<what package-structure or module-placement issue exists>

### Evidence
<specific files, directories, and why the current layout hurts>

### Requested Change
<the target package, directory, or ownership change>

### Acceptance Criteria
<observable completion criteria that distinguish a real package-boundary fix from a mere file shuffle>

### Verification
<repo-safe checks that should still pass after the restructure>

Return only the review tickets markdown. If no strong issues are present, say no tickets are recommended.
