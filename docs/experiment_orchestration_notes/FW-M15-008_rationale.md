# FW-M15-008 Rationale

## Design Choices

This ticket intentionally publishes Milestone 15 readiness as a two-lane audit
instead of pretending the current orchestration layer is fully green.

The first lane is a representative manifest-driven suite probe that uses the
shipped suite CLI, real manifest resolution, deterministic work scheduling, and
actual simulator execution on local fixture assets. That lane is the right
place to verify:

- suite-manifest versus embedded-manifest resolution parity
- hashed suite-cell and work-item materialization paths
- seeded ablation realization and stimulus-bundle preflight
- deterministic simulation-stage execution through the shipped command surface

The second lane is a packaged-suite review probe that uses the shipped suite
aggregation and reporting CLIs on a deterministic packaged fixture. That lane
is the right place to verify:

- suite packaging and result-index discovery
- suite-level rollups and collapsed CSV exports
- deterministic SVG plot generation and static HTML review delivery

Splitting the readiness pass this way keeps the report honest. The repo can now
prove the parts that are truly working while explicitly holding the gate on the
two orchestration gaps that are still blocking a full manifest-driven
simulation-to-analysis-to-dashboard handoff.

Another deliberate choice is to reuse deterministic fixture builders that
already live in the regression suite instead of copying a second set of large
fixture factories into `src/`. The readiness module imports only the specific
helper functions it needs from the tests so the readiness gate and the unit
tests stay aligned on the same fixture semantics.

## Testing Strategy

The regression coverage for this ticket operates at three levels.

`tests/test_experiment_suite_execution.py` now covers the suite-seed
materialization fix all the way into manifest comparison-arm rewrites, so the
Milestone 12 null-test contract stays intact when suite seeds are expanded.

`tests/test_experiment_comparison_analysis.py` now covers the config-path
normalization fix that lets comparison analysis accept equivalent
materialized-at-different-path configs, which is necessary for per-work-item
suite input staging.

`tests/test_milestone15_readiness.py` exercises the full readiness pass and
asserts the intended result shape:

- manifest resolution passes
- representative shuffle simulation passes
- packaged aggregation and reporting pass deterministically
- the overall readiness gate remains `hold` until the two blocking follow-on
  tickets are closed

That test shape matters. The purpose of this ticket is not to fake a green
status; it is to make the current state reproducible, reviewable, and hard to
misinterpret.

## Simplifications

The readiness workflow stays conservative in a few places.

- It uses one small manifest-driven suite fixture rather than a broader sweep.
- It proves packaging, aggregation, and reporting on a deterministic packaged
  fixture rather than on fresh outputs from the blocked full-stage suite path.
- It records the remaining blockers as explicit follow-on tickets instead of
  widening this ticket into a multi-contract repair across Milestones 12 to 15.
- It reuses the existing suite CLIs and report directories instead of adding a
  second bespoke verification artifact format.

Those simplifications keep this ticket focused on orchestration confidence and
evidence capture.

## Future Expansion Points

The next meaningful expansion points are straightforward.

- Close `FW-M15-FOLLOW-001` so required morphology-demotion ablations can run
  against compatible coupling assets.
- Close `FW-M15-FOLLOW-002` so manifest-driven suites can hand off condition
  coverage cleanly into Milestone 12 analysis and the later validation and
  dashboard layers.
- Once those blockers are resolved, promote the readiness verdict from `hold`
  to `ready` and keep the same deterministic report path as the review anchor
  for Milestone 16 showcase work.
- If later scientific sweeps need denser coverage, extend the readiness fixture
  set by adding new manifest cases rather than replacing the current compact
  deterministic probe.
