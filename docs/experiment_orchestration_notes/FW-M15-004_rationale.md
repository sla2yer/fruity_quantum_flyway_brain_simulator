# FW-M15-004 Rationale

## Design Choices

This ticket adds one library-owned transform module,
`flywire_wave.experiment_ablation_transforms`, instead of scattering Milestone
15 ablation semantics across suite planning, manifest overrides, and runtime
executors.

The core design choice is that an ablation first becomes a normalized
realization record before it becomes a mutated arm payload or runtime plan.
That realization record carries:

- a stable transform identity
- the source suite-cell lineage reference
- the perturbed input surface
- validated prerequisite notes
- either one explicit perturbation seed or a per-simulation-seed perturbation
  policy

That keeps the causal change visible in software. Two runs only mean the same
thing if they carry the same realization payload.

I kept the ablation-specific seed separate from the simulator seed on purpose.
The stochastic families, such as synapse-location shuffles and morphology
shuffles, now record a distinct perturbation seed path so reviewers can tell
whether an observed difference came from the simulator RNG or from the
ablation itself.

The transform layer is integrated at two boundaries:

- suite planning and execution now carry `ablation_realization` on the suite
  cell and inject it into the materialized config for that work item
- simulation planning reads the injected realization, mutates the targeted
  surface-wave arms deterministically, and threads the realized ablation
  provenance into the resulting arm plan and model-configuration asset hash

That keeps the suite layer as the owner of ablation provenance while letting
the existing Milestone 9 through 12 planning surfaces remain the owner of
simulation-plan structure.

The concrete family semantics are intentionally explicit:

- `no_waves` demotes all targeted roots to `point_neuron`
- `waves_only_selected_cell_classes` keeps wave morphology only for the
  requested normalized cell-class IDs and demotes the rest to `point_neuron`
- `no_lateral_coupling` removes the selected inter-root coupling bundles
- `shuffle_synapse_locations` keeps the same coupling bundles but applies a
  deterministic postsynaptic patch permutation
- `shuffle_morphology` permutes compatible surface-operator bundles across
  targeted roots
- `coarsen_geometry` demotes eligible surface roots to `skeleton_neuron`
- `altered_sign_assumptions` and `altered_delay_assumptions` perturb coupling
  components at runtime through one bounded first-pass mode family

## Testing Strategy

The regression coverage is fixture-driven and focuses on the transform
semantics rather than on large end-to-end simulation runs.

The new focused test module:

- resolves deterministic fixture simulation plans from the existing local test
  geometry and coupling assets
- realizes every roadmap-required ablation family from a stable base plan
- asserts stable provenance fields for every realized family
- checks the concrete transform effect for each family, such as fidelity
  demotion, coupling-edge removal, patch permutations, operator-asset swaps,
  skeleton coarsening, and sign or delay perturbations
- exercises clear failure cases for missing cell-class assignments, absent
  inter-root coupling edges, missing raw-skeleton variants, and unsupported
  sign or delay requests
- verifies the suite integration path by confirming that a seeded ablation
  suite cell carries `ablation_realization` and that execution materializes it
  into the per-work-item config

I also reran the nearby planning and orchestration test modules to make sure
the new transform surface did not break deterministic suite planning,
materialized-config generation, or the existing simulation-plan fixtures.

## Simplifications

The first version is deliberately narrower than the full scientific design
space.

- `shuffle_morphology` is currently limited to deterministic permutation of
  compatible surface-operator assets. It does not yet synthesize new meshes,
  new skeletons, or cross-resolution remeshing.
- `coarsen_geometry` currently means surface-to-skeleton demotion when every
  targeted surface root exposes a ready raw SWC skeleton. It does not yet
  support multiple coarse geometry tiers.
- `shuffle_synapse_locations` currently permutes postsynaptic coarse-patch
  landing sites. It does not yet expose richer perturbation families such as
  distance-constrained or class-conditioned synapse remapping.
- `altered_sign_assumptions` is intentionally bounded to the
  `sign_inversion_probe`.
- `altered_delay_assumptions` is intentionally bounded to the
  `zero_delay_probe` and the fixed `delay_scale_half_probe`.
- `no_lateral_coupling` removes inter-root coupling edges only. It does not
  redefine intra-root coupling semantics.

These limits are documented in the transform policies and enforced by explicit
errors rather than by silent fallback.

## Future Expansion Points

The clearest follow-on paths are:

- add richer sign and delay perturbation catalogs once Grant decides which
  scientific probes should become canonical
- add broader morphology perturbation families that can swap or resample
  geometry across non-identical patch counts and mixed fidelity classes
- extend coarsening beyond one surface-to-skeleton step into multiple geometry
  ladders when later milestones ship those assets
- expose more structured analysis helpers that can group or diff results by
  canonical ablation transform identity without reparsing ad hoc tags
- revisit seed-sweep rematerialization for additional direct simulation-plan
  entrypoints if future workflows need seed-indexed ablations outside the
  current suite-cell orchestration path
