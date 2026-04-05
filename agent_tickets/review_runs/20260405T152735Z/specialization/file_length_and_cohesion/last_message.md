# File Length And Cohesion Review Prompt

You are performing a focused code review for the FlyWire Wave Pipeline repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where files, modules, classes, or functions have grown too large or too mixed in responsibility, making this repo harder to navigate, test, and change safely.

## Repo Context

This repo is a preprocessing, packaging, and local review/simulation pipeline for FlyWire assets. It is not a live service. Most real implementation lives in the flat `src/flywire_wave/` package, so cohesion problems often show up as single modules becoming the de facto owner for several adjacent concerns.

Use these boundaries while reviewing:
- `src/flywire_wave/`: primary library code and the main source of actionable file-length/cohesion tickets
- `scripts/`: CLI entrypoints; usually acceptable when they parse args, dispatch subcommands, print summaries, and delegate into `src/flywire_wave/`
- `tests/`: local unit tests; useful both as evidence and as possible ticket targets when a test file has become a mixed-responsibility harness
- `docs/`: design and pipeline references; use them to understand intended ownership boundaries rather than as primary ticket targets
- `config/`, `manifests/`, `schemas/`: supporting contract/config artifacts; de-prioritize unless one has clearly become an unreadable multi-subsystem spec

Repo-safe validation commands:
- `make test`
- `make validate-manifest`
- `make smoke`

Do not require FlyWire-token or network-backed commands such as `make verify` or `make meshes` unless an issue specifically involves those entrypoints.

## Real Module Families

Review against the repo’s actual families, not generic app/service layers:
- Pipeline and asset-prep: `config.py`, `registry.py`, `selection.py`, `mesh_pipeline.py`, `geometry_*`, `coupling_*`, `synapse_mapping.py`, `operator_qa.py`
- Simulation/runtime: `simulation_planning.py`, `simulator_*`, `baseline_*`, `surface_wave_*`, `mixed_fidelity_*`, `hybrid_morphology_*`
- Stimulus and retinal input: `stimulus_*`, `retinal_*`
- Experiment orchestration and analysis: `experiment_*`, `shared_readout_analysis.py`, `task_decoder_analysis.py`
- Validation and readiness: `validation_*`, `milestone*_readiness.py`
- Local review/package surfaces: `dashboard_*`, `showcase_*`, `whole_brain_*`, `review_prompt_tickets.py`, `agent_tickets.py`

Modules most likely to have real cohesion drift are the orchestration, planning, and query families that bridge many of those groups:
- `src/flywire_wave/simulation_planning.py`
- `src/flywire_wave/showcase_session_planning.py`
- `src/flywire_wave/whole_brain_context_planning.py`
- `src/flywire_wave/experiment_suite_planning.py`
- `src/flywire_wave/dashboard_session_planning.py`
- `src/flywire_wave/experiment_comparison_analysis.py`
- `src/flywire_wave/experiment_suite_aggregation.py`
- `src/flywire_wave/experiment_suite_packaging.py`
- `src/flywire_wave/hybrid_morphology_runtime.py`
- `src/flywire_wave/whole_brain_context_query.py`
- `src/flywire_wave/validation_planning.py`
- `src/flywire_wave/simulator_execution.py`

## Focus

- Oversized library modules that interleave planning, contract normalization, asset discovery, execution, packaging, reporting, and UI state in one file
- Flat-package modules that have become “misc owners” for an entire subsystem because there is no stronger boundary
- Script files that quietly contain reusable library logic instead of serving as entrypoints
- Test files that mix multiple subsystems or accumulate private fixture/build helpers that should live in shared test utilities
- Split opportunities aligned to this repo’s real seams:
  contract/catalog
  planning/resolution
  execution/runtime
  packaging/export
  query/analysis
  UI state/presentation
  validation/reporting

## Important Repo-Specific Nuance

Treat these large-file categories differently:

- Thin CLI entrypoints in `scripts/` are often acceptable. `scripts/build_registry.py` and `scripts/run_simulation.py` show the intended pattern. Larger entrypoints such as `scripts/03_build_wave_assets.py`, `scripts/29_dashboard_shell.py`, `scripts/35_showcase_session.py`, and `scripts/36_whole_brain_context_session.py` may still be acceptable when most of the file is argparse or subcommand wiring plus delegation. Only ticket them when reusable planning, normalization, or domain logic is trapped in `scripts/` instead of `src/flywire_wave/`.
- Contract-heavy modules such as `geometry_contract.py`, `coupling_contract.py`, `validation_contract.py`, `simulator_result_contract.py`, `dashboard_session_contract.py`, `experiment_suite_contract.py`, `showcase_session_contract.py`, `whole_brain_context_contract.py`, `surface_wave_contract.py`, `retinal_contract.py`, `stimulus_contract.py`, `readout_analysis_contract.py`, `experiment_analysis_contract.py`, and `hybrid_morphology_contract.py` are intentionally dense. Large constant catalogs, builder/parser pairs, discovery helpers, and normalization helpers are not automatically a cohesion problem. Only ticket them when they also absorb runtime or planning behavior, mix multiple unrelated contract domains, or become materially hard to navigate as a single contract owner.
- Milestone readiness modules can legitimately aggregate one milestone’s verification surface. Only ticket them when they have become the only home for reusable logic that clearly belongs under shared `validation_*`, `dashboard_*`, `experiment_*`, or other family modules.
- Large tests are often mirrors of large planning or contract modules. Do not file tickets based on test size alone; file them when a test file spans unrelated subsystems or hides a reusable fixture framework inside one monolithic test module.
- `src/flywire_wave/dashboard_assets/` is first-party source, not generated output. It is in scope if file size is causing real cohesion problems across panes, overlays, replay, or export behavior.

## Skip Or De-Prioritize

- `data/raw/codex/`
- `data/interim/`
- `data/processed/`
- `flywire_codex/`
- Generated review artifacts such as `agent_tickets/review_runs/`
- Docs as primary ticket targets; use `README.md`, `AGENTS.md`, `docs/milestones.md`, and `docs/pipeline_notes.md` to understand intended seams

## Exclude

- Mechanical file splitting with no clear ownership payoff
- Complaints based on line count alone
- Tickets against large contract catalogs or CLI parsers when the file still has one coherent responsibility
- Issues better framed as abstraction debt, algorithm choice, API design, or missing tests
- Suggestions that would move or split generated, vendored, or external content

## Review Process

1. Start with the largest and most central `src/flywire_wave/` orchestration, planning, and query modules.
2. Decide whether the current size reflects one coherent responsibility or several interleaved ones.
3. Check `scripts/` for leaked library logic rather than penalizing argparse-heavy entrypoints.
4. Use `tests/` to confirm intended subsystem boundaries and to spot cross-subsystem test harness drift.
5. Prefer tickets where a clearer ownership split would reduce future change risk along this repo’s real families.
6. Use docs and config artifacts to understand intended boundaries, not as the main ticket surface.
7. Skip speculative refactors that mostly reshuffle helpers without improving navigation or reviewability.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with the prefix `FILECOH`, for example `FILECOH-001`.
- Make the case for why the current size or shape is a practical problem in this repo.
- Cite concrete files and line references.
- Describe a better ownership boundary, not just “split the file.”
- When relevant, name the target family boundary explicitly, for example contract vs planning, planning vs packaging, execution vs reporting, or script vs library.
- If no strong issues are present, say no tickets are recommended.

## Verification Guidance

For each ticket’s verification section, prefer repo-safe checks:
- `make test`
- `make validate-manifest` when manifest, planning, or contract paths are touched
- `make smoke` when both should still pass

Avoid requiring token-backed or network-backed pipeline steps unless the ticket is specifically about those code paths.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# File Length And Cohesion Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: file_length_and_cohesion review
- Area: <module / subsystem>

### Problem
<what has become too large or too mixed>

### Evidence
<specific files, lines, and why the current shape hurts>

### Requested Change
<target split, boundary, or ownership change>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or review checks that should still pass after the refactor>

Return only the review tickets markdown.