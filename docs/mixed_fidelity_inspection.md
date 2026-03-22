# Mixed-Fidelity Inspection Workflow

Milestone 11 is not finished when surface, skeleton, and point classes merely
run in one arm. Reviewers need one offline workflow that can answer:

- which roots were assigned to which fidelity class
- what the policy hook recommended promoting or demoting
- how a lower-fidelity surrogate behaves against a declared higher-fidelity
  reference on the same local fixture
- whether the observed deviations are acceptable, review-level, or blocking
- which roots should be promoted before later readout or validation work relies
  on them

`scripts/18_mixed_fidelity_inspection.py` is that workflow.

## Inputs

The workflow consumes only local artifacts:

- one manifest with at least one `surface_wave` arm
- the local geometry, operator, skeleton, and coupling assets already referenced
  by that arm
- a recorded local stimulus bundle compatible with the manifest timing
- the normalized mixed-fidelity policy inside `simulation.mixed_fidelity`

No live FlyWire access is required.

## Run It

Inspect the shipped `surface_wave` arm and let the resolved policy choose which
surrogate roots to compare against a higher-fidelity reference:

```bash
python scripts/18_mixed_fidelity_inspection.py \
  --config config/local.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --arm-id surface_wave_intact
```

Provide explicit reference roots when you want to override the policy target:

```bash
python scripts/18_mixed_fidelity_inspection.py \
  --config config/local.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --arm-id surface_wave_intact \
  --reference-root 303:surface_neuron
```

Equivalent Make target:

```bash
make mixed-fidelity-inspect \
  CONFIG=config/local.yaml \
  MIXED_FIDELITY_INSPECT_ARGS="--arm-id surface_wave_intact --reference-root 303:surface_neuron"
```

The shipped Milestone 11 integration gate wraps this inspection workflow
together with mixed execution and bundle visualization:

```bash
make milestone11-readiness
```

The underlying readiness entrypoint is `scripts/19_milestone11_readiness.py`.
It reruns the same fixture through `scripts/run_simulation.py`,
`scripts/17_visualize_simulator_results.py`, and
`scripts/18_mixed_fidelity_inspection.py` before publishing the report.

The readiness-generated visualization lives at
`config.paths.processed_simulator_results_dir/readiness/milestone_11/visualization/index.html`.
That viewer is fully static, so no local server is required. Open the file
directly in your browser if you want to inspect the mixed bundle after the
readiness pass.

That command writes the generated fixture config and manifest under
`config.paths.processed_simulator_results_dir/readiness/milestone_11/generated_fixture/`
so the exact same local mixed-fidelity arm can be rerun directly through
`scripts/run_simulation.py`, `scripts/17_visualize_simulator_results.py`, and
`scripts/18_mixed_fidelity_inspection.py`.

When `--reference-root` is omitted, the workflow first uses any policy-driven
promotion recommendation. If the policy does not nominate a higher-fidelity
reference, it falls back to the next higher class in the promotion order.

## Output Layout

The default output directory is deterministic for the exact arm, normalized
reference-root set, and normalized thresholds:

```text
config.paths.mixed_fidelity_inspection_dir/experiment-<experiment-id>__arm-<arm-id>__inspection-<hash>/
```

Example contents:

```text
data/processed/mixed_fidelity_inspection/experiment-milestone-1-demo-motion-patch__arm-surface-wave-intact__inspection-<hash>/summary.json
data/processed/mixed_fidelity_inspection/experiment-milestone-1-demo-motion-patch__arm-surface-wave-intact__inspection-<hash>/report.md
data/processed/mixed_fidelity_inspection/experiment-milestone-1-demo-motion-patch__arm-surface-wave-intact__inspection-<hash>/roots.csv
data/processed/mixed_fidelity_inspection/experiment-milestone-1-demo-motion-patch__arm-surface-wave-intact__inspection-<hash>/details/root_303__point_neuron__to__surface_neuron.json
```

## What It Records

The top-level summary records:

- the resolved mixed-fidelity plan excerpt, including per-root fidelity choice
  and the normalized policy hook
- the base mixed-fidelity run used as the surrogate under review
- one reference run per inspected root, built by rewriting only that root's
  fidelity assignment in a deterministic manifest sidecar
- per-root surrogate-versus-reference metrics:
  - root mean-trace MAE
  - root peak-amplitude error
  - root final-state error
  - root peak-timing delta
  - shared-output trace MAE
  - shared-output peak error
- per-check `pass`, `review`, `blocking`, or `blocked` outcomes
- the final promotion target list inferred from those deviations

## Review Guidance

- `pass`: the lower-fidelity surrogate stayed close enough to the declared
  reference on the current fixture
- `review`: the surrogate diverged enough that a human should decide whether the
  approximation is still scientifically defensible
- `blocking`: the surrogate materially changed a blocking metric, usually one of
  the shared-output comparisons
- `blocked`: the workflow could not build or compare the reference variant from
  local artifacts, so the root remains unresolved

The workflow is intentionally an approximation audit, not a final biological
validation ladder. Its job is to keep Milestone 11 honest and produce a stable
review artifact for later milestones.
