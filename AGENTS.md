# AGENTS.md

## Purpose

This repo preprocesses FlyWire metadata and meshes into wave-ready assets for a later simulator. It is not the final simulator itself.

## Fast Start

1. Run `make test`.
2. Use `make validate-manifest` for Milestone 1 spec changes.
3. Use `make registry`, `make select`, `make meshes`, and `make assets` for pipeline work.
4. Prefer the repo `Makefile`; it auto-selects `.venv/bin/python` when that virtualenv exists.

## Repo Map

- `src/flywire_wave/`: core library code for config loading, registry building, selection, manifest validation, and mesh processing
- `scripts/`: thin CLI wrappers around the library
- `tests/`: local unit tests that do not require FlyWire network access
- `config/`: example runtime config plus the Milestone 1 design lock
- `manifests/`: example experiment manifests
- `schemas/`: manifest schema files
- `docs/milestones.md`: roadmap and milestone planning
- `docs/pipeline_notes.md`: concise pipeline/output contract notes
- `data/raw/codex/`: manually downloaded Codex CSV inputs
- `data/interim/`, `data/processed/`: generated outputs, ignored by git
- `flywire_codex/`: upstream Codex git submodule; avoid editing unless the task explicitly calls for it

## Safe Validation Loop

- `make test`: runs the local unit tests
- `make validate-manifest`: validates the example Milestone 1 manifest
- `make smoke`: runs both of the above

## Pipeline Order

1. `scripts/build_registry.py`: normalize Codex exports into canonical neuron/connectivity registries
2. `scripts/01_select_subset.py`: derive the active root-id subset
3. `scripts/02_fetch_meshes.py`: fetch raw meshes and optional skeletons from FlyWire
4. `scripts/03_build_wave_assets.py`: simplify meshes and build graph/Laplacian assets

## Guardrails

- `scripts/00_verify_access.py` and `scripts/02_fetch_meshes.py` need `.env` with `FLYWIRE_TOKEN`; tests do not.
- Treat `data/raw/codex/` files as source snapshots and `data/interim/` plus `data/processed/` as reproducible outputs.
- Keep docs aligned with the current consolidated milestone doc at `docs/milestones.md`; older milestone sub-doc paths are no longer authoritative.
- The current config and tests assume the public FAFB datastack and materialization version `783`.
