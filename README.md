# FlyWire Female Brain -> Wave Asset Pipeline

This repo preprocesses FlyWire metadata and neuron meshes into wave-ready assets
for a later simulator. It targets the adult female Drosophila FAFB public
datastack (`flywire_fafb_public`, materialization `783`) and focuses on:

- keeping the whole brain as the structural source of truth,
- selecting only a small active circuit to simulate,
- fetching meshes and optional skeletons only for that selected subset,
- building multiresolution geometry and operator bundles offline.

This is not the final simulator and it is not a whole-brain local mirror.

If you are onboarding quickly or using a coding agent, start with
[`AGENTS.md`](AGENTS.md).

## What this repo does

The intended workflow is:

1. download stable FlyWire Codex metadata snapshots,
2. normalize them into canonical neuron and connectivity registries,
3. derive a reproducible named subset,
4. fetch only the selected neurons as raw meshes and optional skeletons,
5. simplify those meshes and build geometry/operator bundles for later wave
   simulation,
6. inspect the result with local HTML/Markdown preview and QA reports.

That gives you the whole-brain metadata context without trying to mirror the
full EM segmentation locally.

## Safe validation loop

These checks are local and do not require FlyWire network access:

```bash
make test
make validate-manifest
make smoke
```

The `Makefile` automatically uses `.venv/bin/python` when that virtualenv
exists.

## Milestone 10 local verification

The shipped Milestone 10 integration pass is:

```bash
make milestone10-readiness
```

That runs `scripts/16_milestone10_readiness.py` with
`config/milestone_10_verification.yaml`, exercises the representative
`surface_wave` execution and the shipped verification-grade inspection sweep on
local fixture assets, and writes `milestone_10_readiness.md` plus
`milestone_10_readiness.json` under
`data/processed/milestone_10_verification/simulator_results/readiness/milestone_10/`.

That local fixture is a readiness and stability probe, not a biological claim.
The readiness gate uses `config/surface_wave_sweep.verification.yaml` as the
non-runaway local reference; the broader exploratory sweep remains available at
`config/surface_wave_sweep.example.yaml`.
To rerun the shipped verification-grade inspection directly after readiness,
point `scripts/15_surface_wave_inspection.py` at
`data/processed/milestone_10_verification/simulator_results/readiness/milestone_10/generated_fixture/simulation_fixture_config.yaml`.

## Milestone 11 local verification

The shipped Milestone 11 mixed-fidelity integration pass is:

```bash
make milestone11-readiness
```

That runs `scripts/19_milestone11_readiness.py` with
`config/milestone_11_verification.yaml`, materializes a deterministic
three-root mixed-fidelity fixture, executes the mixed `surface_wave` arm
through the public simulator command, verifies the offline simulator viewer can
read the resulting mixed bundle, runs the surrogate-preservation inspection
workflow, and writes `milestone_11_readiness.md` plus
`milestone_11_readiness.json` under
`data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/`.

The generated visualization at
`data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/visualization/index.html`
is fully static, so no local server is required. Open that file directly in
your browser, or run `make milestone11-readiness M11_READINESS_ARGS=--open-visualization`
to launch it after the readiness pass. If you do serve it with
`python -m http.server`, a browser with HTTPS-first behavior may log a harmless
`400` before it falls back to plain HTTP.

To rerun the shipped mixed-fidelity verification flow directly after readiness,
use the generated fixture config and manifest from that report directory:

```bash
python scripts/run_simulation.py --config data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/generated_fixture/simulation_fixture_config.yaml --manifest data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/generated_fixture/fixture_manifest.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --model-mode surface_wave --arm-id surface_wave_intact
python scripts/18_mixed_fidelity_inspection.py --config data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/generated_fixture/simulation_fixture_config.yaml --manifest data/processed/milestone_11_verification/simulator_results/readiness/milestone_11/generated_fixture/fixture_manifest.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --arm-id surface_wave_intact
```

## Milestone 12 local verification

The shipped Milestone 12 task-layer integration pass is:

```bash
make milestone12-readiness
```

That runs `scripts/22_milestone12_readiness.py` with
`config/milestone_12_verification.yaml`, materializes a deterministic local
Milestone 12 analysis fixture, executes `scripts/20_experiment_comparison_analysis.py`
and `scripts/21_visualize_experiment_analysis.py` on the shipped representative
manifest path, audits analysis-plan resolution plus packaged-export discovery,
and writes `milestone_12_readiness.md` plus `milestone_12_readiness.json` under
`data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/`.

The generated visualization at
`data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/visualization/index.html`
is fully static, so no local server is required. Open that file directly in
your browser, or run `make milestone12-readiness M12_READINESS_ARGS=--open-visualization`
to launch it after the readiness pass.

To rerun the shipped end-to-end Milestone 12 workflow directly after readiness,
use the generated fixture config and manifest from that report directory. The
second command takes the `analysis_bundle_metadata_path` recorded in
`milestone_12_readiness.json`:

```bash
python scripts/20_experiment_comparison_analysis.py --config data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/generated_fixture/simulation_fixture_config.yaml --manifest data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/generated_fixture/fixture_manifest.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --output data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/generated_fixture/analysis_summary.json
python scripts/21_visualize_experiment_analysis.py --analysis-bundle <analysis_bundle_metadata_path> --output-dir data/processed/milestone_12_verification/simulator_results/readiness/milestone_12/visualization
```

## Milestone 13 local verification

The shipped Milestone 13 validation-ladder integration pass is:

```bash
make milestone13-readiness
```

That runs `scripts/28_milestone13_readiness.py` with
`config/milestone_13_verification.yaml`, materializes a deterministic
representative-manifest plan fixture, executes the packaged smoke ladder
through `scripts/27_validation_ladder.py`, audits validation-plan resolution,
packaged-export discovery, regression command discovery, and documentation, and
writes `milestone_13_readiness.md` plus `milestone_13_readiness.json` under
`data/processed/milestone_13_verification/simulator_results/readiness/milestone_13/`.

To rerun the shipped packaged ladder smoke directly after readiness, use either:

```bash
make validation-ladder-smoke
python scripts/27_validation_ladder.py smoke --processed-simulator-results-dir data/processed/milestone_13_verification/simulator_results/readiness/milestone_13/smoke_fixture/simulator_results --baseline tests/fixtures/validation_ladder_smoke_baseline.json --enforce-baseline
```

## Pipeline at a glance

The main pipeline order is:

1. `scripts/build_registry.py`
2. `scripts/01_select_subset.py`
3. `scripts/02_fetch_meshes.py`
4. `scripts/03_build_wave_assets.py`

Optional offline inspection steps:

5. `scripts/05_preview_geometry.py`
6. `scripts/06_operator_qa.py`
7. `scripts/07_milestone6_readiness.py`
8. `scripts/08_coupling_inspection.py`
9. `scripts/09_milestone7_readiness.py`
10. `scripts/10_stimulus_bundle.py`
11. `scripts/11_milestone8a_readiness.py`
12. `scripts/12_retinal_bundle.py`
13. `scripts/13_milestone8b_readiness.py`
14. `scripts/14_milestone9_readiness.py`
15. `scripts/15_surface_wave_inspection.py`
16. `scripts/16_milestone10_readiness.py`
17. `scripts/17_visualize_simulator_results.py`
18. `scripts/18_mixed_fidelity_inspection.py`
19. `scripts/19_milestone11_readiness.py`
20. `scripts/20_experiment_comparison_analysis.py`
21. `scripts/21_visualize_experiment_analysis.py`
22. `scripts/22_milestone12_readiness.py`
23. `scripts/23_numerical_validation.py`
24. `scripts/24_morphology_validation.py`
25. `scripts/25_circuit_validation.py`
26. `scripts/26_task_validation.py`
27. `scripts/27_validation_ladder.py`
28. `scripts/28_milestone13_readiness.py`

## Source-of-truth inputs

### 1) Bulk tables / annotations

Use the FlyWire Codex download portal for the FAFB dataset:

- `https://codex.flywire.ai/api/download?dataset=fafb`

Recommended files to place in `data/raw/codex/`:

- `classification.csv`
- `cell_types.csv` or `consolidated_cell_types.csv`
- `connections_filtered.csv` or `connections.csv`
- `neurotransmitter_type_predictions.csv` or `neurons.csv`
- optional visual annotations such as `visual_neuron_annotations.csv` and
  `visual_neuron_columns.csv`

Notes:

- export names can drift a little across FlyWire downstream tooling, so trust
  the portal first;
- the registry builder tolerates a minimal `classification.csv`-only setup, but
  richer exports produce a better canonical registry.

### 2) Public programmatic access

Use the public CAVE datastack:

- datastack: `flywire_fafb_public`
- materialization target in this repo: `783`

### 3) Meshes and skeletons

Meshes are not bulk-downloaded from Codex. This repo fetches them per neuron
through the FlyWire/CAVE stack. Skeletons are optional and also fetched
per-neuron when configured.

## Repo layout

- `src/flywire_wave/`: core library code for config loading, registry building,
  subset selection, geometry/operator contracts, mesh processing, preview
  generation, and operator QA
- `scripts/`: thin CLI entrypoints for the pipeline and offline review tools
- `tests/`: local unit tests that do not require FlyWire network access
- `config/`: example runtime config plus the tracked Milestone 1 and Milestone 6
  through Milestone 12 verification configs and inputs, including the
  verification-grade and exploratory surface-wave sweep specs
- `manifests/`: example experiment manifests
- `schemas/`: manifest schema files
- `docs/milestones.md`: consolidated roadmap and milestone planning
- `docs/pipeline_notes.md`: concise pipeline and artifact contract notes
- `docs/geometry_descriptor_qa.md`: descriptor and geometry-QA thresholds
- `docs/operator_bundle_design.md`: authoritative Milestone 6 discretization and
  operator contract note
- `docs/coupling_bundle_design.md`: authoritative Milestone 7 coupling contract
  and topology note
- `docs/coupling_inspection.md`: reviewer-oriented offline coupling inspection
  workflow
- `docs/operator_qa.md`: reviewer-oriented offline operator QA workflow
- `docs/retinal_bundle_design.md`: authoritative Milestone 8B retinal contract
  and sampling note
- `docs/retinal_bundle_workflow.md`: retinal record/replay/inspect workflow plus
  Milestone 8B readiness command
- `docs/retinal_inspection.md`: reviewer-oriented offline retinal inspection and
  readiness workflow
- `docs/surface_wave_model_design.md`: authoritative Milestone 10 wave-model
  contract and stability note
- `docs/surface_wave_inspection.md`: local surface-wave inspection and
  readiness workflow
- `docs/readout_analysis_design.md`: authoritative Milestone 12 task-layer
  metric and fairness contract note
- `docs/experiment_analysis_bundle_design.md`: authoritative Milestone 12
  experiment-analysis packaging and readiness workflow note
- `data/raw/codex/`: manually downloaded Codex CSV snapshots
- `data/interim/`, `data/processed/`: generated outputs, ignored by git
- `flywire_codex/`: upstream Codex submodule; avoid editing unless a task
  explicitly calls for it

## FlyWire authentication

This repo uses two separate auth contexts:

- FlyWire Codex (`codex.flywire.ai`) for browser/UI access and bulk CSV/static
  downloads
- CAVE / FlyWire API for local programmatic access through `caveclient`,
  `fafbseg`, and the repo scripts that read `FLYWIRE_TOKEN` from `.env`

Being signed into FlyWire Codex in the browser does not automatically configure
local Python access. The `FLYWIRE_TOKEN` value in `.env` should be your
FlyWire/CAVE API token.

Recommended setup flow:

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Launch the helper script:

```bash
python scripts/setup_flywire_token.py
```

If you specifically need to mint a new token, run:

```bash
python scripts/setup_flywire_token.py --new-token
```

Creating a new token may invalidate the previous one.

3. Copy the token from the browser page.
4. Paste it into `.env` as `FLYWIRE_TOKEN=...`, or rerun the helper with
   `--write-env` to update `.env` interactively.
5. Optional: after installing dependencies, save the same token to local CAVE
   secret storage if you want machine-wide auth for `caveclient` / `fafbseg`.
6. Rerun access verification:

```bash
python scripts/00_verify_access.py --config config/local.yaml
```

If FlyWire's materialization service is temporarily down, the verifier reports
that as an upstream outage while still checking whether your token works against
the global info service. Add `--require-materialize` if you want that case to
return a non-zero exit code.

## Quick start

### 1) Create the environment

```bash
git submodule update --init --recursive
make bootstrap
```

That initializes the pinned `flywire_codex/` submodule, creates `.venv/` if
needed, upgrades `pip`, and installs the repo in editable mode.

Manual equivalent:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### 2) Set up FlyWire authentication

```bash
cp .env.example .env
python scripts/setup_flywire_token.py
```

Then write `FLYWIRE_TOKEN=...` into `.env`, or rerun the helper with
`--write-env`.

### 3) Download the FlyWire Codex metadata exports

Place the files you downloaded from FlyWire Codex into:

```text
data/raw/codex/
```

Recommended registry inputs:

```text
data/raw/codex/classification.csv
data/raw/codex/cell_types.csv
data/raw/codex/connections_filtered.csv
data/raw/codex/neurotransmitter_type_predictions.csv
```

### 4) Copy the example config

```bash
cp config/visual_subset.example.yaml config/local.yaml
```

All entries under `config.paths` resolve from the repository root, not from the
caller's current working directory. You can run the pipeline from another
directory as long as `--config` points to the right file, for example:

```bash
python /abs/path/to/flywire_wave_repo/scripts/build_registry.py \
  --config /abs/path/to/flywire_wave_repo/config/local.yaml
```

### 5) Verify access

```bash
python scripts/00_verify_access.py --config config/local.yaml
```

### 6) Build the canonical registry

This normalizes the local Codex exports into one neuron registry, one
connectivity registry, and a provenance JSON with pinned snapshot and input-file
metadata. It also refreshes the canonical local synapse-registry path under
`data/processed/coupling/`; when `paths.synapse_source_csv` is configured that
artifact contains normalized per-synapse rows, and otherwise it stays as an
empty audited placeholder.

```bash
python scripts/build_registry.py --config config/local.yaml
```

This writes:

```text
data/interim/registry/neuron_registry.csv
data/interim/registry/connectivity_registry.csv
data/interim/registry/registry_provenance.json
data/processed/coupling/synapse_registry.csv
data/processed/coupling/synapse_registry_provenance.json
```

### 7) Select a subset to mesh

The selector is preset-driven. The sample config defines three named presets:

- `motion_minimal`
- `motion_medium`
- `motion_dense`

Each run writes a root-id list, selected-neuron CSV, stats JSON, manifest JSON,
and a lightweight Markdown/Mermaid preview under
`data/interim/subsets/<preset>/`. The active preset also refreshes
`paths.selected_root_ids` so downstream steps can switch inputs by config alone.
When a synapse source snapshot is configured, selection also refreshes the
canonical `data/processed/coupling/synapse_registry.csv` so it stays scoped to
the active root set.

```bash
python scripts/01_select_subset.py --config config/local.yaml
```

Select a specific preset:

```bash
python scripts/01_select_subset.py --config config/local.yaml --preset motion_dense
```

Generate every preset declared in the config:

```bash
python scripts/01_select_subset.py --config config/local.yaml --all-presets
```

### 8) Fetch raw meshes and optional skeletons

```bash
python scripts/02_fetch_meshes.py --config config/local.yaml
```

This downloads per-neuron assets into:

```text
data/interim/meshes_raw/
data/interim/skeletons_raw/
```

### 9) Build processed geometry and operator bundles

```bash
python scripts/03_build_wave_assets.py --config config/local.yaml
```

The processed manifest records:

- `_asset_contract_version: geometry_bundle.v1`
- `_operator_contract_version: operator_bundle.v2`

Per selected root ID, the build emits:

- `data/processed/meshes/<root_id>.ply`
- `data/processed/graphs/<root_id>_graph.npz`
- `data/processed/graphs/<root_id>_fine_operator.npz`
- `data/processed/graphs/<root_id>_patch_graph.npz`
- `data/processed/graphs/<root_id>_coarse_operator.npz`
- `data/processed/graphs/<root_id>_transfer_operators.npz`
- `data/processed/graphs/<root_id>_descriptors.json`
- `data/processed/graphs/<root_id>_qa.json`
- `data/processed/graphs/<root_id>_operator_metadata.json`
- `data/processed/graphs/<root_id>_meta.json` as a legacy compatibility shim
- `data/processed/asset_manifest.json`

By default, the fine operator bundle uses the Milestone 6 scientific baseline:

- discretization family: `triangle_mesh_cotangent_fem`
- mass treatment: `lumped_mass`
- normalization: `mass_normalized`
- boundary mode: `closed_surface_zero_flux`
- anisotropy model: `isotropic`

When the metric-aware assembly cannot be realized safely, the allowed fallback
family is the structural `surface_graph_uniform_laplacian`, and the manifest
records that explicitly.

### 10) Generate an offline geometry preview report

```bash
python scripts/05_preview_geometry.py --config config/local.yaml --root-id 720575940000000001
```

If you omit `--root-id`, the preview script reads `paths.selected_root_ids`.
Reports write to a deterministic directory under `config.paths.geometry_preview_dir`
(default: `data/processed/previews/`).

Each preview directory contains a static `index.html`, `summary.json`, and the
exact `root_ids.txt` used for that report. See
[`docs/geometry_preview.md`](docs/geometry_preview.md) for reviewer guidance.

### 11) Generate an offline coupling inspection report

```bash
python scripts/08_coupling_inspection.py --config config/local.yaml --edge 202:101
```

Inspect multiple explicit edges instead:

```bash
python scripts/08_coupling_inspection.py --config config/local.yaml --edge 202:101 --edge 101:303
```

This workflow reads only local Milestone 7 artifacts and writes a deterministic
report under `config.paths.coupling_inspection_dir/edges-<sorted-edge-slug>/`
(default: `data/processed/coupling_inspection/`). It does not require FlyWire
network access.

Each report includes:

- `index.html`
- `report.md`
- `summary.json`
- `edges.txt`
- per-edge detail JSON
- presynaptic readout and postsynaptic landing SVG panels

See [`docs/coupling_inspection.md`](docs/coupling_inspection.md) for the
checks, reviewer checklist, and threshold override semantics.

### 12) Generate an offline operator QA report

```bash
python scripts/06_operator_qa.py --config config/local.yaml --limit 4
```

Inspect explicit root IDs instead:

```bash
python scripts/06_operator_qa.py --config config/local.yaml --root-id 101 --root-id 102
```

This workflow reads only local processed bundles and writes a deterministic
report under `config.paths.operator_qa_dir/root-ids-<sorted-root-ids>/`
(default: `data/processed/operator_qa/`). It does not require FlyWire network
access.

Each report includes:

- `index.html`
- `report.md`
- `summary.json`
- per-root detail JSON
- SVG panels for pulse initialization, boundary-mask inspection, patch
  decomposition, smoke-evolved fine/coarse fields, and reconstruction error

See [`docs/operator_qa.md`](docs/operator_qa.md) for the checks, thresholds,
and operator readiness gate semantics.

### 13) Run the Milestone 6 readiness pass

```bash
make milestone6-readiness
```

This uses [`config/milestone_6_verification.yaml`](config/milestone_6_verification.yaml)
and writes isolated outputs under `data/processed/milestone_6_verification/`.
It runs a focused fixture suite, rebuilds the local verification bundle, runs
operator QA, and publishes:

- `milestone_6_readiness.md`
- `milestone_6_readiness.json`

in the same deterministic operator-QA report directory.

### 14) Run the Milestone 7 readiness pass

```bash
make milestone7-readiness
```

This uses [`config/milestone_7_verification.yaml`](config/milestone_7_verification.yaml)
plus [`config/milestone_7_verification_edges.txt`](config/milestone_7_verification_edges.txt)
and writes isolated outputs under `data/processed/milestone_7_verification/`.
It runs a focused Milestone 7 fixture suite, rebuilds the scoped registry and
selected subset, rebuilds the local coupling bundle set, runs coupling
inspection, and publishes:

- `milestone_7_readiness.md`
- `milestone_7_readiness.json`

in the same deterministic coupling-inspection report directory.

Equivalent explicit command sequence:

```bash
./.venv/bin/python scripts/build_registry.py --config config/milestone_7_verification.yaml
./.venv/bin/python scripts/01_select_subset.py --config config/milestone_7_verification.yaml
./.venv/bin/python scripts/03_build_wave_assets.py --config config/milestone_7_verification.yaml
./.venv/bin/python scripts/08_coupling_inspection.py --config config/milestone_7_verification.yaml --edges-file config/milestone_7_verification_edges.txt
```

### 15) Run the Milestone 8A readiness pass

```bash
make milestone8a-readiness
```

This uses [`config/milestone_8a_verification.yaml`](config/milestone_8a_verification.yaml)
and writes isolated outputs under `data/processed/milestone_8a_verification/stimuli/`.
It runs a focused Milestone 8A fixture suite, records and replays one
representative bundle per required stimulus family, validates the example
manifest through the canonical registry, audits the static preview outputs, and
publishes:

- `milestone_8a_readiness.md`
- `milestone_8a_readiness.json`

under the deterministic readiness report directory
`data/processed/milestone_8a_verification/stimuli/readiness/milestone_8a/`.

Equivalent explicit command:

```bash
./.venv/bin/python scripts/11_milestone8a_readiness.py --config config/milestone_8a_verification.yaml
```

### 16) Run the Milestone 8B readiness pass

```bash
make milestone8b-readiness
```

This uses [`config/milestone_8b_verification.yaml`](config/milestone_8b_verification.yaml)
and writes isolated outputs under `data/processed/milestone_8b_verification/`.
It runs a focused Milestone 8B fixture suite, exercises the shipped
`scripts/12_retinal_bundle.py` record, replay, and inspect commands through the
stimulus-config, manifest, and scene entrypoints, audits deterministic bundle
discovery and offline inspection sidecars, and publishes:

- `milestone_8b_readiness.md`
- `milestone_8b_readiness.json`

under the deterministic readiness report directory
`data/processed/milestone_8b_verification/retinal/readiness/milestone_8b/`.

Equivalent explicit command:

```bash
./.venv/bin/python scripts/13_milestone8b_readiness.py --config config/milestone_8b_verification.yaml
```

### 17) Run the Milestone 9 readiness pass

```bash
make milestone9-readiness
```

This uses [`config/milestone_9_verification.yaml`](config/milestone_9_verification.yaml)
and writes isolated outputs under `data/processed/milestone_9_verification/`.
It runs a focused Milestone 9 fixture suite, materializes a deterministic local
baseline-simulator fixture, executes the shipped
`scripts/run_simulation.py` baseline workflow twice against the representative
Milestone 1 manifest path, audits planning/runtime/result-bundle/UI contract
compatibility, and publishes:

- `milestone_9_readiness.md`
- `milestone_9_readiness.json`

under the deterministic readiness report directory
`data/processed/milestone_9_verification/simulator_results/readiness/milestone_9/`.

Equivalent explicit command:

```bash
./.venv/bin/python scripts/14_milestone9_readiness.py --config config/milestone_9_verification.yaml
```

## What "wave-ready" means here

For each selected root ID, the current asset builder can:

1. fetch the raw FlyWire mesh and optional skeleton,
2. simplify the mesh to a target face budget,
3. build a surface graph and patch graph,
4. assemble fine and coarse operators plus transfer operators,
5. write geometry descriptors and QA sidecars,
6. record the exact bundle paths and realized assembly mode in a manifest.

When a selected root is missing its raw mesh, the build now keeps processing the
other roots, records a structured blocked result for the missing input, writes
the manifest for the full attempted set, and exits non-zero after the summary
is complete.

That is enough to support later work on:

- morphology-resolved wave solvers,
- patch-local and multiresolution dynamics,
- synapse-to-patch mapping,
- hybrid surface/skeleton/point-neuron representations,
- offline review gates before simulator integration.

## Packaged Milestone 12 analysis

After local simulator bundles exist for one manifest experiment, the Milestone
12 analysis workflow now writes a canonical experiment-analysis bundle under:

- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/`

Run it with:

```bash
make compare-analysis MANIFEST=manifests/examples/milestone_1_demo.yaml CONFIG=config/local.yaml
```

The packaged bundle includes metadata-backed JSON exports for task summaries,
null-test tables, comparison matrices, a UI-facing analysis payload, and a
static offline report. Regenerate the report from packaged artifacts alone
with:

```bash
python scripts/21_visualize_experiment_analysis.py \
  --analysis-bundle data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/experiment_analysis_bundle.json
```

## Contract and QA references

- [`docs/pipeline_notes.md`](docs/pipeline_notes.md): concise artifact-contract
  overview
- [`docs/experiment_analysis_bundle_design.md`](docs/experiment_analysis_bundle_design.md):
  Milestone 12 experiment-analysis packaging contract
- [`docs/coupling_inspection.md`](docs/coupling_inspection.md): Milestone 7
  offline edge-inspection workflow and reviewer checklist
- [`docs/geometry_descriptor_qa.md`](docs/geometry_descriptor_qa.md): geometry
  descriptors and QA thresholds
- [`docs/operator_bundle_design.md`](docs/operator_bundle_design.md): Milestone 6
  discretization choice and operator contract
- [`docs/operator_qa.md`](docs/operator_qa.md): offline operator QA workflow
- [`docs/retinal_bundle_design.md`](docs/retinal_bundle_design.md): Milestone 8B
  retinal contract and sampling choice
- [`docs/retinal_inspection.md`](docs/retinal_inspection.md): offline retinal
  inspection workflow and reviewer checklist

## Milestone 1 design-lock artifacts

Milestone 1 is treated here as a design/specification milestone rather than a
proof-of-effect milestone.

- roadmap and detailed milestone planning:
  [`docs/milestones.md`](docs/milestones.md)
- machine-readable design lock and success criteria:
  [`config/milestone_1_design_lock.yaml`](config/milestone_1_design_lock.yaml)
- example demo manifest:
  [`manifests/examples/milestone_1_demo.yaml`](manifests/examples/milestone_1_demo.yaml)
- manifest schema:
  [`schemas/milestone_1_experiment_manifest.schema.json`](schemas/milestone_1_experiment_manifest.schema.json)

Validate the example manifest with:

```bash
make validate-manifest
```

or:

```bash
python scripts/04_validate_manifest.py \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml
```

## Suggested first run

Do not start by meshing hundreds or thousands of neurons.

A good first pass is:

- 10-25 visual neurons,
- simplify each to about 10k-20k faces,
- use the default subset presets and default operator assembly,
- inspect both the geometry preview and operator QA report before scaling up.

Once that is stable, you can add:

- synapse-to-vertex or synapse-to-patch projection,
- cross-neuron coupling,
- richer anisotropy experiments,
- hybrid representation selection,
- scheduler-driven promotion and demotion.

## Make targets

```bash
make help
make bootstrap
make test
make smoke
make verify CONFIG=config/local.yaml
make registry CONFIG=config/local.yaml
make select CONFIG=config/local.yaml
make meshes CONFIG=config/local.yaml
make assets CONFIG=config/local.yaml
make preview CONFIG=config/local.yaml
make operator-qa CONFIG=config/local.yaml
make milestone6-readiness
make milestone7-readiness
make milestone8a-readiness
make milestone8b-readiness
make milestone9-readiness
make validate-manifest
make all CONFIG=config/local.yaml
```

## Caveats

- the full EM and segmentation volumes are far too large for a practical local
  mirror, so this repo intentionally stays selective;
- FlyWire Codex portal exports can change names over time, so check the portal
  if a filename differs;
- `make verify` and `make meshes` require a valid FlyWire token and network
  access;
- tests, manifest validation, geometry preview, operator QA, and the Milestone 6,
  Milestone 7, Milestone 8A, Milestone 8B, and Milestone 9 readiness passes are all local workflows;
- the default processed operator is now a cotangent-FEM-style surface operator,
  not just a starter graph Laplacian, but a graph-based fallback still exists
  for guarded cases;
- this repo is an asset-preparation and QA pipeline, not the final simulator.
