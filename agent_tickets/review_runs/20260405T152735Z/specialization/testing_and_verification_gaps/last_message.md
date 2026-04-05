# Testing And Verification Gaps Review Prompt

You are performing a focused code review of the FlyWire Wave pipeline repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where important behavior can regress without the repo's local tests, contract validators, deterministic smoke fixtures, or subsystem readiness commands catching it. Prioritize gaps that could let a meaningful regression through in preprocessing, versioned bundle contracts, manifest/config validation, simulation and analysis packaging, or readiness workflows.

## Repo Context

- Baseline safe loop: `make test`, `make validate-manifest`, and `make smoke`.
- `make test` runs `python -m unittest discover -s tests -v`.
- Deterministic validation smoke surfaces include `make validation-ladder-smoke`, plus layer-level commands `make numerical-validate`, `make morphology-validate`, `make circuit-validate`, and `make task-validate`.
- Main preprocessing path: `make registry`, `make select`, `make meshes`, and `make assets`. `make all` runs `verify -> registry -> select -> meshes -> assets`.
- Feature-specific verification entrypoints include `make milestone6-readiness`, `make milestone7-readiness`, `make milestone8a-readiness`, `make milestone8b-readiness`, `make milestone9-readiness`, `make milestone10-readiness`, `make milestone11-readiness`, `make milestone12-readiness`, `make milestone13-readiness`, `make milestone14-readiness`, `make milestone15-readiness`, and `make milestone17-readiness`.
- `make verify` and `make meshes` require `.env` with `FLYWIRE_TOKEN` plus network access; do not default to asking for live-network tests when a local fixture-based test can protect the contract.
- Current docs and tests assume the public FAFB datastack and materialization version `783`.

## Required Repo Context To Inspect

Read at least `AGENTS.md`, `README.md`, `Makefile`, `docs/pipeline_notes.md`, `docs/milestones.md`, `scripts/`, `src/flywire_wave/`, and `tests/`.

Prioritize these contract and workflow owners:
- `src/flywire_wave/config.py`, `src/flywire_wave/manifests.py`, `src/flywire_wave/registry.py`, `src/flywire_wave/selection.py`, and `src/flywire_wave/mesh_pipeline.py`
- versioned contract modules such as `geometry_contract.py`, `coupling_contract.py`, `stimulus_contract.py`, `retinal_contract.py`, `surface_wave_contract.py`, `simulator_result_contract.py`, `experiment_analysis_contract.py`, `validation_contract.py`, `dashboard_session_contract.py`, `experiment_suite_contract.py`, `showcase_session_contract.py`, `whole_brain_context_contract.py`, and `hybrid_morphology_contract.py`
- thin CLI and readiness entrypoints such as `scripts/04_validate_manifest.py`, `scripts/build_registry.py`, `scripts/01_select_subset.py`, `scripts/02_fetch_meshes.py`, `scripts/03_build_wave_assets.py`, `scripts/run_simulation.py`, `scripts/20_experiment_comparison_analysis.py`, `scripts/27_validation_ladder.py`, and the `scripts/*milestone*_readiness.py` commands

Use tests as contract evidence, especially:
- `tests/test_manifest_validation.py`, `tests/test_registry.py`, `tests/test_selection.py`
- `tests/test_mesh_pipeline_fetch.py`, `tests/test_mesh_pipeline_build.py`, `tests/test_operator_contract.py`
- `tests/test_stimulus_registry.py`, `tests/test_stimulus_generators.py`, `tests/test_retinal_geometry.py`, `tests/test_retinal_contract.py`
- `tests/test_simulator_execution.py`, `tests/test_experiment_suite_execution.py`
- `tests/test_validation_contract.py`, `tests/test_validation_planning.py`, `tests/test_validation_reporting.py`
- readiness tests such as `tests/test_milestone13_readiness.py`, `tests/test_milestone14_readiness.py`, `tests/test_milestone15_readiness.py`, and `tests/test_milestone17_readiness.py`

## Fixture Strategy

Assume the intended verification style is local and deterministic:
- many tests create tiny registries, manifests, meshes, and bundle trees in `TemporaryDirectory` rather than depending on live FlyWire access
- committed fixtures in `tests/fixtures/` are small contract fixtures and baselines, especially `manifest_stimulus_cases.yaml`, `stimulus_resolution_cases.yaml`, `stimulus_generator_cases.yaml`, `retinal_geometry_cases.yaml`, `operator_metadata_fixture.json`, and `validation_ladder_smoke_baseline.json`
- prefer tickets that ask for the narrowest missing fixture, unittest module, smoke assertion, or readiness check, not vague “add more tests” guidance

## Focus

- Core handoff contracts that write and later consume canonical artifacts: manifest/schema/design-lock validation, `selected_root_ids`, subset bundles, `synapse_registry.csv`, geometry and operator bundles, `asset_manifest.json`, simulator result bundles, analysis bundles, validation ladder bundles, dashboard packages, showcase packages, and whole-brain-context packages.
- Behavior that docs promise as deterministic, offline, or versioned, but whose tests only cover indirect happy paths and not the contract itself.
- Failure or fallback paths already represented in code but weakly exercised, such as optional-source autodetection, cache hit versus refetch, blocked mapping or fallback status, missing perturbation coverage, resume-safe suite execution, bundle discovery, and readiness report audits.
- CLI wrappers and readiness commands whose documented command surface is not actually protected by tests, smoke fixtures, or targeted script-level assertions.
- Cases where `make smoke`, `make validation-ladder-smoke`, or the relevant `make milestone*-readiness` target could still pass even if a meaningful repo contract regressed.
- Areas where a subsystem has a readiness command, but the underlying tests do not directly protect the invariants that command claims to verify.
- Docs-to-tests gaps. Treat `docs/pipeline_notes.md` and `docs/milestones.md` as current references; older milestone note paths are secondary evidence only.

## Exclude

- Requests for tests on low-risk trivia or pure refactors.
- Broad “add more tests” tickets without a concrete failing contract.
- Issues that are mainly about performance, architecture, or modeling quality rather than verification gaps.
- Live-network coverage requests for `make verify` or `make meshes` when a stubbed or local contract test would be the right protection.
- Issues inside `flywire_codex/`, raw snapshot contents under `data/raw/codex/`, generated outputs under `data/interim/` or `data/processed/`, generated review runs under `agent_tickets/review_runs/`, or research/media docs under `docs/research_pdfs/`, unless repo code mishandles those surfaces.
- Gaps that are already clearly intentional and documented.

## Review Process

1. Map the core workflows: manifest validation; registry/select/meshes/assets; simulate/compare-analysis; validation ladder; readiness packaging.
2. Compare the workflow and contract docs against the actual unit tests, smoke commands, and readiness tests.
3. Prefer gaps where a concrete regression could slip past `make test`, `make smoke`, `make validation-ladder-smoke`, or the relevant `make milestone*-readiness` target.
4. Recommend the narrowest useful protection: a direct unittest, a committed fixture or baseline, a deterministic script smoke test, or a readiness assertion.
5. Emit only actionable tickets with one concrete missing protection each.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with the prefix `TESTGAP-`, for example `TESTGAP-001`.
- Cite the specific code path, the missing coverage, and the likely regression it would fail to catch.
- Name the exact test module, smoke command, fixture file, or readiness command that should cover it when that is inferable.
- Prefer verification steps that use real repo commands such as `make test`, `make validate-manifest`, `make smoke`, `make validation-ladder-smoke`, or the relevant `make milestone*-readiness` target.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Testing And Verification Gaps Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: testing_and_verification_gaps review
- Area: <module / subsystem>

### Problem
<what important behavior is under-protected>

### Evidence
<specific files, lines, tests, fixture gaps, and validation gaps>

### Requested Change
<the missing tests, fixtures, smoke coverage, or readiness assertion>

### Acceptance Criteria
<observable completion criteria>

### Verification
<the exact unittest modules, fixture checks, or repo commands that should pass once the gap is closed>

Return only the final ticket markdown.