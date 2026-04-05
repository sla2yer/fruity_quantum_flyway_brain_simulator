# Geometry Preview Workflow

Milestone 5 preview generation is intentionally offline. The preview step reads
only local files that were already produced by the pipeline:

- raw mesh: `config.paths.meshes_raw_dir/<root_id>.ply`
- simplified mesh: `config.paths.processed_mesh_dir/<root_id>.ply`
- optional skeleton: `config.paths.skeletons_raw_dir/<root_id>.swc`
- surface graph: `config.paths.processed_graph_dir/<root_id>_graph.npz`
- patch graph: `config.paths.processed_graph_dir/<root_id>_patch_graph.npz`
- optional sidecars: descriptor and QA JSON written by `scripts/03_build_wave_assets.py`

## Generate a preview

Preview one or more specific root IDs:

```bash
python scripts/05_preview_geometry.py --config config/local.yaml --root-id 101 --root-id 102
```

Preview the active selected subset from `config.paths.selected_root_ids`:

```bash
python scripts/05_preview_geometry.py --config config/local.yaml --limit 4
```

Equivalent Make target:

```bash
make preview CONFIG=config/local.yaml
```

The output location is deterministic for the exact root-id set. By default the
script writes to:

```text
config.paths.geometry_preview_dir/root-ids-<sorted-root-ids>/
```

Example:

```text
data/processed/previews/root-ids-101-102/index.html
data/processed/previews/root-ids-101-102/summary.json
data/processed/previews/root-ids-101-102/root_ids.txt
```

That makes the report path stable enough to reference from run logs, ticket
notes, or review comments.

If one or more required preview inputs are missing, the command still writes the
deterministic preview directory and returns a structured blocked summary instead
of aborting on the first `FileNotFoundError`. The summary records the blocked
root IDs, missing asset keys, resolved paths, and whether the operator should
rerun `make meshes`, `make assets`, or both.

## What the report shows

Each root section keeps the following in one place:

- raw mesh wireframe
- simplified mesh wireframe
- skeleton projection or an explicit unavailable marker
- surface graph projection
- patch graph projection
- bundle summary metrics, artifact paths, and QA highlights

The HTML is fully static and does not require a notebook server, Neuroglancer,
or FlyWire access.

## Reviewer checklist

Reviewers should look for:

- raw vs simplified mesh silhouette staying broadly consistent rather than collapsing or drifting
- skeleton presence matching expectations for that neuron and following the same gross orientation as the meshes when available
- surface graph coverage matching the simplified geometry instead of showing obvious holes or disconnected clutter
- patch graph being non-empty and spatially distributed rather than collapsing to one dominant patch unless that is expected
- QA warnings or failures that suggest simplification drift, patch coverage gaps, or coarse graph degeneracy
