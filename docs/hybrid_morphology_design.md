# Hybrid Morphology Design

## Purpose

Milestone 11 needs one contract-owned vocabulary for mixed morphology fidelity
before planner code, runtime glue, and result serialization encode different
meanings for the same run. The canonical contract is `hybrid_morphology.v1`,
implemented in `flywire_wave.hybrid_morphology_contract`.

This note reuses earlier locked decisions instead of reopening them:

- Milestone 7 already fixes coupling sign, delay, aggregation, and anchor
  fallback semantics.
- Milestone 9 already fixes the shared result-bundle timebase and readout
  comparison surface.
- Milestone 10 already fixes the `surface_wave` top-level mode plus the default
  surface-wave family and state vocabulary.

Milestone 11 therefore does not add a new top-level simulator mode. Mixed
fidelity stays inside `surface_wave` through per-root morphology-class metadata.

## Contract Summary

`hybrid_morphology.v1` freezes three simulator-facing morphology classes:

- `surface_neuron`
- `skeleton_neuron`
- `point_neuron`

The registry role aliases map directly:

- `surface_simulated` -> `surface_neuron`
- `skeleton_simulated` -> `skeleton_neuron`
- `point_simulated` -> `point_neuron`

The planner-owned metadata lives at
`surface_wave_execution_plan.hybrid_morphology`. Execution provenance and the
wave summary mirror the same normalized payload so review code sees one stable
field path.

## Fidelity Classes

### `point_neuron`

- required local assets:
  `root_local_synapse_registry`, `incoming_anchor_map`, `outgoing_anchor_map`,
  `root_coupling_index`, `selected_edge_coupling_bundles`
- optional local assets:
  `raw_swc_skeleton`, `processed_surface_mesh`, `geometry_descriptors`
- realized state space:
  one root-local lumped state with optional auxiliary terms and no intraneuron
  spatial resolution
- readout surface:
  `root_state_scalar`
- coupling anchor resolution:
  incoming and outgoing `lumped_root_state`
- allowed approximation:
  remove intraneuron propagation while preserving root identity, coupling sign,
  coupling delay, and total signed weight semantics
- intentional class-specific behavior:
  cannot express branch-local or surface-local spread

### `skeleton_neuron`

- required local assets:
  `raw_swc_skeleton`, `skeleton_runtime_asset`,
  `root_local_synapse_registry`, `incoming_anchor_map`, `outgoing_anchor_map`,
  `root_coupling_index`,
  `selected_edge_coupling_bundles`
- optional local assets:
  `processed_surface_mesh`, `surface_transfer_operators`,
  `geometry_descriptors`
- realized state space:
  distributed activation over skeleton nodes or segments
- canonical runtime handoff:
  `skeleton_runtime_asset.v1`, a deterministic local bundle that records the
  rooted graph operator, node order, node masses, and readout semantics derived
  from the cached raw SWC
- readout surface:
  `skeleton_anchor_cloud`
- coupling anchor resolution:
  incoming and outgoing `skeleton_node`
- allowed approximation:
  preserve branch and path structure while omitting explicit surface-sheet
  geometry and patch-local tangential spread
- intentional class-specific behavior:
  may express branch-local timing or attenuation that a point neuron cannot,
  but not surface-sheet effects reserved for `surface_neuron`

### `surface_neuron`

- required local assets:
  `processed_surface_mesh`, `fine_surface_operator`, `coarse_patch_operator`,
  `surface_transfer_operators`, `surface_operator_metadata`,
  `root_local_synapse_registry`, `incoming_anchor_map`, `outgoing_anchor_map`,
  `root_coupling_index`, `selected_edge_coupling_bundles`
- optional local assets:
  `raw_mesh`, `raw_swc_skeleton`, `geometry_descriptors`, `geometry_qa`
- realized state space:
  distributed surface field on the simplified mesh with patch projection
- readout surface:
  `coarse_patch_cloud`
- coupling anchor resolution:
  incoming and outgoing `coarse_patch`
- allowed approximation:
  retain surface-local spread while abstracting away raw membrane biophysics and
  per-synapse state
- intentional class-specific behavior:
  may express geodesic spread, patch-local heterogeneity, anisotropy, and
  descriptor-scaled branching when the wave model enables them

## Cross-Class Coupling Routes

All nine source/target class pairs are contract-valid:

- point -> point
- point -> skeleton
- point -> surface
- skeleton -> point
- skeleton -> skeleton
- skeleton -> surface
- surface -> point
- surface -> skeleton
- surface -> surface

For every route, the source class supplies the presynaptic readout surface and
outgoing anchor resolution, while the target class supplies the landing surface
and incoming anchor resolution. The route may change spatial support, but it
may not change Milestone 7 sign, delay, or aggregation semantics.

## Promotion And Demotion Invariants

Promoting `point_neuron -> skeleton_neuron -> surface_neuron`, or demoting in
the opposite direction, must preserve these meanings unless the contract version
changes:

- selected root IDs and manifest-arm identity stay fixed
- the selected connectome edge set stays fixed
- shared readout IDs, units, and timebase stay fixed
- coupling sign, delay, and aggregation semantics stay fixed
- root-local input identity and comparison-readout meaning stay fixed
- class-specific diagnostics may expand under `extensions/`, but shared result
  payloads do not change shape or semantics

Promotion is therefore allowed to refine intraneuron state resolution and local
spatial patterning. It is not allowed to introduce a new decoder, new edges,
new per-synapse sign rules, or a new top-level model mode.

## Policy Hook

Milestone 11 now exposes one narrow planner-owned policy hook under
`simulation.mixed_fidelity.assignment_policy`. The hook is deterministic and
review-oriented: it does not silently rewrite the realized fidelity assignment.
Instead, it records what a downstream planner or reviewer should consider
promoting or demoting before relying on a mixed-fidelity arm for later readout
or validation work.

Supported fields:

- `default_source`
- `promotion_mode`
- `demotion_mode`
- `recommendation_rules`

`promotion_mode` and `demotion_mode` currently support:

- `disabled`
- `recommend_from_policy`

Each `recommendation_rules[]` entry may declare:

- `minimum_morphology_class` and/or `maximum_morphology_class`
- optional `root_ids` or `cell_types` filters
- optional manifest-context filters:
  `topology_conditions`, `morphology_conditions`, `arm_tags_any`
- optional numeric descriptor thresholds under `descriptor_thresholds`

Example:

```yaml
simulation:
  mixed_fidelity:
    assignment_policy:
      promotion_mode: recommend_from_policy
      demotion_mode: disabled
      recommendation_rules:
        - rule_id: promote_patch_dense_surrogate
          minimum_morphology_class: surface_neuron
          root_ids: [303]
          topology_conditions: [intact]
          arm_tags_any: [surface_wave]
          descriptor_thresholds:
            patch_count:
              gte: 2
```

The normalized mixed-fidelity plan records, for each root:

- the realized morphology class
- the recommended morphology class
- whether that recommendation implies promotion, demotion, or no change
- which policy rules matched
- the descriptor and manifest context used for that decision

The planner summary also includes a `policy_hook` block that lists all rule IDs
and the roots currently flagged for promotion or demotion review.

## Serialization Rules

Every per-root class record must remain deterministic and include at least:

- `root_id`
- `morphology_class`
- `source_project_role`
- `promotion_rank`

The normalized contract payload is serialized in three places:

- `surface_wave_execution_plan.hybrid_morphology`
- `execution_provenance.json -> model_execution.hybrid_morphology`
- `surface_wave_summary.json -> hybrid_morphology`

Shared comparison traces still live in `simulator_result_bundle.v1`. Class-
specific state or diagnostics may live under `extensions/`, but they may not
mutate the shared readout catalog, shared trace layout, or shared metric table.

## Scope Boundary

This note freezes the vocabulary for mixed morphology classes, approximation
limits, and promotion invariants. Later Milestone 11 tickets may implement more
of the runtime, but they should cite this note instead of inventing new class
names or changing what `point_neuron`, `skeleton_neuron`, or `surface_neuron`
mean inside one simulator run.
