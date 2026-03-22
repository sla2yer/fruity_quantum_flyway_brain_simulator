# Milestone 7 Synapse Asset Contract And Coupling Topology Choice

This note freezes the Milestone 7 synapse and inter-neuron coupling handoff so
later simulator and UI work can target one explicit manifest contract, one
explicit bundle layout, and one explicit coupling interpretation.

## Contract summary

The processed manifest now carries `_coupling_contract_version:
coupling_bundle.v1` plus a per-root `coupling_bundle` block.

The top-level contract owns:

- the authoritative local synapse-registry path
- the versioned design-note reference and design-note version
- the supported coupling-topology families
- the supported fallback modes
- the default sign, delay, aggregation, and missing-geometry policies
- the canonical root-asset and edge-bundle directories

Each per-root `coupling_bundle` block owns:

- the same contract and design-note versions
- the realized topology family for that root-local handoff
- the fallback hierarchy the later mapping/assembly stages must follow
- the sign and delay representation rules
- the multi-synapse aggregation rule
- the discoverable local synapse registry pointer
- the incoming and outgoing anchor-map artifact paths
- the root-local coupling index path
- any explicit edge-level coupling bundle references that already exist

The canonical Milestone 7 layout is:

- `config.paths.processed_coupling_dir/synapse_registry.csv`
- `config.paths.processed_coupling_dir/roots/<root_id>_incoming_anchor_map.npz`
- `config.paths.processed_coupling_dir/roots/<root_id>_outgoing_anchor_map.npz`
- `config.paths.processed_coupling_dir/roots/<root_id>_coupling_index.json`
- `config.paths.processed_coupling_dir/edges/<pre_root_id>__to__<post_root_id>_coupling.npz`

Later tickets may add more sidecars, but those filenames and manifest fields are
the stable discovery surface.

## Candidate topology families

### Point-to-point

Definition:

- each synapse maps to one presynaptic readout anchor and one postsynaptic
  landing anchor
- the coupling artifact stays close to the raw synapse table

Advantages:

- highest localization fidelity
- easy to inspect against raw synapse rows
- minimal aggregation assumptions

Costs:

- expensive to evaluate for dense edges
- overly sensitive to mesh simplification or anchor jitter
- awkward when a later solver runs on patches instead of vertices
- does not naturally share one representation across surface, skeleton, and
  point-neuron fallbacks

### Patch-to-patch

Definition:

- each connectome edge becomes one or more direct transfers between coarse patch
  IDs
- synapse detail is collapsed early into patch-pair weights

Advantages:

- cheap to serialize and simulate
- easy to compare to coarse point-neuron baselines
- naturally aligned with reduced patch-state models

Costs:

- throws away within-patch landing structure too early
- strongly depends on the current patch partition
- makes later refinement back to finer resolution difficult
- mixes geometric localization and aggregation into one irreversible step

### Distributed patch-cloud

Definition:

- each synapse or aggregate contributes a sparse cloud over a small set of
  presynaptic readout anchors and postsynaptic landing anchors
- edge bundles may aggregate multiple synapses, but only after preserving the
  cloud structure that records where activity is sampled and where it lands

Advantages:

- preserves locality without forcing the simulator to operate on one raw
  synapse at a time
- works with surface patches now and still degrades cleanly to skeleton or
  point-neuron fallbacks
- keeps the handoff compatible with both coarse and finer later solvers
- separates geometry localization from sign, delay, and weight aggregation

Costs:

- more metadata than direct patch-to-patch coupling
- requires an explicit normalization convention inside each cloud
- needs careful testing so aggregation stays deterministic

## Decision

The default Milestone 7 coupling topology is `distributed_patch_cloud`.

Point-to-point and patch-to-patch remain recognized comparison families for
debugging, ablations, or future coarse baselines, but the authoritative
Milestone 7 handoff assumes that coupling is a sparse cloud-to-cloud transfer
derived from synapse-local anchors.

Why this is the default:

- it preserves enough geometry to justify morphology-resolved simulation
- it avoids binding the later solver to raw per-synapse loops
- it keeps one contract usable across mixed morphology classes
- it postpones irreversible aggregation until sign, delay, and fallback mode are
  already explicit

## Fallback hierarchy

Later mapping and coupling tickets must follow this hierarchy in order:

1. `surface_patch_cloud`
2. `skeleton_segment_cloud`
3. `point_neuron_lumped`

Meaning:

- `surface_patch_cloud`: default. Use surface/patch anchors from the Milestone 5
  and 6 geometry/operator bundles.
- `skeleton_segment_cloud`: fallback when surface geometry is missing or not
  trusted but a usable skeleton anchor representation exists.
- `point_neuron_lumped`: last resort when only a reduced single-state
  representation is available.

Current anchor realization notes for the shipped Milestone 7 mapper:

- surface mode localizes to deterministic coarse patch anchors while also
  recording the nearest supporting surface vertex and residuals
- skeleton mode currently localizes to the nearest raw SWC node so the fallback
  stays easy to audit before any later segment-parameter refinement
- point mode uses one deterministic root-local lumped anchor proxy per
  direction, derived from the mean available synapse query point for that root

Missing geometry is never a silent drop. Every mapped synapse or aggregated edge
must either:

- record the realized fallback mode explicitly, or
- record a structured blocked reason explaining why no supported fallback was
  possible

## Sign, delay, and aggregation rules

### Sign representation

Milestone 7 uses `categorical_sign_with_signed_weight`.

That means later bundles must carry both:

- an explicit semantic sign label such as excitatory, inhibitory, modulatory, or
  unknown
- a signed numeric coupling weight or gain term

Rules:

- unknown sign must stay explicit; it may not be silently coerced to positive
- opposite signs may not be merged into one net scalar without preserving the
  polarity split
- downstream consumers should read the categorical field first and treat the
  signed numeric field as the magnitude/polarity realization of that label

### Delay representation

Milestone 7 uses `nonnegative_delay_ms_per_synapse_or_delay_bin`.

Rules:

- delays are serialized in milliseconds
- delays must be finite and non-negative
- heterogeneous delays on one biological edge may be aggregated into bins, but
  not collapsed to one mean value unless the bundle explicitly declares that
  approximation

### Kernel family and normalization

Milestone 7 now ships one default kernel-family contract:

- kernel family: `separable_rank_one_cloud`
- source cloud normalization: `sum_to_one_per_component`
- target cloud normalization: `sum_to_one_per_component`

Meaning:

- each aggregate first samples a weighted presynaptic readout cloud
- the resulting event is then distributed over a weighted postsynaptic landing
  cloud
- the scalar coupling gain stays in the aggregate's signed weight total rather
  than being hidden inside the cloud weights

Supported explicit alternatives remain limited on purpose:

- `point_impulse` is reserved for point-like bundles where each aggregate has
  one source anchor and one target anchor
- `none` may be used for source or target cloud normalization when a later
  consumer wants raw anchor-weight totals instead of unit-sum clouds

### Delay model

Milestone 7 now ships one conservative default delay model:

- delay model: `constant_zero_ms`

and one explicit geometric alternative:

- `euclidean_anchor_distance_over_velocity`

The bundle always records the chosen delay model plus its parameters
(`base_delay_ms`, `velocity_distance_units_per_ms`, and `delay_bin_size_ms`) so
later baseline and wave simulators can share the same handoff even when they
interpret the transfer physics differently.

### Multi-synapse aggregation

Milestone 7 uses `sum_over_synapses_preserving_sign_and_delay_bins`.

Rules:

- aggregate only after grouping by source root, target root, topology family,
  realized fallback mode, sign, delay bin, and kernel family
- record at least the aggregated synapse count and total signed weight for each
  aggregate
- never cancel excitatory and inhibitory synapses into one unlabeled total
- never merge distinct delay bins into one scalar without an explicit contracted
  approximation field

## Invariants later milestones must preserve

Later simulator, mapping, and UI milestones should preserve these invariants
instead of silently changing them:

- the local synapse registry is the auditable row-level source for every anchor
  map and edge bundle
- root-local anchor maps and edge bundles refer to the same root IDs and the
  same design-note version recorded in the manifest
- `distributed_patch_cloud` remains the default authoritative family unless a
  later contract revision explicitly supersedes this one
- fallback mode is an explicit data field, not an inference from missing arrays
- a bundle that distributes one coupling event over multiple anchors must state
  its normalization convention explicitly in the bundle metadata
- sign and delay semantics survive aggregation; later consumers must not assume
  that one edge has only one polarity or one delay
- missing geometry or mapping failure remains visible as structured metadata, not
  as a silent omission from the coupling bundle

## Scope boundary

This note freezes the handoff contract, including the default kernel family,
delay-model metadata, and cloud-normalization rules. Later Milestone 7 tickets
may extend the supported family list or add stricter QA, but they should cite
this note instead of re-litigating the default topology family or the
fallback/sign/delay/aggregation semantics.
