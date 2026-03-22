# Surface-Wave Sweep And Inspection Workflow

Milestone 10 is not finished when the solver merely runs one hand-picked
parameter bundle. Reviewers need one deterministic local workflow that can:

- expand one or more normalized `surface_wave` arm plans into a repeatable
  parameter sweep
- record the exact parameter bundle and seed context used for each run
- flag clearly unstable, degenerate, or numerically suspicious behavior
- show coupled wave trajectories and isolated single-neuron pulse behavior in a
  reviewable report without opening notebooks

`scripts/15_surface_wave_inspection.py` is that workflow.
For the full shipped Milestone 10 integration pass, run
`scripts/16_milestone10_readiness.py` or `make milestone10-readiness`; that
workflow writes `milestone_10_readiness.md` plus `milestone_10_readiness.json`
under
`config.paths.processed_simulator_results_dir/readiness/milestone_10/`.

## Inputs

The inspection workflow consumes only local Milestone 8 through 10 artifacts:

- a manifest that resolves at least one `surface_wave` arm
- the local geometry and coupling assets referenced by that arm plan
- a recorded local stimulus or retinal input bundle already compatible with the
  manifest timing
- an optional YAML or JSON sweep spec that declares explicit parameter sets,
  grid axes, explicit seeds, or representative-root limits

No live FlyWire access is required.

## Run It

Inspect the shipped example `surface_wave` arm with the example sweep spec:

```bash
python scripts/15_surface_wave_inspection.py \
  --config config/local.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --arm-id surface_wave_intact \
  --sweep-spec config/surface_wave_sweep.example.yaml
```

Use the Make target:

```bash
make wave-inspect \
  CONFIG=config/local.yaml \
  WAVE_INSPECT_ARGS="--arm-id surface_wave_intact --sweep-spec config/surface_wave_sweep.example.yaml"
```

Expand the manifest seed sweep before inspecting:

```bash
python scripts/15_surface_wave_inspection.py \
  --config config/local.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --use-manifest-seed-sweep \
  --sweep-spec config/surface_wave_sweep.example.yaml
```

## Sweep Spec

The optional sweep spec uses one versioned format:

```yaml
version: surface_wave_sweep.v1
representative_root_limit: 1
seed_values: [17, 23]

parameter_sets:
  - sweep_point_id: recovery_probe
    parameter_bundle:
      parameter_preset: m10_recovery_probe
      recovery:
        mode: activity_driven_first_order
        time_constant_ms: 14.0
        drive_gain: 0.3
        coupling_strength_per_ms2: 0.12

grid:
  sweep_id: damping_wave_speed
  base_parameter_bundle:
    parameter_preset: m10_grid
  axes:
    - key: damping.gamma_per_ms
      values: [0.12, 0.18, 0.28]
    - key: propagation.wave_speed_sq_scale
      values: [1.0, 1.25]
```

`parameter_sets` are preset-style explicit comparisons. `grid.axes` expands a
deterministic cartesian product on top of the normalized base
`surface_wave.parameter_bundle`.

If no sweep spec is provided, the workflow still runs one deterministic audit of
the arm's declared parameter bundle and seed.

## Output Layout

The output directory is deterministic for the exact arm set and normalized sweep
spec:

```text
config.paths.surface_wave_inspection_dir/experiment-<experiment-id>__arms-<arm-slug>__sweep-<hash>/
```

Example contents:

```text
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/summary.json
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/report.md
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/runs.csv
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/runs/<run-id>/summary.json
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/runs/<run-id>/report.md
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/runs/<run-id>/traces.npz
data/processed/surface_wave_inspection/experiment-milestone-1-demo__arms-surface-wave-intact__sweep-<hash>/runs/<run-id>/coupled_shared_trace.svg
```

That path stability is deliberate so later Milestone 12 or 13 comparisons can
reference the same run summaries and trace artifacts directly.

## What It Records

Each run records:

- arm reference, topology condition, seed, RNG family, and seed scope
- the full normalized parameter bundle plus the resulting `parameter_hash`
- coupled-run metrics such as shared-output peak, dynamic range, coupling event
  count, root-to-root coherence, and spatial contrast
- isolated single-neuron pulse metrics such as wavefront-speed estimate,
  energy-growth factor, and activation-peak growth
- deterministic `pass`, `warn`, or `fail` checks for finite values, runaway
  pulse amplification, missing wavefront detection, low driven dynamic range,
  low spatial contrast, and implausible peak-to-drive ratios
- compact SVG trace panels plus a deterministic `traces.npz` archive for later
  diffing or regression checks

## Review Guidance

`pass` means the sweep point executed cleanly and the default checks did not
find obvious numerical issues.

`warn` means the run completed but one or more heuristics suggest degenerate or
scientifically weak behavior, for example:

- a pulse probe failed to show a detectable front
- a driven coupled run stayed almost flat
- morphology-resolved spatial contrast collapsed
- coupling components existed but never produced events inside the run horizon

`fail` means the run was not trustworthy enough for downstream metrics work,
either because the execution itself raised an error or because the diagnostics
detected non-finite values or large runaway growth.
