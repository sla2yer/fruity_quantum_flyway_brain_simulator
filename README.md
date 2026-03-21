# FlyWire Female Brain → Selective Meshing Starter Repo

This scaffold is for the **adult female Drosophila FlyWire brain** (`FAFB v783`) with a workflow that matches your project constraint:

- keep the **whole brain mapped**,
- only **simulate a selected subset**,
- fetch **meshes/skeletons per neuron**,
- precompute **surface graphs / Laplacians / active patches** for the wave-capable part of the sim.

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
- `consolidated_cell_types.csv`
- the FlyWire Codex synapse table for FAFB v783
- the FlyWire Codex neuron / neurotransmitter export for FAFB v783

Notes:
- file names have varied a bit across downstream analysis repos, so always trust the portal first;
- this scaffold is written so that `classification.csv` is the only hard requirement for subset selection.

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
├── requirements.txt
├── Makefile
├── .env.example
├── config/
│   └── visual_subset.example.yaml
├── docs/
│   └── pipeline_notes.md
├── scripts/
│   ├── 00_verify_access.py
│   ├── 01_select_subset.py
│   ├── 02_fetch_meshes.py
│   ├── 03_build_wave_assets.py
│   └── setup_flywire_token.py
├── src/
│   └── flywire_wave/
│       ├── __init__.py
│       ├── config.py
│       ├── io_utils.py
│       ├── mesh_pipeline.py
│       └── selection.py
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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

At minimum, put:

```text
data/raw/codex/classification.csv
```

### 4) Copy the example config

```bash
cp config/visual_subset.example.yaml config/local.yaml
```

### 5) Verify access

```bash
python scripts/00_verify_access.py --config config/local.yaml
```

### 6) Select a subset to mesh

Default example: select a small visual subset from `classification.csv`.
The current FlyWire export uses `visual_projection` rather than `visual`, and
the sample config is set accordingly.

```bash
python scripts/01_select_subset.py --config config/local.yaml
```

This writes a root-id list to something like:

```text
data/interim/root_ids_visual_sample.txt
```

### 7) Fetch meshes + skeletons

```bash
python scripts/02_fetch_meshes.py --config config/local.yaml
```

This downloads raw per-neuron assets into:

```text
data/interim/meshes_raw/
data/interim/skeletons_raw/
```

### 8) Build wave-ready mesh assets

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

```bash
make verify CONFIG=config/local.yaml
make select CONFIG=config/local.yaml
make meshes CONFIG=config/local.yaml
make assets CONFIG=config/local.yaml
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
