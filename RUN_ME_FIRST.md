# RUN_ME_FIRST

This repo has two very different ways to "run":

1. the real FlyWire asset pipeline, which can need a token, network access, and a careful subset choice
2. local fixture-based verification workflows, which already run in this checkout

If your goal is simply "make it run and produce a result", start with the local verification workflows below.

## Fastest Path To A Result

From the repo root:

```bash
make bootstrap
make test
make milestone9-readiness
make milestone10-readiness
```

What these do:

- `make bootstrap` creates or updates `.venv` and installs the repo
- `make test` runs the local test suite
- `make milestone9-readiness` runs the baseline simulator workflow on local fixture assets
- `make milestone10-readiness` runs the surface-wave workflow plus offline inspection on local fixture assets

## Expected Outputs

After `make milestone9-readiness`:

- report: `data/processed/milestone_9_verification/simulator_results/readiness/milestone_9/milestone_9_readiness.md`
- JSON summary: `data/processed/milestone_9_verification/simulator_results/readiness/milestone_9/milestone_9_readiness.json`
- simulator bundles: `data/processed/milestone_9_verification/simulator_results/bundles/`

After `make milestone10-readiness`:

- report: `data/processed/milestone_10_verification/simulator_results/readiness/milestone_10/milestone_10_readiness.md`
- JSON summary: `data/processed/milestone_10_verification/simulator_results/readiness/milestone_10/milestone_10_readiness.json`
- simulator bundles: `data/processed/milestone_10_verification/simulator_results/bundles/`
- wave inspection reports: `data/processed/milestone_10_verification/surface_wave_inspection/`

Notes:

- `milestone9` is the cleanest first success path
- `milestone10` still runs successfully, but the readiness verdict may be `review` instead of `ready`

## Direct Simulator Commands

If you want to run one manifest arm directly after the readiness fixtures exist, these commands work:

Baseline:

```bash
./.venv/bin/python scripts/run_simulation.py \
  --config data/processed/milestone_9_verification/simulator_results/readiness/milestone_9/generated_fixture/simulation_fixture_config.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --model-mode baseline \
  --arm-id baseline_p1_intact
```

Surface wave:

```bash
./.venv/bin/python scripts/run_simulation.py \
  --config data/processed/milestone_10_verification/simulator_results/readiness/milestone_10/generated_fixture/simulation_fixture_config.yaml \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --model-mode surface_wave \
  --arm-id surface_wave_intact
```

## Visualize The Current Produced Results

This command builds an offline HTML viewer comparing the current Milestone 10
baseline companion bundle against the current Milestone 10 surface-wave bundle:

```bash
./.venv/bin/python scripts/17_visualize_simulator_results.py \
  --bundle-metadata data/processed/milestone_10_verification/simulator_results/bundles/milestone_1_demo_motion_patch/baseline_p1_intact/6b5f32ebf39c9b4d36aa13e5d6e85269bdec05e07b23645794641f67c58f8a82/simulator_result_bundle.json \
  --bundle-metadata data/processed/milestone_10_verification/simulator_results/bundles/milestone_1_demo_motion_patch/surface_wave_intact/58d565b23c7354a545d8222c03b44b99925869b8e03ecdd144e80ebe33ba5f3c/simulator_result_bundle.json
```

The report writes under:

```text
data/processed/milestone_10_verification/simulator_results/visualizations/
```

## What Not To Start With

Avoid these as your first run:

- `make all CONFIG=config/local.yaml`
- `make verify CONFIG=config/local.yaml`
- `make meshes CONFIG=config/local.yaml`
- `make preview CONFIG=config/local.yaml`

Why:

- `verify` and `meshes` need FlyWire auth and network access
- the current `config/local.yaml` selection is large, so it is not a light first pass
- the local processed graph directory is only partially materialized for the default config, so some preview and QA paths can be blocked

## If You Want The Real Pipeline Later

The intended main pipeline is:

```bash
make registry CONFIG=config/local.yaml
make select CONFIG=config/local.yaml
make meshes CONFIG=config/local.yaml
make assets CONFIG=config/local.yaml
```

That path is useful once you are ready to work with real FlyWire-backed inputs rather than the local verification fixtures.
