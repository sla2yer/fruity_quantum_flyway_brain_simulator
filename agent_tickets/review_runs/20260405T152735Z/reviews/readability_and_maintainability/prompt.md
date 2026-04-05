Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Prompt set slug: readability_and_maintainability

Run the repo-specific review prompt below against this repository.
Stay in review mode and return only the final ticket markdown requested by the prompt.

# FlyWire Wave Readability And Maintainability Review Prompt

You are performing a focused code review of the FlyWire Wave Pipeline repository. Stay in review mode. Do not edit code.

## Objective

Find senior-level issues where the code is harder to understand and maintain than it needs to be because local intent is obscured by confusing naming, tangled control flow, hidden invariants, or unclear contract boundaries.

This repo builds wave-ready local assets from FlyWire metadata and neuron meshes, then uses those assets for local simulation, validation, analysis, and offline review packages. Many modules are explicit contract and metadata shapers, so prioritize places where future maintainers will struggle to tell which fields, paths, statuses, or bundle records are authoritative.

## Focus

- Start with `src/flywire_wave/`, not `scripts/`.
- Areas where local clarity matters most: config and manifest resolution, path normalization, and contract modules such as `config.py`, `manifests.py`, `*_contract.py`, `validation_*`, and `*_readiness.py`.
- Areas where local clarity matters most: the canonical preprocessing flow `registry -> select -> meshes -> assets`, especially `registry.py`, `selection.py`, `mesh_pipeline.py`, `synapse_mapping.py`, `coupling_assembly.py`, and geometry-related modules.
- Areas where local clarity matters most: operator assembly and runtime execution, especially `surface_operators.py`, `surface_wave_solver.py`, `simulation_planning.py`, `simulator_runtime.py`, `simulator_execution.py`, and `hybrid_morphology_runtime.py`.
- Areas where local clarity matters most: orchestration and packaged review surfaces such as `experiment_suite_*`, `dashboard_*`, `showcase_*`, `whole_brain_context_*`, and `review_prompt_tickets.py`.
- Look for names that blur repo domain meaning around root IDs, subset presets, materialization and snapshot versions, geometry bundles, fine and coarse operators, manifest arms, suite cells, stage IDs, bundle IDs, artifact IDs, and contract versions.
- Look for hidden invariants around deterministic local outputs, selected-root alias refreshes, processed artifact paths, status transitions, planner-to-executor handoffs, and packager metadata.
- Look for repeated dict or JSON payload construction where it is hard to tell which values are source of truth versus copied bookkeeping.
- Look for dense branching where maintainers must mentally simulate blocking rules, failure modes, dependency ordering, or asset readiness to understand the code.
- Use `tests/` to understand intended contract surfaces, but only raise tickets on tests when they expose confusing production interfaces or brittle semantics.

## Exclude

- Pure formatting or stylistic preferences.
- Large-scale refactors whose main payoff is file splitting or architecture churn.
- Documentation-only issues.
- Problems better categorized as testing coverage, performance, data quality, or operability.
- Generated or snapshot-oriented directories: `data/raw/codex/`, `data/interim/`, and `data/processed/`.
- The upstream submodule `flywire_codex/`.
- Thin CLI wrappers in `scripts/` unless the wrapper duplicates logic, hides important defaults, or obscures the contract with `src/flywire_wave/`.
- `docs/`, `config/`, `manifests/`, and `schemas/` when the issue is only wording or spec prose rather than confusing code-side behavior or invariant enforcement.

## Review Process

1. Read the most central library logic first.
2. Prioritize issues that would materially slow changes to the canonical pipeline, deterministic simulator outputs, validation bundles, experiment suites, dashboard packaging, showcase packaging, or whole-brain context packaging.
3. Require concrete evidence that the current code obscures intent, such as unclear source-of-truth fields, implicit pipeline ordering, duplicated contract keys, buried status semantics, or path and bundle invariants that only become obvious after cross-reading multiple files.
4. Favor a small set of high-value tickets over broad cleanup lists.
5. Treat hard-coded datastack assumptions, materialization values, version strings, artifact IDs, and status enums as maintainability issues only when their meaning or authority is buried, duplicated, or easy to misuse.

## Validation Context

- Use the repo `Makefile` commands as the canonical verification language in tickets.
- Default verification commands are `make test`, `make validate-manifest`, and `make smoke`.
- Use `make review-tickets REVIEW_TICKETS_ARGS='--dry-run'` only for issues in the review-ticket specialization or runner flow.
- Prefer local, offline verification paths when possible.
- Avoid suggesting token or network dependent checks such as `make verify` or `make meshes` unless the maintainability issue is specifically about those paths.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with a repo-specific prefix, for example `FWW-MAINT-001`.
- Cite files and line references.
- Name the `Area` as a real repo subsystem, for example `manifest validation`, `registry build`, `subset selection`, `mesh asset build`, `surface operator assembly`, `surface-wave runtime`, `experiment suite orchestration`, `dashboard packaging`, or `review prompt workflow`.
- Explain why the current code is hard to reason about in repo terms. Spell out the maintainer risk, such as not knowing which artifact path is canonical, which bundle field is authoritative, which relation step mutates the root set, or which work-item statuses can coexist.
- Recommend a scoped maintainability improvement with a clear payoff.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Readability And Maintainability Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: readability_and_maintainability review
- Area: <repo subsystem>

### Problem
<what makes the code hard to understand or maintain in this repository's domain>

### Evidence
<specific files, lines, and why the maintainability cost is real>

### Requested Change
<the clarity or maintainability improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<repo-appropriate checks such as `make test`, `make validate-manifest`, `make smoke`, or a narrower local command or test when directly relevant>
