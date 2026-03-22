# Pipeline notes

## Recommended workflow

1. Use FlyWire Codex bulk exports for stable metadata snapshots.
2. Use CAVE / fafbseg for programmatic per-neuron access.
3. Build local preprocessed assets so the simulator does not talk to FlyWire live during runtime.
4. Use `make simulate` for the manifest-driven local simulator execution path.

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
so downstream pipeline steps can switch subsets without code changes. When
`config.paths.synapse_source_csv` is configured, the same active-preset write
also refreshes `config.paths.processed_coupling_dir/synapse_registry.csv` so
the canonical local synapse table stays aligned with the active selected roots.

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

### Synapse and coupling handoff contract

Milestone 7 now reserves one explicit synapse/coupling discovery surface under
the versioned contract `coupling_bundle.v1`.

The canonical layout is:

- `config.paths.processed_coupling_dir/synapse_registry.csv`: local,
  simulator-facing synapse registry owned by the library contract
- `config.paths.processed_coupling_dir/roots/<root_id>_incoming_anchor_map.npz`:
  postsynaptic landing-anchor lookup for one root
- `config.paths.processed_coupling_dir/roots/<root_id>_outgoing_anchor_map.npz`:
  presynaptic readout-anchor lookup for one root
- `config.paths.processed_coupling_dir/roots/<root_id>_coupling_index.json`:
  root-local coupling discovery index that can enumerate realized edge bundles
- `config.paths.processed_coupling_dir/edges/<pre_root_id>__to__<post_root_id>_coupling.npz`:
  canonical edge-level coupling bundle path

Mapping payload notes:

- root-local anchor maps and edge bundles are deterministic `.npz` tables keyed
  by canonical synapse-row IDs rather than opaque simulator-only blobs
- each mapped synapse side records:
  - the query-coordinate source used (`pre_xyz`, `post_xyz`, or fallback
    `synapse_xyz`)
  - the realized anchor mode, anchor type, and anchor resolution
  - anchor coordinates, Euclidean distance, residual vector, and a local support
    scale for QA
  - structured mapping and quality statuses plus any fallback or blocked reason
- surface anchoring currently resolves to coarse patch IDs and patch centroids;
  the supporting nearest surface vertex and its distance are also serialized for
  auditability
- skeleton fallback currently resolves to the nearest raw SWC node
- point-neuron fallback resolves to one deterministic root-local lumped anchor
  derived from the mean available query point for that root and direction

Status semantics:

- mapping status `mapped`: the root's primary supported representation was used
- mapping status `mapped_with_fallback`: a lower-priority fallback mode was used
  because a higher-resolution anchor was unavailable or unsupported
- mapping status `blocked`: no supported anchor could be produced for that
  synapse side; downstream code must inspect `blocked_reason` rather than
  assuming the row disappeared
- quality status `ok`: anchor distance stayed within the local support scale of
  the chosen representation
- quality status `warn`: mapping succeeded but the anchor distance exceeded that
  local support scale; inspect the residuals before trusting the localization
- quality status `unavailable`: quality metrics could not be computed because
  the mapping was blocked

Registry-layer materialization notes:

- `config.paths.synapse_source_csv` is the explicit per-synapse local snapshot
  input when available
- the registry loader normalizes source aliases into one canonical synapse
  schema and requires `pre_root_id`, `post_root_id`, plus at least one complete
  localization field set (`x/y/z`, `pre_x/pre_y/pre_z`, or
  `post_x/post_y/post_z`)
- `config.paths.processed_coupling_dir/synapse_registry_provenance.json` is the
  audit sidecar for the current canonical local synapse registry
- subset extraction keeps only rows where both endpoints are in the requested
  root set so grouping the synapse registry by `(pre_root_id, post_root_id,
  neuropil, nt_type)` reproduces the same-scope edge-level `syn_count`

`config.paths.manifest_json` now also records:

- `_coupling_contract_version` and `_coupling_contract` at the manifest header
- a per-root `coupling_bundle` block that points to the local synapse registry,
  root-local anchor maps, the root-local coupling index, and any explicit
  edge-bundle references already built for that root
- the design-note path and design-note version each bundle conforms to

The default Milestone 7 semantics are intentionally fixed early:

- topology family: `distributed_patch_cloud`
- fallback hierarchy: `surface_patch_cloud` ->
  `skeleton_segment_cloud` -> `point_neuron_lumped`
- kernel family: `separable_rank_one_cloud`
- sign representation: `categorical_sign_with_signed_weight`
- delay representation: `nonnegative_delay_ms_per_synapse_or_delay_bin`
- delay model: `constant_zero_ms`
- multi-synapse aggregation: `sum_over_synapses_preserving_sign_and_delay_bins`
- source/target cloud normalization: `sum_to_one_per_component`

`docs/coupling_bundle_design.md` is the authoritative Milestone 7 decision note;
later tickets should cite it instead of re-litigating the default coupling
family, fallback hierarchy, or sign/delay/aggregation invariants.

### Stimulus bundle contract

Milestone 8A now reserves one explicit visual-stimulus discovery surface under
the versioned contract `stimulus_bundle.v1`.

The library-owned default layout is:

- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_bundle.json`:
  authoritative stimulus descriptor and replay metadata
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_frames.npz`:
  optional cached frame stack derived from the descriptor
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_preview.gif`:
  reserved optional animation slot; the current local recorder marks it as skipped
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/preview/index.html`:
  static offline preview report
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/preview/summary.json`:
  machine-readable preview summary
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/preview/frames/frame-<index>.svg`:
  deterministic preview frame images
- `data/processed/stimuli/aliases/<alias_family>/<alias_name>/<parameter_hash>.json`:
  compatibility alias record pointing old names at the canonical bundle

Contract notes:

- bundle paths, metadata serialization, alias paths, and discovery now live in
  `flywire_wave.stimulus_contract` rather than ad hoc script code
- the descriptor metadata records the stimulus-contract version, design-note
  version, canonical stimulus family/name, deterministic seed, RNG family,
  parameter snapshot, parameter hash, spatial frame, temporal sampling, and
  luminance convention
- the default representation family is `hybrid_descriptor_plus_cache`:
  descriptor metadata is authoritative and frame caches are optional
- the shipped Milestone 8A recorder emits static offline preview sidecars
  alongside the reserved GIF asset slot so preview inspection stays local and deterministic
- timing is always expressed in milliseconds with `sample_hold` frame playback
- the canonical spatial frame is `visual_field_degrees_centered` with origin at
  the aperture center, positive azimuth to the right, positive elevation up,
  and pixel centers as sampling points
- luminance is always interpreted as linear values in `[0.0, 1.0]` with neutral
  gray `0.5`; signed contrast parameters are deltas relative to that neutral
  gray
- compatibility aliases may rename stimulus family/name, but they may not
  mutate seed, timing, spatial frame, luminance semantics, or generator
  parameters

The practical replay key is the tuple `(contract_version, stimulus_family,
stimulus_name, parameter_hash)`. Later manifests and tooling should resolve
stimuli through the library contract instead of hardcoded frame filenames.

`docs/stimulus_bundle_design.md` is the authoritative Milestone 8A decision
note; later tickets should cite it instead of re-litigating the representation
family, replay semantics, or coordinate/luminance conventions.

### Retinal input bundle contract

Milestone 8B now reserves one explicit retinal-input discovery surface under
the versioned contract `retinal_input_bundle.v1`.

The library-owned default layout is:

- `config.paths.processed_retinal_dir/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/retinal_input_bundle.json`:
  authoritative retinal descriptor and replay metadata
- `config.paths.processed_retinal_dir/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/retinal_frames.npz`:
  optional sampled-frame archive derived from that descriptor

Contract notes:

- bundle paths, deterministic retinal-spec hashing, metadata serialization, and
  artifact discovery now live in `flywire_wave.retinal_contract` rather than
  ad hoc script code
- bundle identity is the tuple `(contract_version, source_kind, source_family,
  source_name, source_hash, retinal_spec_hash)`
- the bundle records an explicit upstream `source_reference` so later tooling
  can trace the retinal recording back to the canonical stimulus or scene that
  produced it
- `retinal_input_bundle.v1` freezes one canonical frame meaning:
  dense `time x eye x ommatidium` arrays with explicit eye order and stable
  eye-local ommatidial indexing
- the same bundle also records one default simulator-facing
  `early_visual_unit_stack` mapping with dense `time x eye x unit x channel`
  layout, one `irradiance` channel, identity aggregation from ommatidium to
  unit index, no adaptation, and explicit normalization semantics
- the default and only supported v1 representation family is
  `direct_per_ommatidium_irradiance`; eye-image rasters and higher-level
  feature maps are downstream derived views rather than the source-of-truth
  contract
- timing is always expressed in milliseconds with `sample_hold` semantics
- detector values use linear irradiance in `[0.0, 1.0]` with neutral `0.5` and
  signed contrast interpreted relative to that neutral point
- the coordinate block records one canonical right-handed world, body, head,
  and eye frame convention so later scene, simulator, and UI work do not
  silently disagree about orientation
- the sampling-kernel block records the realized acceptance model, support
  radius, normalization, and out-of-field fill behavior needed for
  deterministic replay

`docs/retinal_bundle_design.md` is the authoritative Milestone 8B decision
note; later tickets should cite it instead of re-litigating the retinal
abstraction family, coordinate frames, or what one retinal frame means.

### Surface-wave model contract

Milestone 10 now reserves one explicit wave-model discovery surface under the
versioned contract `surface_wave_model.v1`.

The library-owned default layout is:

- `data/processed/surface_wave_models/bundles/<model_family>/<parameter_hash>/surface_wave_model.json`:
  authoritative normalized wave-model metadata and parameter bundle

Contract notes:

- model-family naming, parameter normalization, parameter hashing, metadata
  serialization, and metadata-path discovery now live in
  `flywire_wave.surface_wave_contract` rather than ad hoc solver code
- bundle identity is the tuple `(contract_version, model_family,
  parameter_hash)`
- the selected Milestone 10 roadmap family is
  `hybrid_field_readout_system`, realized in v1 as the canonical software
  model family `hybrid_damped_wave_recovery`
- the canonical state catalog is:
  `surface_activation` (`activation_au`), `surface_velocity`
  (`activation_au_per_ms`), and the optional `recovery_state` (`unitless`)
- the propagation term is defined against the Milestone 6 mass-normalized
  surface operator; damping is a separate linear sink on `surface_velocity`
- synaptic injection semantics reuse Milestone 7 sign, delay, aggregation, and
  landing-anchor rules and add the realized source to `surface_velocity`
  through one named source mode `coupling_anchor_current`
- recovery, nonlinearity, anisotropy, and branching now have explicit mode
  identifiers in the contract even when the shipped default preset keeps them
  disabled or in identity mode
- the canonical v1 solver family identifier is
  `semi_implicit_velocity_split`, and later stability checks are expected to
  derive timestep guards from operator spectra rather than graph-degree rules
- `resolve_surface_wave_model_metadata_path()` and
  `build_surface_wave_model_reference()` are the discovery helpers later
  planning, execution, and result code should use instead of hardcoded strings

`docs/surface_wave_model_design.md` is the authoritative Milestone 10 decision
note; later tickets should cite it instead of re-litigating the chosen wave
family, state-variable semantics, stability assumptions, or what counts as a
numerical artifact.

### Hybrid morphology contract

Milestone 11 now reserves one explicit mixed-fidelity vocabulary under the
versioned contract `hybrid_morphology.v1`.

Contract notes:

- class naming, class normalization, per-root metadata normalization, stable
  class discovery, and the allowed cross-class route catalog now live in
  `flywire_wave.hybrid_morphology_contract`
- the canonical simulator-facing classes are `surface_neuron`,
  `skeleton_neuron`, and `point_neuron`, normalized from the existing registry
  roles `surface_simulated`, `skeleton_simulated`, and `point_simulated`
- mixed fidelity stays inside the existing `surface_wave` planning path rather
  than introducing a second top-level simulator mode; the planner writes the
  normalized payload at `surface_wave_execution_plan.hybrid_morphology`
- the normalized payload records:
  - per class required and optional local assets
  - realized state-space semantics
  - local readout surface semantics
  - incoming and outgoing coupling-anchor resolution
  - serialization requirements for planning and result review
  - approximation notes and intentional class-specific behavior
- promotion order is `point_neuron -> skeleton_neuron -> surface_neuron`
- promotion or demotion may refine intraneuron state resolution, but it may not
  change selected root IDs, selected connectome edges, shared readout IDs,
  shared timebase semantics, or Milestone 7 sign/delay/aggregation semantics
- all source/target class pairs are explicit contract routes; the source class
  supplies the presynaptic readout surface and outgoing anchor resolution, and
  the target class supplies the landing surface and incoming anchor resolution
- the same normalized payload is mirrored into surface-wave execution
  provenance and the wave summary sidecar so later review tooling sees one
  stable serialization surface

`docs/hybrid_morphology_design.md` is the authoritative Milestone 11 decision
note; later tickets should cite it instead of re-litigating mixed-fidelity
class names, approximation limits, or promotion invariants.

### Simulator result bundle contract

Milestone 9 now reserves one explicit simulator-owned result surface under the
versioned contract `simulator_result_bundle.v1`.

The library-owned default layout is:

- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/simulator_result_bundle.json`:
  authoritative per-arm run metadata and artifact inventory
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/state_summary.json`:
  comparison-ready long-table state summaries
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/readout_traces.npz`:
  shared readout traces on the canonical simulator timebase
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/metrics.csv`:
  comparison-ready metric rows keyed by stable readout IDs
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/extensions/<file_name>`:
  deterministic execution logs, provenance, UI comparison payloads, and any
  later model-specific diagnostics

Contract notes:

- bundle paths, run-spec hashing, metadata serialization, and artifact
  discovery now live in `flywire_wave.simulator_result_contract` rather than
  ad hoc runner code
- bundle identity is the tuple `(contract_version, experiment_id, arm_id,
  run_spec_hash)`
- the bundle records manifest identity, arm identity, model mode, baseline
  family, seed, shared timebase, ordered selected-asset references, ordered
  shared readout catalog, and the output artifact inventory needed for
  deterministic replay
- timing is always expressed in milliseconds with one declared
  `fixed_step_uniform` timebase shared by state summaries, trace export, and
  metric rows
- `P0` is the canonical passive leaky linear single-compartment baseline and
  `P1` is the stronger reduced baseline with explicit integration current or
  deterministic delay structure; both still use the same shared readout
  contract
- extra wave diagnostics may be written under `extensions/`, but shared
  baseline-versus-wave comparison artifacts keep the same top-level filenames
  and payload conventions
- `scripts/run_simulation.py` is the public Milestone 9 local execution path:
  it resolves manifest arms, runs `baseline` or `surface_wave`, writes the
  canonical bundle, and emits bundle-discovered `structured_log.jsonl`,
  `execution_provenance.json`, `ui_comparison_payload.json`, and any
  wave-specific extension artifacts needed by morphology-resolved runs
- local wave execution uses the same public entrypoint, for example:
  `python scripts/run_simulation.py --config <config> --manifest <manifest> --schema <schema> --design-lock <design-lock> --model-mode surface_wave --arm-id surface_wave_intact`
- `scripts/15_surface_wave_inspection.py` is the Milestone 10 local audit path:
  it resolves one or more normalized `surface_wave` arm plans, expands a
  deterministic parameter sweep, runs coupled executions plus representative
  single-neuron pulse probes, and writes review-friendly `report.md`,
  `summary.json`, `runs.csv`, per-run trace archives, and SVG trace panels
- output goes to
  `config.paths.surface_wave_inspection_dir/experiment-<experiment-id>__arms-<arm-slug>__sweep-<hash>/`
- the audit emits compact `pass`, `warn`, or `fail` checks for finite-value
  stability, pulse-energy growth, wavefront detection, driven dynamic range,
  spatial contrast, coupling-event presence, and large peak-to-drive ratios
- `scripts/16_milestone10_readiness.py` is the shipped integration-audit path:
  it layers a focused fixture suite plus deterministic `surface_wave`
  execution, baseline comparison, documentation checks, and the shipped
  inspection workflow on top of `scripts/run_simulation.py` and
  `scripts/15_surface_wave_inspection.py`
- the readiness report goes to
  `config.paths.processed_simulator_results_dir/readiness/milestone_10/milestone_10_readiness.md`
  and
  `config.paths.processed_simulator_results_dir/readiness/milestone_10/milestone_10_readiness.json`
- `make milestone10-readiness` is the one-command entrypoint for the shipped
  Milestone 10 integration verification pass
- that readiness gate uses `config/surface_wave_sweep.verification.yaml` as one
  conservative non-runaway local reference bundle for stability review
- `config/surface_wave_sweep.example.yaml` remains the broader exploratory
  local sweep and is not the readiness gate
- `scripts/14_milestone9_readiness.py` layers a focused fixture suite plus a
  deterministic manifest-driven baseline audit on top of
  `scripts/run_simulation.py` and writes `milestone_9_readiness.md` plus
  `milestone_9_readiness.json` under
  `config.paths.processed_simulator_results_dir/readiness/milestone_9/`
- `make milestone9-readiness` is the one-command entrypoint for the shipped
  Milestone 9 readiness pass

`docs/simulator_result_bundle_design.md` is the authoritative Milestone 9
decision note; later tickets should cite it instead of re-litigating baseline
fairness, shared readout semantics, or the result-bundle layout.

### Offline retinal inspection contract

Milestone 8B now also defines one deterministic offline inspection workflow for
world-view versus fly-view review:

- `scripts/12_retinal_bundle.py inspect` reads one cached retinal bundle, or
  resolves the canonical bundle path from a retinal config or scene entrypoint
- output goes to the bundle-local directory `.../<retinal_spec_hash>/inspection/`
- the report is static: `index.html`, `report.md`, `summary.json`,
  `coverage_layout.svg`, and paired world-view plus retinal-view SVG frame
  panels under `frames/`
- the report summary emits compact `pass`, `warn`, or `fail` checks for source
  preview availability, timing consistency, detector-value validity, and
  detector coverage
- the workflow writes deterministic inspection pointers back into
  `retinal_input_bundle.json` under `inspection` so later simulator and UI code
  can discover the offline review artifacts from bundle metadata alone
- `scripts/13_milestone8b_readiness.py` layers a focused fixture suite plus a
  config/manifest/scene integration audit on top of the record/replay/inspect
  workflow and writes `milestone_8b_readiness.md` plus
  `milestone_8b_readiness.json` under
  `config.paths.processed_retinal_dir/readiness/milestone_8b/`
- `make milestone8b-readiness` is the one-command entrypoint for the shipped
  Milestone 8B readiness pass

See `docs/retinal_inspection.md` for the reviewer checklist and failure
interpretation.

### Offline coupling inspection contract

Milestone 7 now also defines one deterministic offline inspection workflow for
edge-level coupling review:

- `scripts/08_coupling_inspection.py` reads the local synapse registry, one or
  more edge bundles, the matching root-local anchor maps, and whichever local
  geometry artifacts are needed by the realized anchor types
- output goes to `config.paths.coupling_inspection_dir/edges-<sorted-edge-slug>/`
- the report is static: `index.html`, `report.md`, `summary.json`, `edges.txt`,
  per-edge detail JSON, and SVG panels for presynaptic readout plus
  postsynaptic landing geometry
- each edge emits compact `pass`, `warn`, `fail`, or `blocked` QA flags for
  mapping coverage, anchor-map consistency, component integrity, cloud
  normalization, and delay sanity
- the detail JSON keeps the metric table, blocked-synapse rows, and aggregate
  component rows in a review-friendly format so regressions can be asserted in
  fixture tests
- `scripts/09_milestone7_readiness.py` layers a fixture-suite check plus a
  registry/subset/coupling-contract audit on top of the coupling inspection
  bundle and writes `milestone_7_readiness.md` plus
  `milestone_7_readiness.json` into the same deterministic report directory
- `make milestone7-readiness` is the one-command entrypoint for the shipped
  offline Milestone 7 verification pass; it uses
  `config/milestone_7_verification.yaml` plus a tracked edge list so the local
  audit can run entirely from cached mesh and skeleton assets plus the curated
  Milestone 7 verification synapse snapshot

See `docs/coupling_inspection.md` for the reviewer checklist and threshold
override semantics.

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
- the report summary includes pass / warn / fail checks plus an
  `operator_readiness_gate` of `go`, `review`, or `hold`
- `scripts/07_milestone6_readiness.py` layers a fixture-suite check plus a
  manifest/operator-contract audit on top of the operator QA bundle and writes
  `milestone_6_readiness.md` plus `milestone_6_readiness.json` into the same
  deterministic report directory
- `scripts/03_build_wave_assets.py` now records missing raw meshes as
  structured per-root blocked prerequisites, writes the full manifest for all
  attempted roots, and exits non-zero only after the end-of-run summary is
  emitted
- `make milestone6-readiness` is the one-command entrypoint for the shipped
  offline verification pass; it uses `config/milestone_6_verification.yaml`
  so the local build can run entirely from the cached bundle without touching
  user-specific `config/local.yaml`

See `docs/operator_qa.md` for the full reviewer checklist and gate semantics.
