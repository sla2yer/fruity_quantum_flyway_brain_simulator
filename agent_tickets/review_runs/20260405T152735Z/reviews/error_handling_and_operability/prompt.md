Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Prompt set slug: error_handling_and_operability

Run the repo-specific review prompt below against this repository.
Stay in review mode and return only the final ticket markdown requested by the prompt.

# Error Handling And Operability Review Prompt

You are performing a focused code review of the FlyWire Wave pipeline repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where failures are hard to diagnose, guardrails are weak, error handling is inconsistent, or operator workflows in this repo are more fragile than they need to be.

## Repo Context

- This repo preprocesses FlyWire metadata and meshes into wave-ready local assets, then runs local simulation, comparison analysis, and offline review/report packaging.
- Treat the documented safe validation loop as the baseline operator workflow: `make test`, `make validate-manifest`, and `make smoke`.
- The main preprocessing path is `make verify`, `make registry`, `make select`, `make meshes`, and `make assets`. `make all` runs `verify -> registry -> select -> meshes -> assets`.
- Important downstream operator-facing commands include `make preview`, `make operator-qa`, `make coupling-inspect`, `make simulate`, `make compare-analysis`, and `make review-tickets`.
- The `Makefile` auto-selects `.venv/bin/python` when that virtualenv exists.
- Current docs and config assume the public FAFB datastack `flywire_fafb_public` and materialization version `783`.

## Required Repo Context To Inspect

Read these before filing tickets:

- `AGENTS.md`
- `README.md`
- `Makefile`
- `docs/pipeline_notes.md`
- `scripts/`
- `src/flywire_wave/`
- `tests/`

Prioritize these operator entrypoints and their backing modules:

- `scripts/00_verify_access.py`
- `scripts/build_registry.py`
- `scripts/01_select_subset.py`
- `scripts/02_fetch_meshes.py`
- `scripts/03_build_wave_assets.py`
- `scripts/04_validate_manifest.py`
- `scripts/05_preview_geometry.py`
- `scripts/06_operator_qa.py`
- `scripts/08_coupling_inspection.py`
- `scripts/run_simulation.py`
- `scripts/20_experiment_comparison_analysis.py`
- `scripts/run_review_prompt_tickets.py`
- `src/flywire_wave/config.py`
- `src/flywire_wave/auth.py`
- `src/flywire_wave/registry.py`
- `src/flywire_wave/selection.py`
- `src/flywire_wave/mesh_pipeline.py`
- `src/flywire_wave/manifests.py`
- `src/flywire_wave/review_prompt_tickets.py`

Use tests to confirm intended behavior, especially:

- `tests/test_config_paths.py`
- `tests/test_manifest_validation.py`
- `tests/test_mesh_pipeline_fetch.py`
- `tests/test_simulator_execution.py`
- `tests/test_experiment_comparison_analysis.py`
- `tests/test_run_review_prompt_tickets.py`

## Operator Prerequisites And Artifact Surfaces

Keep these repo-specific prerequisites in mind while reviewing:

- `CONFIG=config/local.yaml` and `config.paths.*` drive most CLI paths. Relative paths are intended to resolve from the repo root, not the caller's cwd.
- `.env` with `FLYWIRE_TOKEN` and network access are required for `make verify` and `make meshes`.
- `MANIFEST`, `SCHEMA`, and `DESIGN_LOCK` default to `manifests/examples/milestone_1_demo.yaml`, `schemas/milestone_1_experiment_manifest.schema.json`, and `config/milestone_1_design_lock.yaml`.
- `data/raw/codex/` holds manual Codex CSV snapshots. `classification.csv` is required for registry building; several other CSVs are optional and auto-detected.
- `data/interim/` and `data/processed/` are reproducible outputs, including subset bundles, raw mesh/skeleton caches, `data/processed/asset_manifest.json`, coupling artifacts, simulator result bundles, and packaged analysis/report outputs.
- `agent_tickets/review_runs/<timestamp>/` is the artifact root for `make review-tickets`.

## Focus

Prioritize issues in these repo-specific areas:

- Missing or ambiguous error messages around config loading, path resolution, manifest/schema/design-lock mismatches, or missing runtime inputs.
- Weak precondition checks before expensive or stateful steps such as FlyWire access, registry building, subset generation, mesh fetches, asset builds, simulation, comparison analysis, and ticket generation.
- Auth and environment handling around `.env`, `FLYWIRE_TOKEN`, local secret syncing, missing Python dependencies, transient FlyWire/materialize failures, and materialization-version mismatches.
- Registry and selection failures caused by missing Codex exports, optional-source autodetection, absent registry outputs, bad preset selection, or selected root IDs drifting out of sync with the canonical registries.
- Mesh-fetch operability problems around cache hits versus invalid cache recovery, forced refetch behavior, optional skeleton failures, partial success, and whether `asset_manifest.json` leaves enough audit trail for operators to understand what happened.
- Asset-build failures where missing raw meshes, malformed geometry, QA failures, or coupling-materialization issues are easy to miss or produce unclear next steps.
- Offline report/inspection commands that depend on already-built local artifacts but do not clearly explain what is missing or where the operator should look.
- Manifest-driven simulation and comparison-analysis paths where bundle discovery, incomplete coverage, or packaged output locations are hard to debug from emitted output.
- `make review-tickets` and the parallel prompt workflow when specialization/review jobs fail, partially succeed, or leave operators unsure which artifact or log to inspect.

## Exclude

- Pure feature requests.
- Minor wording nits in otherwise clear messages.
- Issues that are mainly about algorithm quality, modeling choices, or architecture rather than operability.
- Test-only complaints unless they directly hide or confuse operator-facing failure behavior.
- Issues inside `flywire_codex/`, generated outputs under `data/interim/` or `data/processed/`, raw snapshots under `data/raw/codex/`, or generated review outputs under `agent_tickets/review_runs/`, unless repo code mishandles those surfaces.
- Expected hard failures that are already explicit, actionable, and name the missing file, env var, command, or prerequisite.

## Review Process

1. Start from `AGENTS.md`, `README.md`, `Makefile`, and `docs/pipeline_notes.md` to understand the intended safe validation loop, pipeline order, and artifact contract.
2. Inspect the operator and automation entrypoints in `scripts/` and the supporting library modules in `src/flywire_wave/` that shape their failures and emitted output.
3. Prefer failure paths that would waste operator time during real local runs, especially long preprocessing or packaging workflows.
4. Use the relevant tests to confirm intended behavior before filing a ticket.
5. Emit only issues where error handling or operability is the primary concern.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with the prefix `OPS-`, for example `OPS-001`.
- Cite the concrete code path and the current failure behavior.
- Explain why the present behavior would confuse, slow down, or mislead an operator using the documented repo workflows.
- Recommend a concrete guardrail, validation step, status summary, artifact hint, or error-shaping change.
- Prefer verification steps that use the repo’s real commands, such as `make smoke`, `make verify`, `make registry`, `make select`, `make meshes`, `make assets`, `make simulate`, `make compare-analysis`, or `make review-tickets REVIEW_TICKETS_ARGS='--dry-run'`, whichever is most relevant.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Error Handling And Operability Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: error_handling_and_operability review
- Area: <module / subsystem>

### Problem
<what failure-path or operability issue exists>

### Evidence
<specific files, lines, commands, and observed behavior>

### Requested Change
<the guardrail or error-handling improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, CLI checks, or repro steps>

Return only the final ticket markdown.
