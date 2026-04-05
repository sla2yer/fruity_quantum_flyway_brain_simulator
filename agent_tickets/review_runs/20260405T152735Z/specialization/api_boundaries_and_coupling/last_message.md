# API Boundaries And Coupling Review Prompt

You are performing a focused code review of the FlyWire Wave pipeline repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where public seams, data contracts, or dependency relationships make this repo harder to extend or reason about safely. In this repo, prioritize boundaries between runtime config, manifest/schema/design-lock validation, thin CLI wrappers, versioned bundle metadata, and the library modules that own those contracts.

## Focus

- Leaky boundaries between `Makefile` targets, `scripts/*.py`, and `src/flywire_wave/`. The wrappers are intended to be thin; flag duplicated defaults, path resolution, validation rules, or bundle-discovery logic.
- Config coupling in `src/flywire_wave/config.py`, especially repo-root-relative `config.paths`, injected derived fields, and hidden assumptions about the public FAFB datastack or materialization `783`.
- Manifest/schema/design-lock drift across `src/flywire_wave/manifests.py`, `schemas/milestone_1_experiment_manifest.schema.json`, `manifests/`, `config/milestone_1_design_lock.yaml`, and manifest-driven runners such as `scripts/04_validate_manifest.py`, `scripts/run_simulation.py`, and `scripts/20_experiment_comparison_analysis.py`.
- Pipeline handoff coupling across `registry.py`, `selection.py`, `mesh_pipeline.py`, `geometry_contract.py`, and `coupling_contract.py`, especially ownership of `selected_root_ids`, `synapse_registry.csv`, and `asset_manifest.json`.
- Versioned contract drift in `*_contract.py` modules and their consumers. Treat metadata such as `stimulus_bundle.json`, `retinal_input_bundle.json`, `simulator_result_bundle.json`, `experiment_analysis_bundle.json`, `dashboard_session.json`, `showcase_session.json`, and `whole_brain_context_session.json` as true external seams.
- Cases where planners, packagers, visualizers, or tests reconstruct filenames, JSON shapes, fallback hierarchies, or contract versions instead of using one library-owned contract helper.
- Contract disagreement between library entrypoints, CLI surfaces, and tests like `tests/test_config_paths.py`, `tests/test_manifest_validation.py`, `tests/test_registry.py`, and `tests/test_*contract.py`.

## Distinguish Internal vs Public

- Treat config YAML fields, manifest/schema/design-lock files, `Makefile` behavior, CLI flags in `scripts/`, versioned bundle metadata, and contract modules under `src/flywire_wave/*_contract.py` as primary contract surfaces.
- Treat helpers used only within one subsystem as internal unless they are re-exported, referenced by versioned metadata, or clearly exercised as a contract by scripts or tests.
- Do not file tickets just because `src/flywire_wave/__init__.py` exports many modules. The issue must show real downstream coupling or a boundary other code depends on.

## Exclude

- Pure file-size complaints
- Feedback that is mostly about performance
- Style nits and naming-only issues
- Abstractions whose main problem is unnecessary ceremony rather than coupling
- Internal helper reshuffles with no impact on config, CLI, manifest, schema, or bundle-facing behavior

## Usually Out Of Scope

- `flywire_codex/` vendored upstream code unless the repo's adapter boundary to it is the issue
- `data/interim/` and `data/processed/` generated outputs themselves, except for the code and metadata contracts that define them
- `data/raw/codex/` snapshot contents unless the issue is about source autodiscovery, column normalization, or snapshot assumptions
- `agent_tickets/review_runs/` generated review artifacts
- Most `tests/fixtures/` payloads except as evidence of an intended contract

## Review Process

1. Identify the actual public seams first: `config/`, `manifests/`, `schemas/`, `Makefile`, `scripts/`, contract modules in `src/flywire_wave/`, and the bundle metadata they write and consume. Use `docs/pipeline_notes.md` and relevant design notes in `docs/` as contract references when helpful.
2. Look for places where one subsystem must know another subsystem's filenames, path conventions, JSON layout, contract version, fallback policy, or default CLI flags without going through a canonical library-owned interface.
3. Prefer tickets that tighten ownership: one path builder, one validator, one metadata normalizer, one planner, or one CLI-to-library translation layer.
4. Only emit issues where boundary design is the main reason to act.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example `APICPL-001`.
- Cite concrete files and lines.
- Explain what the public contract is in practice and how the current boundary leaks, couples, or duplicates ownership.
- Recommend a contract or ownership change that would make the system easier to evolve without breaking downstream configs, manifests, scripts, or bundle consumers.
- If no strong issues are present, say no tickets are recommended.

## Verification Guidance

- Prefer `make test`, `make validate-manifest`, or `make smoke`.
- When relevant, cite the narrowest command that exercises the boundary, such as `make registry`, `make select`, `make assets`, `make simulate`, `make compare-analysis`, `make dashboard`, `make showcase-session`, `make whole-brain-context`, or `make review-tickets`.
- Call out when verification requires `FLYWIRE_TOKEN` or network access. `make verify` and `make meshes` are not local-only checks.
- Prefer targeted unit tests when they map cleanly to the contract under review.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# API Boundaries And Coupling Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: api_boundaries_and_coupling review
- Area: <module / subsystem>

### Problem
<what boundary or coupling issue exists>

### Evidence
<specific files, lines, and why this creates risk>

### Requested Change
<the contract or ownership improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, contract checks, or command-level validation>