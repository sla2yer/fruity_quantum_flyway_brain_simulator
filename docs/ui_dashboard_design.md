# UI Dashboard Design

## Purpose

Milestone 14 needs one library-owned dashboard contract before app-shell,
pane, and export work start diverging across static HTML reports, script-local
JSON, and later interactive code. The versioned software contract is
`dashboard_session.v1`, implemented in
`flywire_wave.dashboard_session_contract`.

The contract does not replace earlier bundle contracts. It composes with:

- `simulator_result_bundle.v1` for arm identity, selected assets, shared
  readout semantics, and the shared simulator timebase
- `experiment_analysis_bundle.v1` for experiment-level comparison cards,
  wave-only diagnostics, packaged UI handoff payloads, and bridge links to the
  static Milestone 12 report
- `validation_ladder.v1` for machine summaries, reviewer handoff state, and
  bridge links to the static Milestone 13 report

## Default Delivery Model

The repo default is `self_contained_static_app`.

That means one dashboard session is packaged under a deterministic local bundle
directory with:

- `dashboard_session.json` as the authoritative discovery anchor
- `dashboard_session_payload.json` as the reserved packaged session payload for
  the future app shell
- `session_state.json` as the exportable serialized interaction state
- `app/index.html` as the reserved offline application entrypoint

The intent is the same offline-review property used by earlier milestones: a
reviewer should be able to open the packaged dashboard from local disk without a
backend service.

## Offline Report Compatibility

Milestone 12 and Milestone 13 already ship self-contained offline reports. The
dashboard remains compatible with that approach by treating those reports as
bridge artifacts, not hidden dependencies or competing sources of truth.

The boundary is:

- the dashboard discovers the analysis and validation reports from their
  packaged bundle metadata
- the dashboard may link out to those reports or embed package-owned summary
  references
- the dashboard does not reclassify report HTML as the source of truth for
  metrics, overlays, or review status

That keeps the existing offline-report workflow valid while the Milestone 14
app shell matures.

## Five-Pane Taxonomy

The pane IDs are fixed in v1:

1. `scene`: stimulus or retinal context synchronized to the global replay
   cursor
2. `circuit`: active subset, connectivity context, and neuron selection
3. `morphology`: geometry-centric neuron inspection with activity overlays
4. `time_series`: shared readout traces, replay cursor, and paired comparison
   plots
5. `analysis`: experiment summaries, wave diagnostics, and reviewer-facing
   validation evidence

The IDs are deliberately short and stable. Later UI work may rename visible tab
labels, but it should not rename the contract IDs without a version change.

## Linked Interaction Model

The global interaction state in `dashboard_session.v1` is:

- `selected_arm_pair`
- `selected_neuron_id`
- `selected_readout_id`
- `active_overlay_id`
- `comparison_mode`
- `time_cursor`

Semantics:

- `selected_arm_pair` always records the baseline arm ID, the wave arm ID, and
  the currently foregrounded arm
- `selected_neuron_id` is a root identity and propagates from circuit
  inspection into morphology, time-series, and analysis views without UI-only
  aliases
- `selected_readout_id` is anchored to the simulator result bundle readout
  catalog and therefore stays comparable across panes
- `time_cursor` is serialized as both `time_ms` and `sample_index`; the
  simulator timebase remains the authoritative replay clock
- `active_overlay_id` is global state so export and replay tooling can recreate
  the visible review mode deterministically

## Comparison And Replay Semantics

The comparison modes are:

- `single_arm`
- `paired_baseline_vs_wave`
- `paired_delta`

`paired_baseline_vs_wave` is the default because Milestone 14 exists to make
the matched baseline-versus-wave story understandable without hiding the
baseline.

Replay semantics are constrained by upstream contracts:

- shared comparison uses the simulator-owned shared timebase
- shared readout traces stay anchored to shared readout IDs from
  `simulator_result_bundle.v1`
- paired delta views are only valid when the arm pair remains timebase
  compatible

## Overlay Boundary

The overlay categories are:

- `context`
- `shared_comparison`
- `wave_only_diagnostic`
- `validation_evidence`

These categories are the Milestone 14 boundary markers.

- `shared_comparison` overlays are fairness-critical and must stay on the
  shared simulator readout surface plus experiment-level shared summaries
- `wave_only_diagnostic` overlays may depend on wave-specific artifacts, but
  they must stay labeled as diagnostics instead of being presented as the fair
  comparison surface
- `validation_evidence` overlays are reviewer-oriented evidence and may not be
  silently merged into metrics or wave diagnostics

This contract therefore makes the scientific and reviewer boundaries visible in
the UI vocabulary itself instead of relying on later styling conventions.

## Export Boundary

The v1 export target IDs are:

- `session_state_json`
- `pane_snapshot_png`
- `metrics_json`
- `replay_frame_sequence`

`session_state_json` is the contract-owned serialization of exportable dashboard
state. It captures interaction state and chosen export target identity. It does
not duplicate upstream simulator, analysis, or validation bundle payloads.

The other export IDs reserve deterministic names for later Milestone 14 export
work without committing the repo to one rendering stack yet.

## Upstream Invariants

Milestone 14 code must preserve these invariants unless the dashboard contract
version changes:

- simulator bundle discovery must go through metadata-backed helpers rather
  than filename guessing
- the dashboard may package local state, but it may not mutate earlier bundle
  contracts
- shared timebase and shared readout semantics remain owned by
  `simulator_result_bundle.v1`
- experiment-level comparison and wave-diagnostic packaging remain owned by
  `experiment_analysis_bundle.v1`
- reviewer handoff status and machine finding boundaries remain owned by
  `validation_ladder.v1`

If a later ticket needs different pane IDs, different overlay-category meaning,
or a different exported-state meaning, that is a new contract version rather
than a silent edit to `dashboard_session.v1`.
