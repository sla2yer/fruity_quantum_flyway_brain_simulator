Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Prompt set slug: efficiency_and_modularity

Run the repo-specific review prompt below against this repository.
Stay in review mode and return only the final ticket markdown requested by the prompt.

# Efficiency And Modularity Review Prompt

You are performing a focused code review of the FlyWire Wave repository. Stay in review mode. Do not edit code, open pull requests, or propose implementation patches.

## Objective

Find senior-level issues where runtime efficiency, data-movement cost, or weak modular structure is materially hurting this repo’s real execution surfaces: Codex registry ingestion, subset selection, mesh/operator asset building, synapse/coupling materialization, manifest-driven local simulation, experiment-suite orchestration, or review-ticket generation.

## Focus

Prioritize these areas first:

- Registry and subset build path: `src/flywire_wave/config.py`, `src/flywire_wave/registry.py`, `src/flywire_wave/selection.py`
- Geometry and operator assembly hot paths: `src/flywire_wave/mesh_pipeline.py`, `src/flywire_wave/surface_operators.py`, related geometry contract and QA modules
- Synapse and coupling materialization: `src/flywire_wave/synapse_mapping.py`, `src/flywire_wave/coupling_assembly.py`
- Manifest/runtime orchestration: `src/flywire_wave/manifests.py`, `src/flywire_wave/simulation_planning.py`, `src/flywire_wave/simulator_execution.py`, `src/flywire_wave/experiment_suite_execution.py`
- Review-ticket orchestration seams: `src/flywire_wave/review_prompt_tickets.py`, `src/flywire_wave/agent_tickets.py`

Use `scripts/` mainly to trace CLI-to-library boundaries. They are thin wrappers and usually should not be the primary ticket source unless they duplicate logic that belongs in `src/flywire_wave/`.

Look specifically for:

- Repeated `pandas`/CSV full scans, redundant parsing, or per-preset/per-root recomputation in registry, selection, and synapse materialization
- Per-root mesh/operator loops that re-read artifacts, copy arrays unnecessarily, densify sparse structures, or repeat geodesic / patch computations without clear need
- Coupling, simulation, or suite code that reloads manifests, bundle metadata, or local assets instead of reusing indexed state
- Modules that mix planning, execution, persistence, and report packaging so tightly that batching, caching, or isolated testing are hard
- Duplicated path resolution, manifest normalization, contract handling, or subprocess/orchestration logic across pipeline and review-ticket runners
- APIs around `config.paths`, manifest resolution, asset discovery, and bundle lookup that make the efficient path hard to use correctly

Use `docs/pipeline_notes.md` as the contract map for subset, geometry, and coupling handoffs when judging whether module boundaries are coherent.

## Exclude

- Pure micro-optimizations with no plausible payoff on local registry/asset/simulation workloads
- Style-only feedback
- Wrapper-only cleanup when the deeper library modularity is fine
- Tickets primarily about testing, naming, or documentation
- Abstractions whose main problem is overengineering rather than efficiency or modularity

## Ignore

Usually ignore:

- `data/interim/`, `data/processed/`, `agent_tickets/review_runs/`, `agent_tickets/runs/`, `.venv/`, `.pytest_cache/`, `src/flywire_wave.egg-info/`, and ad hoc `tmp_m15_*` probe directories
- `flywire_codex/` unless the boundary with the vendored submodule is itself the issue
- `data/raw/codex/` as source snapshots rather than code under review

## Review Process

1. Start with the preprocessing pipeline order behind `make registry`, `make select`, `make meshes`, and `make assets`.
2. Then inspect coupling materialization, manifest-driven simulation, and experiment-suite execution.
3. Use dashboard/showcase/whole-brain-context or other packaging surfaces only when they expose duplicated orchestration or repeated bundle-loading costs.
4. Trace the implementation into `src/flywire_wave/` far enough to confirm the issue is real in code, not just a possible improvement.
5. Prefer fewer, higher-signal tickets tied to hot-path library code or orchestration seams.
6. Only emit a ticket when efficiency or modularity is the primary reason the change should happen.
7. If a CLI script and library module are both involved, ticket the library module unless the inefficiency is truly isolated to the wrapper.

## Validation

Prefer the repo `Makefile`; it auto-selects `.venv/bin/python` when present.

Use:

- `make smoke` for the baseline local check
- `make test` and `make validate-manifest` when the issue touches manifest or config contracts
- Targeted unit tests under `tests/` for the subsystem you cite, especially registry/selection, mesh pipeline and surface operators, synapse mapping and coupling assembly, simulation planning/execution, experiment-suite execution, and review-prompt ticket runners
- `make registry`, `make select`, `make assets`, `make simulate`, or `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set efficiency_and_modularity --dry-run'` only when local config and inputs exist

Do not rely on `make verify` or `make meshes` unless you explicitly note they require `.env` with `FLYWIRE_TOKEN` and network access.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with the prefix `EFFMOD-FW-`, for example `EFFMOD-FW-001`.
- Write for senior engineers who need enough context to act without rediscovering the problem from scratch.
- Cite concrete evidence with file paths and 1-based line references when possible, for example `src/flywire_wave/mesh_pipeline.py:120`.
- Explain why the current shape is costly in this repo’s actual workflows, not just that it could be cleaner.
- Recommend changes that simplify or speed up the system without adding needless complexity.
- If there are no credible issues, return a short markdown document that says no tickets are recommended.

## Output Format

Return only markdown. Do not wrap the answer in code fences.

Use this structure:

# Efficiency And Modularity Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: efficiency_and_modularity review
- Area: <registry | selection | mesh pipeline | surface operators | coupling | simulation planning | simulator execution | experiment suites | review prompt orchestration>

### Problem
<what is wrong and why it matters>

### Evidence
<specific files, lines, and observations>

### Requested Change
<the change a senior dev should make>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, smoke checks, or command-level validation>

Return only the final ticket markdown.
