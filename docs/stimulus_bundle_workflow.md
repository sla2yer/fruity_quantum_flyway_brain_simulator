# Stimulus Bundle Workflow

Milestone 8A recording and replay is local-first and deterministic. The
workflow resolves one canonical stimulus spec, writes a reusable bundle under
the contract-owned bundle path, caches the canonical frame stack, and emits an
offline preview report inside the same bundle directory.

## Record a bundle

From config input:

```bash
python scripts/10_stimulus_bundle.py record --config config/local.yaml
```

From manifest input:

```bash
python scripts/10_stimulus_bundle.py record \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml
```

The recorder writes the canonical bundle at:

```text
data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/
```

Key artifacts:

- `stimulus_bundle.json`: authoritative descriptor metadata, timing,
  determinism, normalized parameters, and preview/report pointers
- `stimulus_frames.npz`: deterministic cached frame archive used for cheap
  replay
- `stimulus_preview.gif`: reserved optional animation slot in the contract
  metadata; the current local recorder marks it as skipped
- `preview/index.html`: static offline preview report with representative frames
- `preview/summary.json`: machine-readable preview summary
- `preview/frames/frame-<index>.svg`: deterministic preview images

The preview is intentionally static and local. It does not require notebooks,
GPU rendering, or any live FlyWire services.

## Replay a bundle

Replay directly from the recorded bundle:

```bash
python scripts/10_stimulus_bundle.py replay \
  --bundle-metadata data/processed/stimuli/bundles/<family>/<name>/<hash>/stimulus_bundle.json \
  --time-ms 0 \
  --time-ms 50 \
  --time-ms 250
```

Or replay by resolving the bundle path from the same config or manifest input:

```bash
python scripts/10_stimulus_bundle.py replay --config config/local.yaml --time-ms 50
```

Replay uses the cached frame archive when it exists and falls back to descriptor
regeneration only when the cache is missing. Either way, the recorded
`stimulus_bundle.json` remains the source of truth.

## Full readiness pass

Run the complete Milestone 8A integration verification workflow with:

```bash
make milestone8a-readiness
```

Or directly:

```bash
python scripts/11_milestone8a_readiness.py --config config/milestone_8a_verification.yaml
```

The readiness pass records and replays one representative example from every
required Milestone 8A family, validates the example manifest through the
canonical registry, checks deterministic cache-versus-regeneration replay, and
writes the readiness report under:

```text
data/processed/milestone_8a_verification/stimuli/readiness/milestone_8a/
```
