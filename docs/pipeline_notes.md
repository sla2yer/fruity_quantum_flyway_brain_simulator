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

## Output asset contract

Per neuron, the processed output includes:

- `root_id.ply` simplified mesh
- `root_id_graph.npz` adjacency + Laplacian + patch mask
- `root_id_meta.json` counts and preprocessing metadata

Those files are the handoff point into a later simulator.
