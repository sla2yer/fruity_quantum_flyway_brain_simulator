# FlyWire Wave Pipeline

This repo builds wave-ready local assets from FlyWire metadata and neuron
meshes, then uses those assets for local simulation, analysis, and review
surfaces. It targets the public FAFB datastack
`flywire_fafb_public` at materialization `783`.

It supports two main workflows:

- a real FlyWire-backed preprocessing pipeline for your own selected subset
- local, file-backed review tools built on top of generated assets and result
  bundles

If you want the fastest no-auth walkthrough, start with
[`RUN_ME_FIRST.md`](RUN_ME_FIRST.md). If you are onboarding with an agent, see
[`AGENTS.md`](AGENTS.md).

## Quick Start

```bash
git submodule update --init --recursive
make bootstrap
make test
make validate-manifest
```

The `Makefile` automatically uses `.venv/bin/python` when that virtualenv
exists. Run `make help` to see the full command list.

## FlyWire Setup

1. Copy the example env file and save your API token:

```bash
cp .env.example .env
./.venv/bin/python scripts/setup_flywire_token.py --write-env
```

2. Copy the example runtime config:

```bash
cp config/visual_subset.example.yaml config/local.yaml
```

3. Put your FlyWire Codex CSV exports in `data/raw/codex/`.

Required input:

- `classification.csv`

Optional inputs that the registry builder will auto-detect when present:

- `cell_types.csv`
- `connections_filtered.csv`
- `neurotransmitter_type_predictions.csv`
- `synapses.csv`
- visual annotation and column CSVs

4. Verify access:

```bash
make verify CONFIG=config/local.yaml
```

`make verify` and `make meshes` require `FLYWIRE_TOKEN` plus network access.

## Build The Pipeline

Run the main preprocessing flow with:

```bash
make registry CONFIG=config/local.yaml
make select CONFIG=config/local.yaml
make meshes CONFIG=config/local.yaml
make assets CONFIG=config/local.yaml
```

What each step does:

- `registry`: normalizes Codex exports into canonical neuron, connectivity, and
  optional local synapse registries
- `select`: writes a named subset under `data/interim/subsets/<preset>/` and
  refreshes `selected_root_ids` for downstream steps
- `meshes`: fetches raw meshes and optional skeletons for the active subset
- `assets`: builds simplified meshes, surface graphs, patch graphs, operators,
  transfer operators, and manifest metadata

`make all CONFIG=config/local.yaml` runs `verify -> registry -> select -> meshes -> assets`.

## Run The Code

After assets exist, the main execution path is:

```bash
make simulate CONFIG=config/local.yaml
make compare-analysis CONFIG=config/local.yaml
```

`make simulate` resolves the configured manifest into runnable arms, executes
the supported local model modes, and writes deterministic simulator result
bundles under the configured processed-results directory.

`make compare-analysis` packages experiment-level comparison outputs from those
simulator result bundles.

For the rest of the execution surface, use `make help`. The repo also includes
targets for validation, suite runs, aggregation, reporting, dashboard
packaging, showcase packaging, and whole-brain context packaging.

Most wrapper targets accept extra CLI flags through `*_ARGS`, for example
`SIMULATE_ARGS`, `COUPLING_INSPECT_ARGS`, `DASHBOARD_ARGS`, `SHOWCASE_ARGS`,
and `WHOLE_BRAIN_CONTEXT_ARGS`.

## Agentic Review Tickets

The repo now includes reusable review prompt sets under
`agent_tickets/review_prompt_sets/`. Each set contains:

- a generic review prompt for one code-quality lens
- a specializer prompt that rewrites that generic prompt for this repo

Run the full workflow with:

```bash
make review-tickets
```

The runner does two phases, both in parallel:

1. Specialize each generic review prompt for this repository.
2. Run each specialized prompt to generate a senior-dev ticket pack.

By default artifacts land under `agent_tickets/review_runs/<timestamp>/`,
including:

- `specialization/<prompt-set>/specialized_prompt.md`
- `reviews/<prompt-set>/tickets.md`
- `combined_tickets.md`
- `summary.json`

Useful options:

- `make review-tickets REVIEW_TICKETS_ARGS='--dry-run'`
- `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set efficiency_and_modularity'`
- `make review-tickets REVIEW_TICKETS_ARGS='--specializer-model <model> --review-model <model>'`

To implement the resulting tickets as a refresh-aware backlog, run:

```bash
make review-backlog REVIEW_BACKLOG_ARGS='--review-run-dir agent_tickets/review_runs/<timestamp>'
```

That runner executes one ticket, then re-runs the saved specialized review
prompts to refresh the remaining backlog before starting the next ticket. The
refreshed ticket packs land under `agent_tickets/review_ticket_runs/<timestamp>/`.

If you want a static one-shot execution of the generated markdown without
backlog refresh, you can still use:

```bash
python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/review_runs/<timestamp>/combined_tickets.md
```

## User Interfaces

All review surfaces are local and file-backed. Once the required artifacts
exist, you can open the generated HTML directly from disk; no backend service
is required.

- Geometry preview: `make preview CONFIG=config/local.yaml`
  Needs `make assets`. Generates a static HTML/JSON preview of raw meshes,
  simplified meshes, skeletons, surface graphs, and patch graphs.
- Coupling inspection: `make coupling-inspect CONFIG=config/local.yaml COUPLING_INSPECT_ARGS='--edge <pre>:<post>'`
  Needs local coupling artifacts. Generates a static edge-inspection report for
  synapse mapping and coupling bundles.
- Operator QA: `make operator-qa CONFIG=config/local.yaml`
  Needs `make assets`. Generates a static QA report for fine/coarse operators
  and transfer quality.
- Simulator result viewer: `./.venv/bin/python scripts/17_visualize_simulator_results.py --bundle-metadata <simulator_result_bundle.json> --bundle-metadata <simulator_result_bundle.json> --open-browser`
  Needs `make simulate`. Builds an offline HTML viewer from one or more result
  bundles.
- Experiment analysis viewer: `./.venv/bin/python scripts/21_visualize_experiment_analysis.py --analysis-bundle <experiment_analysis_bundle.json> --open-browser`
  Needs `make compare-analysis`. Builds an offline HTML report from one
  packaged analysis bundle.
- Dashboard shell: `make dashboard-open CONFIG=config/local.yaml`
  Needs simulator bundles, an analysis bundle, and a packaged validation
  bundle. Builds and opens the packaged local dashboard app.
- Showcase player:

```bash
make showcase-session CONFIG=config/local.yaml SHOWCASE_ARGS='--dashboard-session-metadata <dashboard_session.json> --suite-package-metadata <experiment_suite_package.json>'
make showcase-player SHOWCASE_SESSION_METADATA=<showcase_session.json> SHOWCASE_PLAYER_COMMAND=status
```

  Needs a packaged dashboard session plus suite artifacts. Packages a scripted
  presentation bundle and drives it through the CLI player commands.
- Whole-brain context package:

```bash
make whole-brain-context CONFIG=config/local.yaml WHOLE_BRAIN_CONTEXT_ARGS='--dashboard-session-metadata <dashboard_session.json>'
```

  Needs subset artifacts and the local synapse registry, and can also consume
  dashboard or showcase packages. Packages a larger-brain context bundle for
  review.

## Repo Map

- `src/flywire_wave/`: library code for config loading, registry building,
  subset selection, mesh processing, simulation, analysis, and packaging
- `scripts/`: thin CLI wrappers around the library
- `tests/`: local unit tests
- `config/`: example configs and shipped verification configs
- `manifests/`: experiment manifests
- `schemas/`: manifest schemas
- `docs/`: design notes and workflow references
- `data/raw/codex/`: manually downloaded Codex CSV inputs
- `data/interim/`, `data/processed/`: generated outputs, ignored by git
- `flywire_codex/`: upstream Codex submodule; avoid editing unless a task
  explicitly calls for it

## Useful Docs

- [`docs/pipeline_notes.md`](docs/pipeline_notes.md): artifact contracts and
  output layout
- [`docs/geometry_preview.md`](docs/geometry_preview.md): geometry preview
  workflow
- [`docs/coupling_inspection.md`](docs/coupling_inspection.md): coupling review
  workflow
- [`docs/operator_qa.md`](docs/operator_qa.md): operator QA workflow
- [`docs/retinal_bundle_workflow.md`](docs/retinal_bundle_workflow.md): retinal
  bundle workflow
- [`docs/ui_dashboard_design.md`](docs/ui_dashboard_design.md): dashboard
  package design
- [`docs/showcase_mode_design.md`](docs/showcase_mode_design.md): showcase
  package design
- [`docs/whole_brain_context_design.md`](docs/whole_brain_context_design.md):
  whole-brain context package design

## Notes

- Paths under `config.paths` resolve from the repo root.
- `make smoke` runs tests plus manifest validation.
- This repo keeps whole-brain metadata as context, but only builds local assets
  for selected subsets.
- The repo is designed for offline inspection once artifacts have been built;
  it is not a live FlyWire mirror or a hosted web service.
