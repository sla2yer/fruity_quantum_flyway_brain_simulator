# Pipeline notes

## Recommended workflow

1. Use FlyWire Codex bulk exports for stable metadata snapshots.
2. Use CAVE / fafbseg for programmatic per-neuron access.
3. Build local preprocessed assets so the simulator does not talk to FlyWire live during runtime.

## Why this repo uses selective meshing

The female whole brain is the structural scaffold, but the final simulation should only keep a small subset in a mesh-wave state at once. That matches a multiresolution strategy:

- whole brain mapped,
- selected circuit meshed,
- only active patches numerically updated.

## Artifact contracts

### Subset-selection contract

Milestone 4 subset generation writes one artifact bundle per named preset under
`data/interim/subsets/<preset>/`:

- `root_ids.txt`: simulator-facing root-id list
- `selected_neurons.csv`: filtered registry rows for the preset
- `subset_stats.json`: graph counts, role counts, and boundary summaries
- `subset_manifest.json`: resolved selection rules plus the selected neuron roster
- `preview.md`: lightweight Markdown/Mermaid preview for quick inspection

The active preset also refreshes the path named by `config.paths.selected_root_ids`
so downstream pipeline steps can switch subsets without code changes.

### Geometry handoff contract

Per neuron, the processed output includes:

- `root_id.ply` simplified mesh
- `root_id_graph.npz` adjacency + Laplacian + patch mask
- `root_id_meta.json` counts and preprocessing metadata

Those files are the handoff point into a later simulator.
