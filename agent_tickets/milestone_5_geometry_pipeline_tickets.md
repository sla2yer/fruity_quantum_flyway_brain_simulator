# Milestone 5 Geometry Pipeline Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M5-001 - Define a versioned geometry asset contract for multiresolution morphology bundles
- Status: open
- Priority: high
- Source: Milestone 5 roadmap 2026-03-21
- Area: geometry pipeline / manifests / provenance

### Problem
The current geometry handoff contract is too narrow for Milestone 5. The repo documents a simplified mesh, one graph archive, and one metadata file, but the roadmap requires a fuller per-neuron bundle that can account for raw mesh, simplified mesh, skeleton, surface graph, patch graph, derived descriptors, and the versioned preprocessing choices that produced them. Without a centralized asset contract, later milestones will end up binding themselves to ad hoc filenames and partially duplicated script logic.

### Requested Change
Introduce a single versioned geometry asset contract in library code and apply it across the fetch and build steps. Define the canonical per-neuron output layout, manifest fields, naming rules, and build metadata needed for multiresolution morphology assets. The contract should make it obvious which raw and processed files belong to a neuron, which config values shaped them, and which bundle version downstream code is reading.

### Acceptance Criteria
- Geometry bundle path construction is centralized in library code instead of being reimplemented in multiple scripts.
- The processed manifest records, per root ID, the canonical locations and statuses for raw mesh, raw skeleton, simplified mesh, surface graph, patch graph, descriptor sidecar, and QA sidecar.
- The manifest includes an explicit asset-contract version plus the dataset, materialization version, and meshing config snapshot used to build the bundle.
- Existing pipeline scripts write outputs that conform to the new contract, or a documented compatibility shim keeps current consumers working while the repo migrates.
- Regression coverage verifies manifest structure, version fields, and deterministic path generation for fixture builds.

### Verification
- `make test`
- A focused unit or integration-style test that builds a fixture geometry bundle and asserts the manifest contents and output layout

### Notes
This is the foundation ticket for the rest of the Milestone 5 work and should land first. Keep the contract implementation small and boring: one code path for path building, one code path for manifest writing, and no script-specific naming rules.

## FW-M5-002 - Make raw geometry ingestion cache-aware, resumable, and provenance-rich
- Status: open
- Priority: high
- Source: Milestone 5 roadmap 2026-03-21
- Area: geometry ingestion / caching / CLI behavior

### Problem
`scripts/02_fetch_meshes.py` always behaves like a one-shot downloader. It does not clearly separate cache hits from fresh downloads, it does not record structured per-neuron fetch provenance, and optional skeleton failures collapse to `None` without leaving behind enough information for a later rebuild or audit. That makes large subset fetches brittle and expensive to rerun.

### Requested Change
Upgrade raw geometry ingestion so it can skip valid cached assets, refetch stale or corrupt ones, and record a structured fetch status per root ID. Treat mesh fetches as required, skeleton fetches as optional-but-audited, and capture enough provenance to explain what happened during a run without reading console logs. The implementation should support resumable ingestion and make repeated executions cheap by default.

### Acceptance Criteria
- Re-running the fetch step against already downloaded valid assets reports cache hits and avoids unnecessary re-downloads by default.
- The fetch layer can explicitly refetch assets when requested through config or CLI controls.
- Per-root raw-asset provenance records whether mesh and skeleton fetches were fetched, reused from cache, skipped, or failed, along with enough context to diagnose the reason.
- Zero-byte, malformed, or otherwise invalid cached files are detected and do not silently count as healthy cache hits.
- Regression coverage exercises cache-hit, forced-refetch, and optional-skeleton-failure scenarios using local stubs rather than live FlyWire access.

### Verification
- `make test`
- A targeted unit test suite for `scripts/02_fetch_meshes.py` or the underlying library functions that covers cache reuse and corrupted-cache recovery

### Notes
Assume `FW-M5-001` is already in place so raw-asset provenance has a stable home in the manifest or bundle layout. Be careful not to turn skeleton failures into hard failures unless the config explicitly says skeletons are required.

## FW-M5-003 - Build explicit surface-graph and patch-graph artifacts for the multiresolution morphology bundle
- Status: open
- Priority: high
- Source: Milestone 5 roadmap 2026-03-21
- Area: processed geometry / graph construction

### Problem
`scripts/03_build_wave_assets.py` currently emits a simplified mesh and one combined graph archive with an example patch mask. That is a good scaffold, but it is not yet a true multiresolution morphology bundle. Milestone 5 calls for explicit surface and patch graph assets, stable mappings between resolutions, and a clearer representation boundary between fine surface data and coarse simulation-ready patches.

### Requested Change
Refactor the processed-asset builder so it writes explicit surface-graph and patch-graph artifacts with well-defined metadata and mapping arrays. Preserve the simplified mesh output, but make the coarse representation first-class rather than an implicit mask tucked into a single archive. The result should be a bundle that a later simulator can consume without reverse-engineering the build step.

### Acceptance Criteria
- The processed output contains a first-class surface graph artifact and a first-class patch graph artifact instead of only one opaque combined archive.
- Patch generation is deterministic for the same mesh and config, and the bundle records the mapping from fine surface vertices to coarse patches.
- The processed manifest ties each multiresolution artifact back to the raw mesh and skeleton inputs used to build it.
- The implementation keeps graph construction in library code and leaves the script as a thin orchestration layer.
- Regression coverage validates artifact filenames, key arrays, graph dimensions, and deterministic behavior on fixture meshes.

### Verification
- `make test`
- A focused fixture-driven test that builds assets for a stub mesh and asserts the surface graph, patch graph, and mapping outputs

### Notes
Assume `FW-M5-001` has landed so the artifact layout is already settled. Keep formats easy to inspect and serialize; avoid burying unrelated structures in one monolithic file if separate artifacts make later operator work clearer.

## FW-M5-004 - Add derived geometry descriptors and simplification QA with documented error budgets
- Status: open
- Priority: medium
- Source: Milestone 5 roadmap 2026-03-21
- Area: geometry QA / scientific guardrails / docs

### Problem
The repo currently has no quantitative answer to a basic Milestone 5 question: did simplification and patchification preserve the geometry features that matter for later wave propagation experiments? Without descriptor sidecars and QA thresholds, the pipeline can produce smaller assets but cannot tell us whether they are still faithful enough for downstream numerical work.

### Requested Change
Add a descriptor and QA stage that computes wave-relevant geometry summaries for raw, simplified, and coarse representations, then compares them against configurable error budgets. Capture both the implemented metrics and the reasoning behind them in a short markdown design note so later milestones have a documented baseline for what counts as an acceptable morphology approximation.

### Acceptance Criteria
- The processed bundle includes a descriptor sidecar with geometry summaries such as counts, component structure, size/extent metrics, and coarse-representation occupancy metrics, plus skeleton summaries when a skeleton is available.
- The build step emits a QA sidecar that compares raw versus simplified versus coarse representations and records pass, warn, or fail outcomes against configurable thresholds.
- Default QA thresholds and descriptor rationale are documented in a dedicated markdown note aimed at later Milestone 6 and Milestone 11 consumers.
- The build summary surfaces QA warnings clearly and fails only for conditions that should block downstream use.
- Regression coverage exercises both a healthy fixture build and a threshold-violating case.

### Verification
- `make test`
- A focused test that asserts descriptor output fields and QA threshold behavior for fixture geometry

### Notes
Keep the first descriptor set pragmatic rather than exhaustive. Favor metrics that are cheap to compute locally and easy to explain in docs, then leave room for future expansion if Milestone 6 needs more physically specific fidelity checks.

## FW-M5-005 - Ship offline geometry preview tooling for raw, simplified, skeleton, and patchified assets
- Status: open
- Priority: medium
- Source: Milestone 5 roadmap 2026-03-21
- Area: developer tooling / visualization / docs

### Problem
Milestone 5 is not done until raw, simplified, and patchified geometry can be visualized together, but the repo currently offers no standard preview workflow for that. A developer can inspect files manually, yet there is no repeatable tool that turns a built bundle into a quick sanity-check report for a chosen subset of neurons.

### Requested Change
Add offline preview tooling that consumes already-built local geometry bundles and generates an inspection-friendly report for one or more root IDs. The tool can be a script, notebook, or small library-backed report generator, but it should standardize how the team compares raw mesh, simplified mesh, skeleton, surface graph, and patch graph views without requiring live FlyWire access.

### Acceptance Criteria
- A documented local preview workflow exists for one or more root IDs using only files produced by the pipeline.
- The preview output renders or summarizes raw mesh, simplified mesh, skeleton availability, surface graph structure, and patch graph structure in one place.
- Preview artifacts are written to a deterministic output location so they can be linked from run logs or shared during reviews.
- README or pipeline docs explain how to generate the preview and what a reviewer should look for.
- At least one smoke-style automated test covers preview generation from fixture assets.

### Verification
- `make test`
- A smoke-style test or scripted fixture run that generates preview output from local stub assets

### Notes
Assume the earlier Milestone 5 tickets have already landed. Favor a lightweight offline artifact such as HTML, Markdown plus images, or another review-friendly format that does not require interactive infrastructure to be useful.
