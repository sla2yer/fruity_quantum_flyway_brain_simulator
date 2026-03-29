# FW-M14-006 Rationale

## Design Choices

This ticket introduces one library-owned replay and comparison layer instead of
letting the browser shell infer time alignment, comparison validity, or trace
semantics on its own.

`flywire_wave.dashboard_replay` now normalizes:

- the canonical replay model derived from the paired simulator bundle timebase
- shared readout traces used for fair baseline-versus-wave comparison
- selection-linked wave-only diagnostic traces kept separate from the fair
  comparison surface
- deterministic replay-state export data written into `session_state.json`

That keeps Milestone 14 aligned with the earlier contracts:

- shared comparison still comes from `simulator_result_bundle.v1` readout
  traces and shared timebase metadata
- wave-only diagnostics still come from wave-arm mixed-fidelity outputs
- the dashboard shell consumes packaged JSON and does not rescan local files or
  `.npz` archives in JavaScript

The time-series pane is intentionally split into two visibly different bands:

- `shared_comparison` for baseline, wave, and paired-delta views on the shared
  timebase
- `wave_only_diagnostic` for root-linked wave diagnostics that are useful for
  interpretation but not the fairness boundary

The shell keeps one global replay cursor in the toolbar, but the new replay
model also serializes timebase identity, playback cadence, comparison-mode
availability, and the normalized replay-state snapshot. That gives later export
and showcase work one stable replay contract to depend on.

## Testing Strategy

Coverage is split across planner/package tests, replay-focused unit tests, and
the existing shell packaging test.

`tests/test_dashboard_replay.py` verifies:

- fixture sessions expose a canonical replay model plus distinct
  shared-comparison and wave-only diagnostic trace payloads
- the time-series view model normalizes paired baseline-versus-wave, paired
  delta, and single-arm modes on the same shared cursor
- replay-state serialization is deterministic across repeated fixture planning
- invalid paired-comparison requests fail clearly when the replay model no
  longer exposes a compatible shared timebase

`tests/test_dashboard_session_planning.py` now checks that the planned payload
and exported dashboard state both carry the replay model and replay-state
snapshot.

`tests/test_dashboard_app_shell.py` checks the packaged bootstrap embeds the
replay model, serialized replay-state metadata, and the shared trace catalog
needed by the offline shell.

Together these tests act as the requested integration-style coverage: they load
the representative fixture dashboard session, drive replay/comparison state
through the shared Python view model, and assert synchronized time-series
metadata plus fairness-boundary labeling.

## Simplifications

The first replay scrubber is still an offline static HTML control surface. It
does not persist browser-side edits back to disk or expose a richer export UI
yet.

The time-series pane uses lightweight SVG charts generated in the shell instead
of a plotting dependency. That keeps `file://` review simple and deterministic
for the packaged fixtures.

Wave-only diagnostics are currently reduced to one root-linked aggregate trace
per selected neuron. The underlying morphology pane still carries richer
per-element activity, but the time-series pane stays focused on readable review
state rather than maximal detail.

## Future Expansion Points

Likely follow-up work:

- add richer replay serialization and export actions on top of the new replay
  state payload
- support more than one comparison-ready readout chart at once when later UI
  layout work can absorb denser plots
- expose root-level diagnostic families beyond the current aggregated wave trace
  when later bundles package stronger wave-local observables
- reuse the replay model in showcase and experiment-orchestration surfaces so
  the dashboard remains the canonical source of replay semantics
