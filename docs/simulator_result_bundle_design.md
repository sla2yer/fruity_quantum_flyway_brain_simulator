# Simulator Result Bundle Design

## Purpose

Milestone 9 needs one simulator-owned result contract before baseline, wave,
metrics, and UI work diverge. The versioned software contract for that bundle is
`simulator_result_bundle.v1`, implemented in
`flywire_wave.simulator_result_contract`.

The bundle is per manifest arm and per deterministic run-spec hash. The shared
comparison surface is fixed early so later `surface_wave`, UI, and validation
work do not silently invent new layouts or semantics.

## Canonical Layout

The library-owned default layout is:

- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/simulator_result_bundle.json`
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/state_summary.json`
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/readout_traces.npz`
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/metrics.csv`
- `data/processed/simulator_results/bundles/<experiment_id>/<arm_id>/<run_spec_hash>/extensions/<file_name>`

`run_spec_hash` is the stable replay key. It is derived from manifest identity,
arm identity, determinism, timebase, selected input assets, and the shared
readout catalog. Later tooling should discover bundles from metadata and the
contract path builder, not from ad hoc globbing.

## Baseline Decision

Milestone 1 already locked the fairness claim, so this note reuses that
language instead of reopening it.

- `P0` means the canonical point baseline: passive leaky linear non-spiking
  single-compartment neurons on the same selected circuit with the same shared
  downstream readout.
- `P1` means the stronger reduced baseline: an effective-point or reduced
  compartment realization that may add explicit synaptic integration current or
  deterministic delay structure, but still on the same connectome slice and the
  same shared readout.

For `simulator_result_bundle.v1`, the default software realizations are:

- `P0`: one scalar per-neuron state updated on one global fixed-step timebase.
- `P1`: `P0` plus extra internal integration state and optional deterministic
  delay buffers derived from the same coupling contract.

Neither baseline is allowed to add:

- extra connectome edges
- changed synapse signs
- arbitrary extra weights
- a decoder or shared readout unavailable to the other arm
- hand-fitted per-synapse delays granted only to the wave model

The wave model is allowed to add the Milestone 1 surface-specific content:

- surface-localized inputs on explicit morphology regions
- morphology-bound propagation state
- local timing structure from geodesic separation, spread, damping, and mild
  anisotropy
- wave-only diagnostics or state archives under `extensions/`

Wave-only additions must stay out of the shared comparison surface.

The extension directory may also hold deterministic handoff sidecars such as:

- structured execution logs
- provenance snapshots for local audit
- bundle-discovered UI comparison payloads

Those sidecars are still discovered from `simulator_result_bundle.json`, not by
guessing filenames directly.

## Shared Timebase

All comparison-ready outputs use one shared timebase:

- unit: milliseconds
- mode: `fixed_step_uniform`
- samples: `t_k = time_origin_ms + k * dt_ms`
- count rule: `sample_count * dt_ms == duration_ms`
- the shared readout archive, state summary, and metric table all refer to this
  same global time axis

Baseline and `surface_wave` runs may use different internal solvers later, but
they must resample or emit the shared outputs onto the same declared timebase
before claiming comparison readiness.

## Shared Readouts

`readout_catalog` is the comparison surface. It is ordered by `readout_id` and
records the stable IDs, scope, aggregation rule, units, and value semantics for
every shared trace. Invariants:

- the same `readout_id` means the same observable across all model modes
- units and aggregation semantics may not change per arm
- later UI and metrics code should key on `readout_id`, not display labels
- extra wave diagnostics belong in `extensions/`, not in the shared readout
  catalog

## Shared Payload Formats

The v1 payload contracts are:

- `state_summary.json`: long-table JSON rows with fields
  `state_id`, `scope`, `summary_stat`, `value`, `units`
- `readout_traces.npz`: arrays `time_ms`, `readout_ids`, and `values`, where
  `values` is indexed by shared time and shared readout order
- `metrics.csv`: comparison-ready rows with columns
  `metric_id`, `readout_id`, `scope`, `window_id`, `statistic`, `value`,
  `units`

These files are intentionally generic. New metrics and readouts may be added by
new rows or IDs, but not by changing the file names, array names, or required
column fields without a contract version bump.

## Reproducibility Metadata

Each bundle records:

- manifest identity and path
- arm identity, model mode, and baseline family
- explicit simulator contract version and design-note version
- deterministic seed and RNG family
- shared timebase
- ordered selected-asset references
- ordered shared readout catalog
- shared artifact inventory

This is the minimum metadata needed for deterministic replay and later audit.

## Invariants For Later Milestones

Milestones 10, 12, 13, and 14 must preserve these invariants:

- baseline and `surface_wave` bundles keep the same top-level directory shape
- the metadata file remains the discovery anchor for all other artifacts
- shared readout IDs, units, and timebase semantics stay aligned across arms
- comparison-ready metrics only refer to the shared readout catalog
- wave-only morphology/state details live under `extensions/` and do not
  mutate the shared artifact filenames or schemas
- UI code discovers artifacts from the metadata inventory, not hardcoded file
  guesses
- `scripts/run_simulation.py` is the public local execution path for
  manifest-driven baseline and `surface_wave` result bundles
- `scripts/14_milestone9_readiness.py` is the shipped integration-audit path:
  it reruns the local baseline workflow on fixture assets, checks comparison
  readiness, and writes `milestone_9_readiness.md` plus
  `milestone_9_readiness.json` under
  `config.paths.processed_simulator_results_dir/readiness/milestone_9/`
- `make milestone9-readiness` is the one-command entrypoint for that audit
- `scripts/16_milestone10_readiness.py` is the shipped Milestone 10 follow-on
  audit path: it reruns the local `surface_wave` workflow plus the shipped
  inspection sweep on fixture assets, checks bundle compatibility against a
  representative baseline arm, and writes `milestone_10_readiness.md` plus
  `milestone_10_readiness.json` under
  `config.paths.processed_simulator_results_dir/readiness/milestone_10/`
- `make milestone10-readiness` is the one-command entrypoint for that audit

If a future ticket needs a different shared layout, different shared payload
columns, or a different meaning for `P0`/`P1`, that is a new contract version,
not a silent edit to `simulator_result_bundle.v1`.
