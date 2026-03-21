# FlyWire Female Brain → Selective Meshing Starter Repo

This scaffold is for the **adult female Drosophila FlyWire brain** (`FAFB v783`) with a workflow that matches your project constraint:

- keep the **whole brain mapped**,
- only **simulate a selected subset**,
- fetch **meshes/skeletons per neuron**,
- precompute **surface graphs / Laplacians / active patches** for the wave-capable part of the sim.

If you're onboarding quickly or using a coding agent, start with [`AGENTS.md`](AGENTS.md).

## What this repo is for

This is **not** a whole-brain bulk mirror. The full EM volume and segmentation are too large for conventional downloads. Instead, the intended workflow is:

1. download **bulk metadata tables** from FlyWire Codex,
2. query the **public FlyWire datastack** through CAVE,
3. fetch **only the neurons you want to simulate** as meshes/skeletons,
4. simplify those meshes and build graph/Laplacian assets for your wave solver.

That gives you the best of both worlds:
- the female whole brain remains the structural source of truth,
- runtime stays manageable because only chosen neurons are meshed into simulation assets.

## Source-of-truth download locations

### 1) Bulk tables / annotations
Use the FlyWire Codex download portal for the **FAFB** dataset:

- `https://codex.flywire.ai/api/download?dataset=fafb`

Recommended files to place in `data/raw/codex/`:
- `classification.csv`
- `cell_types.csv` or `consolidated_cell_types.csv`
- `connections_filtered.csv` or `connections.csv`
- `neurotransmitter_type_predictions.csv` or `neurons.csv`
- optional visual annotations such as `visual_neuron_annotations.csv` and `visual_neuron_columns.csv`

Notes:
- file names have varied a bit across downstream analysis repos, so always trust the portal first;
- the registry builder will use the extra exports when present, but still tolerates a minimal `classification.csv`-only setup.

### 2) Public programmatic access
Use the public CAVE datastack:

- datastack: `flywire_fafb_public`
- materialization target in this repo: `783`

### 3) Meshes and skeletons
Meshes are **not** bulk-downloaded directly from FlyWire Codex. Fetch them per neuron using:
- `fafbseg` / `cloudvolume` / `meshparty`
- or the FlyConnectome notebooks as reference

Skeletons for proofread public neurons are also available through the FlyWire annotations repo:
- `https://github.com/flyconnectome/flywire_annotations`

## Repo layout

```text
flywire_wave_repo/
├── README.md
├── AGENTS.md
├── requirements.txt
├── pyproject.toml
├── Makefile
├── .env.example
├── config/
│   ├── milestone_1_design_lock.yaml
│   └── visual_subset.example.yaml
├── docs/
│   ├── milestones.md
│   ├── pipeline_notes.md
│   └── subset_presets.md
├── manifests/
│   └── examples/
│       └── milestone_1_demo.yaml
├── schemas/
│   └── milestone_1_experiment_manifest.schema.json
├── scripts/
│   ├── 00_verify_access.py
│   ├── build_registry.py
│   ├── 01_select_subset.py
│   ├── 02_fetch_meshes.py
│   ├── 03_build_wave_assets.py
│   ├── 04_validate_manifest.py
│   └── setup_flywire_token.py
├── src/
│   └── flywire_wave/
│       ├── __init__.py
│       ├── config.py
│       ├── io_utils.py
│       ├── manifests.py
│       ├── mesh_pipeline.py
│       ├── registry.py
│       └── selection.py
├── tests/
│   ├── test_manifest_validation.py
│   └── test_registry.py
├── flywire_codex/
└── data/
    ├── raw/
    │   └── codex/
    ├── interim/
    └── processed/
```

## FlyWire Authentication

This repo uses two separate auth contexts:

- **FlyWire Codex** (`codex.flywire.ai`) for browser/UI access and bulk CSV/static downloads
- **CAVE / FlyWire API** for local programmatic access through `caveclient`, `fafbseg`, and the repo scripts that read `FLYWIRE_TOKEN` from `.env`

Being signed into **FlyWire Codex** in the browser does **not** automatically configure local Python access. The `FLYWIRE_TOKEN` value in `.env` should be your **FlyWire/CAVE API token**.

Recommended setup flow:

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Launch the helper script:

```bash
python scripts/setup_flywire_token.py
```

This opens the existing-token page first. If you specifically need to mint a new token, run:

```bash
python scripts/setup_flywire_token.py --new-token
```

Creating a new token may invalidate the previous one.

3. Copy the token from the browser page.
4. Paste it into `.env` as `FLYWIRE_TOKEN=...`, or rerun the helper with `--write-env` to update `.env` interactively.
5. Optional: after installing dependencies, save the same token to local CAVE secret storage with `caveclient` if you want machine-wide auth for `caveclient` / `fafbseg`.
6. Rerun access verification:

```bash
python scripts/00_verify_access.py --config config/local.yaml
```

If FlyWire's materialization service is temporarily down, the verifier will now
report that as an upstream outage while still confirming whether your token works
against the global info service. Add `--require-materialize` if you want that
case to return a non-zero exit code.

This keeps the auth split explicit: **FlyWire Codex** handles website browsing/downloads, while `FLYWIRE_TOKEN` handles local API access.

## Quick start

### 1) Create environment

```bash
git submodule update --init --recursive
make bootstrap
```

Initialize the pinned `flywire_codex/` submodule once after cloning, then run `make bootstrap` to create `.venv/` if needed, upgrade `pip`, and install the repo in editable mode via [`pyproject.toml`](pyproject.toml).

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

Then copy the token from the browser page into `.env` as `FLYWIRE_TOKEN=...`, or rerun the helper with `--write-env` to update `.env` interactively.

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

### 5) Verify access

```bash
python scripts/00_verify_access.py --config config/local.yaml
```

### 6) Build the canonical registry

This normalizes the local Codex exports into one neuron registry, one
connectivity registry, and a provenance JSON with pinned snapshot/materialization
metadata plus input file fingerprints.

```bash
python scripts/build_registry.py --config config/local.yaml
```

This writes:

```text
data/interim/registry/neuron_registry.csv
data/interim/registry/connectivity_registry.csv
data/interim/registry/registry_provenance.json
```

### 7) Select a subset to mesh

The Milestone 4 selector is now preset-driven. The sample config defines three
named presets:

- `motion_minimal`
- `motion_medium`
- `motion_dense`

Each run writes a root-id list, selected-neuron CSV, stats JSON, manifest JSON,
and a lightweight Markdown/Mermaid preview under `data/interim/subsets/<preset>/`.
The active preset also refreshes `paths.selected_root_ids` so downstream mesh and
asset steps can switch inputs by config alone.

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

This writes the active root-id list to something like:

```text
data/interim/root_ids_visual_sample.txt
```

And writes per-preset reports to:

```text
data/interim/subsets/
```

### 8) Fetch meshes + skeletons

```bash
python scripts/02_fetch_meshes.py --config config/local.yaml
```

This downloads raw per-neuron assets into:

```text
data/interim/meshes_raw/
data/interim/skeletons_raw/
```

### 9) Build wave-ready mesh assets

```bash
python scripts/03_build_wave_assets.py --config config/local.yaml
```

This creates:
- simplified meshes,
- sparse adjacency,
- graph Laplacians,
- an example active patch per neuron.

Outputs land in:

```text
data/processed/
```

## What “meshing for the simulation” means here

For each selected root ID, this scaffold does:

1. fetch full-resolution FlyWire mesh,
2. simplify it to a target face budget,
3. build a sparse surface graph from triangle connectivity,
4. compute a graph Laplacian,
5. choose an example local patch that can become the wave solver’s active region,
6. save everything as `.npz` / `.json` / `.ply`.

That is enough to support:
- mesh-resolved wave experiments,
- branch/patch-local dynamics,
- synapse-to-patch mapping later,
- selective promotion of only the currently active neurons.

## Milestone 1 design-lock artifacts

Milestone 1 is treated here as a design/specification milestone rather than a proof-of-effect milestone.

- Roadmap and detailed milestone planning: [`docs/milestones.md`](docs/milestones.md)
- Machine-readable design lock and success criteria: [`config/milestone_1_design_lock.yaml`](config/milestone_1_design_lock.yaml)
- Example demo manifest: [`manifests/examples/milestone_1_demo.yaml`](manifests/examples/milestone_1_demo.yaml)
- Manifest schema: [`schemas/milestone_1_experiment_manifest.schema.json`](schemas/milestone_1_experiment_manifest.schema.json)

Validate the example manifest with:

```bash
make validate-manifest
```

or:

```bash
python3 scripts/04_validate_manifest.py \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml
```

## Suggested first run for your project

Do **not** start by meshing hundreds or thousands of neurons.

A good first pass is:
- 10–25 visual neurons,
- simplify each to ~10k–20k faces,
- use one active patch per neuron,
- test your wave solver on the patch graph before scaling up.

Once that is stable, you can add:
- synaptic placement from CAVE metadata,
- cross-neuron coupling,
- neuropil-level sheets,
- scheduler-driven promotion/demotion.

## Make targets

The `Makefile` defaults to `.venv/bin/python` when that virtualenv exists, which makes the local test and pipeline loop work without manually swapping interpreters.

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
make validate-manifest
make all CONFIG=config/local.yaml
```

## Caveats

- The full EM/segmentation volumes are massive; this repo intentionally avoids trying to mirror them locally.
- FlyWire Codex portal exports can change names over time; check the portal if a filename differs.
- Mesh fetching depends on a valid token and network access.
- The provided Laplacian is a **starter graph Laplacian**, not a full finite-element surface operator.
- This scaffold is for preprocessing / asset generation, not the final simulator.

## Good next steps after this scaffold

- add synapse-to-vertex projection,
- create branch-aware active patches,
- build a local wave PDE / reaction-diffusion solver on the simplified mesh graph,
- add a scheduler that promotes neurons from latent → mesh-wave only when needed.
