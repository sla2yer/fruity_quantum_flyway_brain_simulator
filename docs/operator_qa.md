# Offline Operator QA Workflow

Milestone 6 is not finished when bundles merely serialize. Before Milestone 10
starts, the team needs one offline workflow that can:

- initialize a localized pulse on the fine surface
- check that a lightweight smoke evolution behaves stably enough for pre-engine work
- compare fine and coarse behavior quantitatively
- show the result on the mesh and patch decomposition without opening raw arrays

`scripts/06_operator_qa.py` is that workflow.

## Inputs

The report reads only local bundle artifacts that were already built by
`scripts/03_build_wave_assets.py`:

- `config.paths.processed_graph_dir/<root_id>_fine_operator.npz`
- `config.paths.processed_graph_dir/<root_id>_coarse_operator.npz`
- `config.paths.processed_graph_dir/<root_id>_transfer_operators.npz`
- `config.paths.processed_graph_dir/<root_id>_patch_graph.npz`
- `config.paths.processed_graph_dir/<root_id>_operator_metadata.json`
- optional descriptor / geometry-QA sidecars for extra context

No FlyWire token or network access is required.

## Run It

Inspect one or more explicit root IDs:

```bash
python scripts/06_operator_qa.py --config config/local.yaml --root-id 101 --root-id 102
```

Inspect the active selected subset:

```bash
python scripts/06_operator_qa.py --config config/local.yaml --limit 4
```

Equivalent Make target:

```bash
make operator-qa CONFIG=config/local.yaml
```

Run the full Milestone 6 readiness pass against the tracked offline verification
bundle:

```bash
make milestone6-readiness
```

That target uses `config/milestone_6_verification.yaml`, which points at the
cached local mesh bundle under `data/interim/meshes_raw/` and writes isolated
outputs under `data/processed/milestone_6_verification/`.

Optional smoke depth override:

```bash
python scripts/06_operator_qa.py --config config/local.yaml --root-id 101 --pulse-steps 12
```

## Output Layout

The output directory is deterministic for the exact sorted root-id set:

```text
config.paths.operator_qa_dir/root-ids-<sorted-root-ids>/
```

Example:

```text
data/processed/operator_qa/root-ids-101/index.html
data/processed/operator_qa/root-ids-101/report.md
data/processed/operator_qa/root-ids-101/summary.json
data/processed/operator_qa/root-ids-101/101_details.json
data/processed/operator_qa/root-ids-101/101_pulse_initial.svg
data/processed/operator_qa/root-ids-101/101_boundary_mask.svg
data/processed/operator_qa/root-ids-101/101_patch_decomposition.svg
data/processed/operator_qa/root-ids-101/101_fine_pulse_final.svg
data/processed/operator_qa/root-ids-101/101_coarse_pulse_final.svg
data/processed/operator_qa/root-ids-101/101_coarse_reconstruction.svg
data/processed/operator_qa/root-ids-101/101_reconstruction_error.svg
```

The Milestone 6 readiness pass writes two more deterministic artifacts into the
same directory:

```text
.../milestone_6_readiness.md
.../milestone_6_readiness.json
```

That path stability is deliberate so the report can be referenced from run logs,
ticket notes, or review comments.

## What It Checks

The current report combines bundle-level structural checks with one
stability-oriented pulse smoke loop.

Structural checks:

- fine and coarse operator symmetry residuals
- fine and coarse constant-field nullspace residuals on the stiffness matrices
- non-positive mass counts on fine and coarse mass diagonals
- coarse-versus-fine Galerkin and application residuals already serialized in
  the transfer bundle

Pulse smoke checks:

- deterministic localized pulse initialization from the fine bundle’s stored
  geodesic neighborhood data
- explicit diffusion-style stepping with `dt` derived from the estimated
  largest eigenvalue of the symmetric mass-normalized operator
- mass drift across the smoke evolution
- Dirichlet-energy monotonicity under the chosen time step
- final coarse-vs-restricted-fine residual
- final fine-vs-prolongated-coarse residual

The report also renders:

- pulse initialization on the fine surface
- boundary-mask inspection
- patch decomposition
- fine pulse after the smoke loop
- coarse pulse after the smoke loop
- prolongated coarse reconstruction on the fine surface
- absolute reconstruction error on the fine surface

## Gate Semantics

Every metric gets `pass`, `warn`, or `fail`. The aggregate report also emits a
Milestone 10 gate:

- `go`: no warnings or failures
- `review`: no blocking failures, but at least one warning or non-blocking failure
- `hold`: at least one blocking failure

Use that gate this way:

- `go`: acceptable baseline for downstream engine integration and solver work
- `review`: engine work can continue only if a reviewer signs off on the
  degraded metrics and the visual overlays still look scientifically plausible
- `hold`: do not treat the operator bundle as an engine baseline; rebuild or
  debug the bundle first

## Reviewer Checklist

Reviewers should look for:

- pulse initialization staying localized around one seed region rather than
  starting already smeared across the whole surface
- boundary masks matching the intended surface topology instead of lighting up
  unexpected interior structure
- fine smoke evolution diffusing smoothly without explosive growth or obvious
  checkerboard artifacts
- coarse pulse support following the same broad region as the restricted fine
  result
- prolongated coarse reconstruction tracking the fine field instead of
  collapsing onto a few dominant patches
- reconstruction error concentrating near coarse partition limits rather than
  covering the whole neuron

When the report fails:

- if symmetry, nullspace, or non-positive-mass checks fail, stop Milestone 10
  work and inspect the operator build itself
- if pulse mass or energy checks fail, treat the bundle as numerically unstable
  for pre-engine use
- if only coarse-vs-fine comparison checks warn or fail, inspect the patch
  decomposition and transfer quality before deciding whether the bundle is still
  usable for exploratory work

## Threshold Overrides

Optional overrides live under `meshing.operator_qa_thresholds` in the config and
follow the same shape as the geometry-QA thresholds:

```yaml
meshing:
  operator_qa_thresholds:
    pulse_final_fine_vs_prolongated_coarse_residual_relative:
      warn: 0.25
      fail: 0.60
      blocking: false
```

Tighten thresholds when using the workflow as a release gate. Relax them only
when the report is being used for exploratory analysis and the deviation is
documented explicitly.
