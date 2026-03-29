# FW-M13-006 Rationale

## Purpose

Milestone 12 already packaged experiment-level comparison bundles, but it still
left a gap at the task-validation layer. This ticket adds the missing
task-sanity execution surface in `flywire_wave.validation_task`.

The new suite answers three concrete questions against packaged
experiment-analysis outputs:

- are task-level outputs stable across the declared seed inventory
- are baseline-versus-wave or intact-versus-ablated differences reproducible
- do those differences survive declared perturbation or noise sweeps

## Design Choices

- One reusable suite consumes Milestone 12 analysis artifacts directly.
  `run_task_validation_suite` accepts either a loaded experiment-analysis
  summary or a packaged `experiment_analysis_bundle`, then writes the standard
  Milestone 13 validation bundle artifacts.
- The manifest workflow stays bundle-oriented instead of re-running task
  kernels.
  `execute_task_validation_workflow` resolves the normalized Milestone 13 plan,
  reuses the packaged experiment-analysis bundle as the base evidence surface,
  and accepts explicit perturbation analysis bundles for external sweeps such as
  noise robustness.
- Fairness boundaries stay visible in the review artifact.
  The suite records shared-comparison inventory, task-decoder inventory, and
  wave-only diagnostic inventory separately, then checks that shared and
  wave-only sections remain visibly distinct in the UI handoff payload.
- Coverage failures are explicit rather than permissive.
  Missing seed rows, missing perturbation variants, missing task-decoder
  inventories, incompatible rollup keys, and absent null-test records all raise
  clear errors instead of silently degrading the validation result.
- Built-in versus external perturbations stay distinct.
  Geometry-variant checks are satisfied from the base experiment-analysis
  summary because those comparisons already live inside the Milestone 12 group
  catalog, while declared noise or sign/delay sweeps require external packaged
  experiment-analysis bundles keyed by suite and variant identifiers.

## Local Workflow

The repo now exposes a manifest-oriented command path:

```bash
make task-validate \
  CONFIG=path/to/config.yaml \
  MANIFEST=path/to/manifest.yaml \
  TASK_VALIDATE_ARGS="\
    --analysis-bundle-metadata path/to/experiment_analysis_bundle.json \
    --perturbation-analysis-bundle noise_robustness:seed_11__noise_0p0:path/to/noise_0/experiment_analysis_bundle.json \
    --perturbation-analysis-bundle noise_robustness:seed_11__noise_0p1:path/to/noise_01/experiment_analysis_bundle.json"
```

That target runs `scripts/26_task_validation.py`, resolves the task-only
validation plan, and writes deterministic validation artifacts under the
standard Milestone 13 bundle layout.

For direct fixture use, the canonical library entrypoints are:

```python
from flywire_wave.validation_task import (
    execute_task_validation_workflow,
    run_task_validation_suite,
)
```

## Testing Strategy

Coverage lands in a single deterministic multi-arm fixture suite:

- `tests/test_validation_task.py` materializes the existing Milestone 12
  comparison fixture, augments the readout-analysis plan with task-decoder
  metrics, computes a real experiment summary with multiple arms and two seeds,
  and packages that result into fixture-owned analysis bundles.
- The same test file exercises the end-to-end task workflow with clean and
  modestly perturbed noise bundles, then asserts deterministic pass findings for
  seed stability, perturbation coverage, and robustness reporting.
- Additional regression cases assert that the workflow fails clearly for missing
  perturbation variants, missing task seed coverage, and missing task-decoder
  inventories, and that contradictory perturbation outcomes produce blocking
  validator status.

This keeps the suite fully local and appropriate for the normal `make test`
loop.

## Simplifications

- The first version evaluates only the task-level signals already exposed by the
  packaged experiment-analysis summary.
  It does not introduce a second task-analysis kernel or a new downstream
  decoder boundary.
- Thresholds are local defaults embedded in the validator, not yet criteria
  payloads loaded from a future registry.
- Perturbation bundles are caller-supplied.
  The workflow validates that declared sweep coverage is present, but it does
  not synthesize the perturbation experiment-analysis bundles on its own.

## Future Expansion

Likely follow-on work:

- promote current thresholds into criteria-profile loaders while keeping the
  finding schema stable
- attach richer reviewer sidecars that summarize contradictory outcomes by arm,
  metric, and perturbation family
- add explicit support for more perturbation families once Milestone 13 starts
  packaging additional experiment-analysis bundles beyond geometry and noise
- expand effect-consistency reporting with stronger cross-variant ranking or
  trend summaries when reviewers need more than pass, review, blocked, or
  blocking labels
