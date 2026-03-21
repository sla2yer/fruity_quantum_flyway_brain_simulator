# FlyWire Female Brain → Selective Meshing Starter Repo

This scaffold is for the **adult female Drosophila FlyWire brain** (`FAFB v783`) with a workflow that matches your project constraint:

- keep the **whole brain mapped**,
- only **simulate a selected subset**,
- fetch **meshes/skeletons per neuron**,
- precompute **surface graphs / Laplacians / active patches** for the wave-capable part of the sim.

## What this repo is for

This is **not** a whole-brain bulk mirror. The full EM volume and segmentation are too large for conventional downloads. Instead, the intended workflow is:

1. download **bulk metadata tables** from Codex,
2. query the **public FlyWire datastack** through CAVE,
3. fetch **only the neurons you want to simulate** as meshes/skeletons,
4. simplify those meshes and build graph/Laplacian assets for your wave solver.

That gives you the best of both worlds:
- the female whole brain remains the structural source of truth,
- runtime stays manageable because only chosen neurons are meshed into simulation assets.

## Source-of-truth download locations

### 1) Bulk tables / annotations
Use the Codex download portal for the **FAFB** dataset:

- `https://codex.flywire.ai/api/download?dataset=fafb`

Recommended files to place in `data/raw/codex/`:
- `classification.csv`
- `consolidated_cell_types.csv`
- the Codex synapse table for FAFB v783
- the Codex neuron / neurotransmitter export for FAFB v783

Notes:
- file names have varied a bit across downstream analysis repos, so always trust the portal first;
- this scaffold is written so that `classification.csv` is the only hard requirement for subset selection.

### 2) Public programmatic access
Use the public CAVE datastack:

- datastack: `flywire_fafb_public`
- materialization target in this repo: `783`

### 3) Meshes and skeletons
Meshes are **not** bulk-downloaded directly from Codex. Fetch them per neuron using:
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
│   └── 03_build_wave_assets.py
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

## Quick start

### 1) Create environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Put your token in `.env`

```bash
cp .env.example .env
```

Then set:

```env
FLYWIRE_TOKEN=your_token_here
```

You can generate/store the token using the FlyWire/CAVE docs, or let this repo save it for local use.

### 3) Download the Codex metadata exports

Place the files you downloaded from Codex into:

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
- Codex portal exports can change names over time; check the portal if a filename differs.
- Mesh fetching depends on a valid token and network access.
- The provided Laplacian is a **starter graph Laplacian**, not a full finite-element surface operator.
- This scaffold is for preprocessing / asset generation, not the final simulator.

## Good next steps after this scaffold

- add synapse-to-vertex projection,
- create branch-aware active patches,
- build a local wave PDE / reaction-diffusion solver on the simplified mesh graph,
- add a scheduler that promotes neurons from latent → mesh-wave only when needed.
