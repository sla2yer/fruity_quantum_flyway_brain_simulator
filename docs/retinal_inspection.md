## Offline retinal inspection

Milestone 8B needs one repeatable way to inspect both the world-facing source
and the sampled fly-facing retinal representation before simulator or UI work
starts. `scripts/12_retinal_bundle.py inspect` is that workflow.

Run it from a cached bundle:

```bash
python scripts/12_retinal_bundle.py inspect \
  --bundle-metadata data/processed/retinal/bundles/.../retinal_input_bundle.json
```

Or resolve the same deterministic bundle from the source entrypoint:

```bash
python scripts/12_retinal_bundle.py inspect --config path/to/retinal_stimulus.yaml
python scripts/12_retinal_bundle.py inspect --scene path/to/scene.yaml
```

The report lives under:

```text
data/processed/retinal/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/inspection/
```

That path stability is deliberate so run logs, fixture tests, and later UI work
can refer to the same report directory without guessing filenames.

## What the report shows

- world-view preview frames reconstructed from the local source bundle or scene
- fly-view retinal frames rendered on the detector lattice
- detector coverage and lattice indexing in `coverage_layout.svg`
- timing, field-of-view, geometry, and sampling-kernel summaries
- compact `pass`, `warn`, or `fail` checks in both `index.html` and
  `summary.json`

## What reviewers should look for

- The world-view frame and the retinal lattice response should move together.
  If the source changes direction, contrast, or time phase, the sampled retinal
  view should change coherently rather than staying frozen or jumping between
  unrelated patterns.
- `coverage_layout.svg` should stay mostly green. Amber means support samples
  are clipped by the source field of view. Red means one or more ommatidia are
  fully uncovered and the bundle is not a trustworthy Milestone 8B handoff.
- Timing should be internally consistent. The source timeline, bundle frame
  count, and sample-hold frame times should agree.
- Detector values should stay finite and inside `[0.0, 1.0]`. Any NaN, Inf, or
  out-of-range detector is a bundle-integrity problem, not just a preview
  issue.

## Interpreting QA status

- `pass`: the bundle is locally inspectable and no obvious coverage, timing, or
  detector-value issue was found.
- `warn`: the bundle is structurally usable, but reviewers should look at the
  flagged item before simulator or UI work relies on it. The common case is
  clipped detector support without fully missing coverage.
- `fail`: the bundle has an obvious integrity or coverage problem. Treat it as a
  stop sign for Milestone 8B review until the source setup or sampler behavior
  is fixed.

## Full readiness pass

Run the shipped Milestone 8B integration audit with:

```bash
make milestone8b-readiness
```

Or directly:

```bash
python scripts/13_milestone8b_readiness.py --config config/milestone_8b_verification.yaml
```

That workflow exercises the full local world-to-retina surface on fixture
assets and writes `milestone_8b_readiness.md` plus
`milestone_8b_readiness.json` under:

```text
data/processed/milestone_8b_verification/retinal/readiness/milestone_8b/
```
