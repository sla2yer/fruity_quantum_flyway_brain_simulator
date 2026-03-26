# Readout Analysis Design

## Purpose

Milestone 12 needs one library-owned analysis contract before metric code,
readiness reports, inspection helpers, and later UI payloads drift apart. The
versioned software contract is `readout_analysis.v1`, implemented in
`flywire_wave.readout_analysis_contract`.

This note does not add a new downstream biological decoder boundary. It freezes
how the repo names and separates:

- fair shared-comparison metrics
- fair derived task metrics
- wave-only diagnostics
- experiment-level comparison outputs

## Locked Boundary

Milestone 12 stays aligned with the earlier locked milestones.

- The readout stop point remains `T4a/T5a` axon terminals in lobula plate layer
  1.
- `simulator_result_bundle.v1` remains the upstream comparison surface.
- The same shared `readout_id` must still mean the same observable across
  baseline, `surface_wave`, and mixed-fidelity runs.
- Milestone 12 does not promote the fairness boundary downstream into LPi,
  tangential-cell, or custom wave-only decoders.

Meaning:

- shared-comparison metrics must be computable from the shared readout catalog,
  shared timebase, and arm-invariant task context
- wave-only patch, phase, or inspection extensions may support diagnostics, but
  those diagnostics stay outside the fairness-critical comparison surface

## Taxonomy

`readout_analysis.v1` freezes four layers.

### Shared readout metrics

These are fairness-critical and shared between baseline and wave runs.

- `null_direction_suppression_index`
- `response_latency_to_peak_ms`
- `direction_selectivity_index`
- `on_off_selectivity_index`

Rules:

- they consume the shared readout catalog and shared trace archive from
  `simulator_result_bundle.v1`
- they may also consume declared condition labels or analysis-window metadata
- they may not consume wave-only patch traces, phase maps, or internal solver
  state

### Derived task metrics

These remain fair, but they are one step more interpretive than the raw shared
readout metrics.

- `motion_vector_heading_deg`
- `motion_vector_speed_deg_per_s`
- `optic_flow_heading_deg`
- `optic_flow_speed_deg_per_s`

Rules:

- they consume shared readout evidence plus declared task context such as
  stimulus-direction labels and retinotopic geometry metadata
- they remain task-level summaries of the locked T4a/T5a terminal readout
- for the current local-patch vertical slice they are small-field estimates,
  not whole-field behavior claims

### Wave-only diagnostics

These are explicitly allowed to depend on wave extensions and must stay labeled
as diagnostics.

- `synchrony_coherence_index`
- `phase_gradient_mean_rad_per_patch`
- `phase_gradient_dispersion_rad_per_patch`
- `wavefront_speed_patch_per_ms`
- `wavefront_curvature_inv_patch`
- `patch_activation_entropy_bits`

Rules:

- they may consume `surface_wave` patch-trace, summary, or future phase-map
  extensions
- they are useful for interpretation, sanity checks, and UI inspection
- they are not substitute shared observables for baseline-versus-wave fairness

### Experiment-level comparison outputs

Milestone 12 also freezes the first UI-facing output identities.

- `null_direction_suppression_comparison`
- `latency_shift_comparison`
- `motion_decoder_summary`
- `wave_diagnostic_summary`
- `milestone_1_decision_panel`
- `analysis_ui_payload`

The rule is simple: outputs may package both fair shared metrics and wave-only
diagnostics only when those scopes stay visibly separated.

## Metric Interpretation

### Null-direction suppression

`null_direction_suppression_index` is the primary Milestone 1 observable. It is
the preferred-versus-null comparison on the shared terminal readout surface,
not on a wave-only internal state.

### Latency

`response_latency_to_peak_ms` is the main mechanistic companion observable. It
is measured on the shared readout timebase relative to the declared analysis
window, and it supports the primary claim rather than replacing it.

### Direction selectivity

`direction_selectivity_index` is the normalized preferred-minus-null directional
contrast on the shared terminal readout surface.

### ON/OFF selectivity

`on_off_selectivity_index` is the normalized ON-versus-OFF polarity contrast on
matched shared readout conditions.

### Motion-vector and optic-flow estimates

The motion and optic-flow families are allowed task decoders only if they are
built from shared readout evidence plus arm-invariant task context. They may be
more interpretive than the shared metrics, but they are not allowed to become
wave-only cheats.

### Wave-structure diagnostics

Synchrony, coherence, phase gradients, wavefront speed, wavefront curvature,
and patch activation entropy describe morphology-resolved wave structure. They
help explain *how* a wave run is behaving, but they do not change the meaning
of the shared readout IDs or the Milestone 1 evidence ladder.

## First Task Families

Milestone 12 v1 freezes these task families:

- `milestone_1_shared_effects`: the fairness-critical shared observables tied
  to the Milestone 1 evidence ladder
- `motion_decoder_estimates`: motion-vector and optic-flow summaries derived
  from shared readouts plus declared task context
- `wave_structure_diagnostics`: wave-only morphology-aware diagnostics
- `experiment_comparison_outputs`: packaged comparison views and UI payloads

## Null-Test Hooks

The first null-test hooks are:

- `geometry_shuffle_collapse`
- `stronger_baseline_survival`
- `seed_stability`
- `polarity_label_swap`
- `direction_label_swap`
- `wave_artifact_presence_guard`

Intent:

- geometry shuffle should shrink or collapse a shared-readout effect
- the stronger reduced baseline `P1` should not explain away the effect
- seed variation should not flip the qualitative interpretation
- label swaps should flip or collapse polarity and directional scores
- absent wave artifacts should produce explicit unavailable diagnostics rather
  than silently fabricated shared metrics

## UI-Facing Outputs

Milestone 12 must support local review surfaces for:

- null-direction suppression comparison
- latency shift comparison
- motion-decoder summary
- wave-diagnostic summary
- the Milestone 1 decision panel
- one packaged `analysis_ui_payload` that keeps shared-comparison content and
  wave-only diagnostics visibly separated

## Invariants For Later Milestone 12 Tickets

Later Milestone 12 tickets may add kernels, planning, packaging, and reports,
but they must preserve these invariants:

- `readout_analysis.v1` remains the canonical source of metric IDs, task-family
  IDs, null-test IDs, and experiment-output IDs
- experiment-level packaging may add `experiment_analysis_bundle.v1` metadata
  and exports, but it must reuse the same Milestone 12 metric and output IDs
- shared-comparison metrics stay computable from the shared result-bundle
  surface
- wave-only diagnostics stay outside the shared fairness boundary
- task decoders remain bounded by the locked T4a/T5a terminal readout plus
  arm-invariant task context
- UI payloads must not blur together fairness-critical shared metrics and
  wave-only diagnostics

If a later ticket needs different metric semantics, a different dependency
surface, or a different experiment-output meaning, that is a new contract
version rather than a silent rename inside `readout_analysis.v1`.
