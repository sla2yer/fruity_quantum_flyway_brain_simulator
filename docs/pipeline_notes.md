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

Milestone 5 uses the versioned geometry bundle contract
`geometry_bundle.v1`. One canonical library path builder owns the
filenames below, and both `scripts/02_fetch_meshes.py` plus
`scripts/03_build_wave_assets.py` use it directly.

Per neuron, the bundle layout is:

- `config.paths.meshes_raw_dir/<root_id>.ply`: raw mesh
- `config.paths.skeletons_raw_dir/<root_id>.swc`: raw skeleton
- `config.paths.processed_mesh_dir/<root_id>.ply`: simplified mesh
- `config.paths.processed_graph_dir/<root_id>_graph.npz`: surface graph
- `config.paths.processed_graph_dir/<root_id>_fine_operator.npz`: fine surface operator
- `config.paths.processed_graph_dir/<root_id>_patch_graph.npz`: patch graph
- `config.paths.processed_graph_dir/<root_id>_coarse_operator.npz`: Galerkin coarse patch operator
- `config.paths.processed_graph_dir/<root_id>_descriptors.json`: derived descriptor sidecar
- `config.paths.processed_graph_dir/<root_id>_qa.json`: QA sidecar

The processed graph archives intentionally separate fine and coarse data:

- the surface graph stores the simplified mesh vertices/faces, sparse surface adjacency/Laplacian arrays, and `surface_to_patch` so every surface vertex has an explicit coarse patch assignment
- the fine operator archive stores cotangent stiffness and mass-normalized operator matrices plus explicit supporting geometry including edge lengths/weights, lumped mass, normals, tangent frames, boundary masks, anisotropy coefficients (`anisotropy_vertex_tensor_diagonal`, `anisotropy_edge_direction_uv`, `anisotropy_edge_multiplier`, `effective_cotangent_weights`), and capped edge-geodesic neighborhoods
- the patch graph stores sparse coarse adjacency/Laplacian arrays plus `patch_sizes`, `patch_centroids`, `patch_seed_vertices`, and CSR-style `member_vertex_indices` / `member_vertex_indptr` arrays for reconstructing patch membership deterministically
- the coarse operator archive stores patch mass / area, Galerkin-projected stiffness, the mass-normalized coarse operator, and the quality metrics used to compare coarse and fine application
- `config.paths.processed_graph_dir/<root_id>_transfer_operators.npz` stores explicit fine/coarse transfer structure, physical-field restriction / prolongation matrices, normalized-state transfer operators, and transfer-quality metrics
- `config.paths.processed_graph_dir/<root_id>_operator_metadata.json` records the realized discretization family, fallback mode, versioned `operator_assembly` config, boundary mode, anisotropy model, geodesic-neighborhood settings, transfer availability, coarse assembly rule, and coarse-versus-fine quality metrics for downstream discovery

`config.paths.manifest_json` records the bundle contract version, dataset,
materialization version, an explicit meshing-config snapshot including
`meshing.operator_assembly`, and per-root asset
statuses/paths. Raw fetch runs also record `raw_asset_provenance` per
root ID so cache hits, refetches, skips, validation failures, and
optional skeleton fetch errors can be audited without reading console
logs. Processed bundle records also expose `artifact_sources` so each
simplified mesh, surface graph, patch graph, and sidecar points back to
the raw mesh and skeleton inputs it was built against.

Descriptor and QA rationale:

- `docs/geometry_descriptor_qa.md` documents the default `meshing.qa_thresholds`
  profile, what each descriptor bucket is meant to capture, and which failed
  checks should block downstream use by default.

Compatibility shim:

- `config.paths.processed_graph_dir/<root_id>_meta.json` is still written as
  a legacy metadata pointer so older consumers can keep reading the prior
  sidecar name during migration.
- `docs/operator_bundle_design.md` is the authoritative Milestone 6 operator
  decision note; later tickets should cite it instead of re-litigating the
  default discretization family.

### Offline operator QA contract

Milestone 6 also now defines one deterministic offline inspection workflow for
operator bundles:

- `scripts/06_operator_qa.py` reads the local fine operator, coarse operator,
  transfer bundle, patch graph, and operator metadata for one or more root IDs
- output goes to `config.paths.operator_qa_dir/root-ids-<sorted-root-ids>/`
- the report is static: `index.html`, `report.md`, `summary.json`,
  per-root detail JSON, and SVG panels for pulse initialization, boundary-mask
  inspection, patch decomposition, smoke-evolved fine/coarse fields, and coarse
  reconstruction error
- the report summary includes pass / warn / fail checks plus a Milestone 10
  gate of `go`, `review`, or `hold`
- `scripts/07_milestone6_readiness.py` layers a fixture-suite check plus a
  manifest/operator-contract audit on top of the operator QA bundle and writes
  `milestone_6_readiness.md` plus `milestone_6_readiness.json` into the same
  deterministic report directory
- `make milestone6-readiness` is the one-command entrypoint for the shipped
  offline verification pass; it uses `config/milestone_6_verification.yaml`
  so the local build can run entirely from the cached bundle without touching
  user-specific `config/local.yaml`

See `docs/operator_qa.md` for the full reviewer checklist and gate semantics.
