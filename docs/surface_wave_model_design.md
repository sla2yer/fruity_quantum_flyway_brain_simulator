# Surface Wave Model Design

## Purpose

Milestone 10 needs one first-class wave-model contract before solver code,
planning, result serialization, and validation start encoding scientific choices
in incompatible places. The versioned software contract is
`surface_wave_model.v1`, implemented in `flywire_wave.surface_wave_contract`.

This note reuses three earlier milestone decisions instead of reopening them:

- Milestone 1 fixes the fairness claim. The wave mode may add morphology-bound
  intraneuronal state and nothing else that trivially explains a comparison gap.
- Milestone 6 fixes the operator assumptions. The spatial operator is symmetric,
  positive semidefinite after mass normalization, and any stable time-step rule
  must derive from the relevant operator spectrum rather than graph-degree
  heuristics.
- Milestone 9 fixes the shared comparison surface. Wave-only state details may
  add metadata or extension artifacts, but shared readouts still land on the
  same declared simulator timebase.

## Candidate Model Families

Milestone 10 named five viable families. The contract compares them at the
level needed to choose a default:

| Roadmap family | Strength | Reason not chosen as the v1 default |
| --- | --- | --- |
| `damped_wave_system` | Clean finite-speed propagation and direct use of Milestone 6 operators | Too narrow by itself: recovery, synaptic source semantics, and later readout coupling would still need a second informal layer |
| `diffusion_like_neural_field` | Simple and stable | Parabolic spread blurs finite-speed wavefront claims and makes Milestone 10 less diagnostic relative to baseline mode |
| `excitable_medium` | Natural refractory structure and traveling fronts | Too nonlinear and parameter-heavy for the first fairness-locked implementation |
| `reaction_diffusion_system` | Rich morphology-sensitive dynamics | Strong scientific flexibility, but too much freedom for the first contract and too much risk of fitting morphology-specific effects |
| `hybrid_field_readout_system` | Keeps one auditable surface field while naming optional recovery and readout mechanics explicitly | Chosen default |

## Chosen Family

The selected roadmap family is `hybrid_field_readout_system`.

`surface_wave_model.v1` realizes that family as one canonical software model
family:

- model family: `hybrid_damped_wave_recovery`
- default state layout: `surface_activation_velocity_optional_recovery`
- default readout state: `surface_activation`
- default solver family: `semi_implicit_velocity_split`

This is intentionally conservative. The core is a damped surface-wave system,
while recovery, nonlinearity, anisotropy, and branching are named extension
slots with explicit mode identifiers. Disabled or identity modes are part of the
contract, not informal omissions.

## State Variables

The canonical state catalog is:

- `surface_activation` (`u`, units `activation_au`): the primary
  morphology-bound activation field
- `surface_velocity` (`v`, units `activation_au_per_ms`): the time derivative
  of `surface_activation`
- `recovery_state` (`r`, units `unitless`): an optional local refractory budget
  that is disabled in the default v1 preset but already named in the contract

The shared comparison readout samples `surface_activation`. Wave-only auxiliary
state remains wave-only metadata unless a later contract revision explicitly
promotes it.

## Canonical Dynamics

The contract freezes the meaning of the terms even before the full solver lands.
In words, the v1 family evolves

- one primary surface field `u`
- one velocity-like auxiliary field `v`
- one optional recovery field `r`

with the intended continuous-time structure

`du/dt = v`

`dv/dt = -c_prop^2 A u - gamma v - k_rest u - k_rec r + I_syn + I_ext - N(u)`

`tau_rec dr/dt = G(u) - r` when recovery is enabled

where:

- `A` is the positive semidefinite mass-normalized surface operator from
  Milestone 6
- `c_prop^2` is the contract's `wave_speed_sq_scale`
- `gamma` is linear velocity damping
- `k_rest` is a weak restoring sink used to suppress unbounded DC drift
- `k_rec r` is the optional recovery-mediated sink
- `I_syn` is the connectome-constrained synaptic source term
- `N(u)` is an optional saturating nonlinearity

The default v1 preset keeps recovery disabled, nonlinearity disabled,
anisotropy isotropic, and branching disabled. Those choices are deliberate:
they keep the first solver auditable while still reserving stable mode names for
later Milestone 10 tickets.

## Synaptic Source Semantics

`surface_wave_model.v1` does not invent a new coupling contract. It reuses the
Milestone 7 sign, delay, aggregation, and fallback semantics and only fixes how
those sources enter the wave state:

- presynaptic source state: `surface_activation`
- postsynaptic injection target: `surface_velocity`
- source mode: `coupling_anchor_current`
- delay semantics: taken from `coupling_bundle.v1`
- sign semantics: taken from `coupling_bundle.v1`
- aggregation semantics: preserve sign and delay bins before summation
- landing support: the postsynaptic patch cloud or whichever contract-approved
  landing anchor the coupling bundle records

The wave model is not allowed to add hand-fitted per-synapse delays, extra
edges, or extra signs. Those remain Milestone 1 fairness violations.

## Optional Mechanics

### Recovery

Supported recovery modes:

- `disabled`
- `activity_driven_first_order`

The first enabled recovery mode is intentionally modest: it uses rectified local
activation as the drive and relaxes back to baseline with one time constant.
Later tickets may implement that mode, but they may not silently change what the
mode means.

### Nonlinearity

Supported nonlinearity modes:

- `none`
- `tanh_soft_clip`

The first nonlinear mode is a bounded amplitude soft clip. It is meant to limit
obviously unphysical amplitude blow-up, not to create a second hidden decoder.

### Anisotropy

Supported anisotropy modes:

- `isotropic`
- `operator_embedded`

`operator_embedded` must consume declared Milestone 6 anisotropy metadata or an
equivalent contract-approved operator realization. It may not change topology or
 invent new directions unavailable in the operator bundle.

### Branching

Supported branching modes:

- `disabled`
- `descriptor_scaled_damping`

The first branching extension is deliberately narrow. It may scale a local
damping-like modifier from existing geometry descriptors, but it may not become
a free per-neuron fitting channel.

## Stability-Relevant Assumptions

Later execution and validation tickets may rely on these assumptions:

- the realized surface operator is symmetric and positive semidefinite in the
  same inner product documented by Milestone 6
- damping, recovery, nonlinearity, and branching modifiers are dissipative or
  neutral in their default or identity modes
- the main time-step guard is spectral: any explicit or split-step stability
  bound is derived from the largest relevant eigenvalue of the realized operator
- identity anisotropy and disabled branching must reproduce the simpler isotropic
  no-branching dynamics within solver tolerance
- shared readouts must be emitted on the Milestone 9 simulator timebase even if
  the wave solver later uses internal substeps
- any source injection must preserve Milestone 7 sign, delay, and aggregation
  semantics

Recommended review ranges for the first local sweeps:

- `cfl_safety_factor`: `(0, 1]`, with `0.2` to `0.8` preferred
- `wave_speed_sq_scale`: positive and order-one relative to the realized
  operator spectrum
- `gamma_per_ms`: non-negative, usually small enough that propagation still
  remains visible
- `restoring_strength_per_ms2`: non-negative and weaker than the main spatial
  term
- recovery coupling and branching gains: non-negative and modest enough that
  they perturb, not dominate, the linear core

## Physically Meaningful Behavior Versus Numerical Artifact

Later tickets should classify results with the following distinction in mind.

Physically meaningful, contract-compatible behavior:

- finite-speed spread shaped by morphology and geodesic structure
- damped decay in the absence of persistent drive
- small but reproducible timing differences between intact and geometry-shuffled
  conditions
- optional anisotropy or branching effects that disappear when those modes are
  reset to identity
- stability conclusions that persist when the same run is repeated with the same
  seed and contract metadata

Numerical artifact warnings:

- growth from rest without source, declared instability, or enabled positive
  feedback
- checkerboard or mesh-local oscillations that track vertex layout rather than
  morphology
- strong dependence on update ordering, serialization order, or dictionary key
  order
- sign reversals or delay shifts caused only by the timestep choice
- effects that disappear when `dt` is reduced modestly or when identity
  anisotropy/branching modes are restored
- morphology effects that can only be reproduced by undocumented per-neuron
  tuning

## Invariants For Later Milestone 10 Tickets

Later Milestone 10 execution, sweep, metrics, and validation work must preserve
these invariants unless the contract version changes:

- `surface_wave` remains the simulator `model_mode`, and
  `hybrid_damped_wave_recovery` remains the default wave model family for
  `surface_wave_model.v1`
- state IDs, units, and the default readout state do not drift
- the meaning of the named modes
  `semi_implicit_velocity_split`, `activity_driven_first_order`,
  `tanh_soft_clip`, `operator_embedded`, and `descriptor_scaled_damping` stays
  fixed
- wave-only metadata remains discoverable from contract-owned metadata rather
  than solver-local constants or hardcoded filenames
- any future change that alters the family name, state catalog, parameter
  schema, or mode semantics is a new contract version, not a silent edit
