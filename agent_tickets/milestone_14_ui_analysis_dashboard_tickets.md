# Milestone 14 UI And Analysis Dashboard Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

Implementation rule for every Milestone 14 ticket:
- Before closing the ticket, add a companion rationale note at `docs/ui_dashboard_notes/<ticket-id>_rationale.md`.
- That note must explain the rationale behind all material design choices, the testing strategy used, and explicitly call out what is intentionally simplified in the first version plus the clearest expansion paths for later work.

## FW-M14-001 - Freeze a versioned dashboard-session contract, pane taxonomy, and interaction design note
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: contracts / docs / dashboard architecture

### Problem
Milestones 8 through 13 already give the repo deterministic local artifacts for scene inputs, selected circuits, simulator bundles, experiment analysis, and validation ladders, but there is still no first-class software contract for the Milestone 14 dashboard that is supposed to make all of that understandable. Right now the project has separate offline reports and UI-facing payload fragments, yet there is no canonical definition of what one dashboard session is, which pane IDs exist, how a selected neuron or selected timepoint should propagate across panes, how baseline-versus-wave comparison mode should be represented, which overlays are fairness-critical versus wave-only, or how exportable dashboard state should be serialized. Without one decisive contract and design note, later UI work will drift across static reports, ad hoc HTML widgets, and script-local JSON, and the team will end up with a demo surface that looks polished while quietly violating upstream bundle semantics.

### Requested Change
Define a library-owned Milestone 14 dashboard-session contract and publish a concise design note that locks the pane taxonomy and interaction model. The contract should name the five dashboard panes, stable pane IDs, global interaction state such as selected arm pair, selected neuron, selected readout, active overlay, and time cursor, plus the artifact references and export target identities required to build a deterministic local dashboard session from existing simulator, analysis, and validation bundles. The design note should choose the default UI delivery model for this repo, explain how the dashboard stays compatible with the existing self-contained offline report approach, and specify the boundary between shared-comparison content, wave-only diagnostics, and reviewer-oriented validation evidence.

### Acceptance Criteria
- There is one canonical dashboard-session contract in library code with explicit identifiers for pane IDs, global interaction state, overlay categories, comparison modes, and export target identities.
- The contract records stable discovery hooks for simulator result bundles, experiment analysis bundles, validation ladder bundles, and any Milestone 14-specific packaged assets without mutating the earlier bundle contracts.
- A dedicated markdown design note explains the chosen UI delivery model, the five-pane taxonomy, linked-selection semantics, replay and comparison semantics, export boundaries, and which upstream contract invariants the dashboard must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 14 dashboard contract sits alongside the existing simulator, analysis, and validation bundle contracts.
- Regression coverage verifies deterministic contract serialization, stable pane and overlay discovery, and normalization of representative fixture dashboard-session metadata.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit test that builds fixture dashboard-session metadata and asserts deterministic serialization plus stable pane and overlay discovery

### Notes
This ticket should land first and give the rest of Milestone 14 a stable vocabulary. Reuse the existing `simulator_result_bundle.v1`, `experiment_analysis_bundle.v1`, and Milestone 13 validation packaging language where those contracts already answer artifact-discovery or fairness-boundary questions. Do not attempt to create a git commit as part of this ticket.

## FW-M14-002 - Build manifest- and bundle-driven dashboard planning plus deterministic session packaging
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: planning / packaging / dashboard assembly

### Problem
Even with a locked dashboard contract, Milestone 14 will stall immediately if there is no canonical way to assemble one dashboard session from local artifacts. The repo already knows how to discover simulator bundles, analysis bundles, and validation bundles independently, but there is still no shared planner that can turn a manifest, an experiment ID, or a concrete bundle set into one normalized dashboard session with stable ordering, explicit pane inputs, deterministic output paths, and clear failure handling when a required artifact is missing. Without that assembly layer, every later visualization script will reimplement artifact discovery, special-case one fixture layout, and silently disagree about which baseline arm, wave arm, analysis bundle, or validation package a dashboard is actually showing.

### Requested Change
Add the planning and packaging layer for Milestone 14 dashboard sessions. Extend the library-owned planning surface so local config plus a manifest, experiment reference, or explicit bundle references resolve into one deterministic dashboard session plan; then package that plan into the dashboard-session bundle layout defined by `FW-M14-001`. The normalized plan should identify the scene source, circuit subset, morphology assets, trace sources, analysis artifacts, validation artifacts, overlay availability, and deterministic session output locations needed by the five panes. Fail clearly when inputs are missing, incompatible, or scientifically misleading, such as mismatched shared timebases, incomparable arm pairs, absent geometry assets for requested neurons, or analysis bundles that do not correspond to the selected simulator runs.

### Acceptance Criteria
- There is one canonical API that resolves local config plus manifest, experiment, or explicit bundle inputs into a normalized dashboard session plan with stable ordering and explicit defaults.
- The normalized plan records scene, circuit, morphology, time-series, analysis, and validation artifact references together with the selected comparison arms, active overlays, and deterministic output locations required for Milestone 14 workflows.
- The packaging layer writes one deterministic dashboard-session bundle or equivalent packaged session surface that later UI code can consume without reparsing raw repo directories.
- Planning fails clearly when required local artifacts are missing or incompatible, including mismatched experiment identity, incompatible shared timebases, missing wave-only diagnostics for a requested overlay, or insufficient morphology metadata for requested selections.
- Existing simulator, analysis, and validation bundle discovery helpers remain reusable inputs to the dashboard planner rather than being bypassed by a separate filename-guessing implementation.
- Regression coverage validates deterministic normalization, representative fixture session assembly, override precedence, and clear failure handling for unsupported dashboard requests.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit or integration-style test that resolves representative fixture simulator, analysis, and validation artifacts into one normalized Milestone 14 dashboard session plan and asserts deterministic ordering plus clear error handling

### Notes
Assume `FW-M14-001` and the Milestone 9 through Milestone 13 packaging layers are already in place. Favor one planning surface that future export, replay, and showcase code can reuse rather than a pile of script-local directory scans. Do not attempt to create a git commit as part of this ticket.

## FW-M14-003 - Ship the dashboard application shell, static asset pipeline, and linked multi-pane state model
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: application shell / state management / UX foundation

### Problem
The repo already has deterministic static reports for several earlier milestones, but Milestone 14 needs a true interactive dashboard rather than one more isolated report page. There is currently no application shell that can load a packaged dashboard session, no shared client-side or view-model state for linked selection and replay, no five-pane layout, no deterministic way to open the dashboard from local artifacts, and no decision on how to keep the first implementation reviewable without requiring backend services. Without a real shell and state model, later pane work will either duplicate logic across HTML reports or hardcode fragile assumptions about how selection, playback, and comparison state should be synchronized.

### Requested Change
Implement the first working Milestone 14 dashboard shell around the packaged dashboard-session surface. Build the static asset or bundled-view pipeline required by the chosen UI delivery model, create the five-pane layout skeleton, and introduce one canonical linked state model that owns selected arms, selected neurons, selected readouts, active overlays, playback state, and time cursor updates across the whole application. Provide at least one documented local command or script that can generate the dashboard artifacts and open the result from local disk, while preserving deterministic packaged outputs suitable for repo fixtures and readiness audits.

### Acceptance Criteria
- A documented local command or script can build and open a Milestone 14 dashboard from packaged local artifacts without requiring live FlyWire access.
- The dashboard shell renders the five top-level panes declared by the contract and supports linked global state for selection, overlay mode, comparison mode, and replay cursor updates.
- The chosen app-shell implementation remains compatible with deterministic local packaging, meaning the review artifact can be regenerated from the same packaged session inputs with stable asset identities.
- The initial layout behaves cleanly on desktop and remains legible on smaller laptop-sized widths, even if some panes collapse into tabs or stacks in the first version.
- The implementation includes a deterministic smoke fixture or regression harness that verifies packaged app generation, global-state bootstrapping, and stable loading of representative fixture dashboard sessions.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style dashboard-build test that generates a fixture Milestone 14 dashboard artifact, loads a representative session payload, and asserts stable output paths plus expected pane and state metadata

### Notes
Assume `FW-M14-001` and `FW-M14-002` are already in place. The goal here is the durable shell and shared state model, not the full scientific richness of every pane. Do not attempt to create a git commit as part of this ticket.

## FW-M14-004 - Implement the scene pane and circuit pane with synchronized subset, connectivity, and scene-context inspection
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: scene visualization / circuit context / linked inspection

### Problem
Milestone 14 explicitly says the dashboard should show what the fly sees and how the active subset sits in connectivity context, yet the repo currently exposes those ideas only through upstream bundles and separate reports. There is no unified pane that can replay the relevant scene or retinal view in sync with simulator time, and there is no linked circuit pane that lets a reviewer inspect the active subset, its key connectivity neighborhood, and neuron metadata while staying anchored to the same experiment story. Without these panes, the dashboard will fail at the most basic narrative requirement: a reviewer still will not understand what input drove the run or which circuit elements are being highlighted.

### Requested Change
Implement the Milestone 14 scene pane and circuit pane on top of the packaged dashboard-session inputs. The scene pane should present the canonical scene or fly-view representation that matches the selected dashboard session and time cursor, while the circuit pane should present the active root subset together with the most relevant connectivity context, neuron metadata, and selection affordances needed to drive the rest of the dashboard. Keep the two panes synchronized with the global selection and replay state, and make sure they consume the existing stimulus, retinal, selection, and coupling-related contracts rather than introducing a competing data model.

### Acceptance Criteria
- The scene pane renders a synchronized view of the selected input context for the current session and time cursor using packaged local artifacts rather than ad hoc screenshots.
- The circuit pane exposes the active subset and connectivity context in a form that supports clicking or otherwise selecting neurons and immediately updating the rest of the dashboard state.
- Selection and hover behavior in the scene or circuit pane propagates through the shared dashboard state so later morphology, trace, and analysis panes can respond consistently.
- Circuit metadata shown in the pane remains grounded in the existing selection, registry, and coupling contracts rather than inventing a separate UI-only naming scheme.
- The implementation includes deterministic fixture coverage for scene-frame discovery, circuit-context normalization, linked-selection payloads, and clear handling of cases where certain context layers are unavailable.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that builds a fixture dashboard session with scene and circuit inputs and asserts deterministic pane payloads plus linked neuron-selection behavior

### Notes
Assume `FW-M14-001` through `FW-M14-003` and the Milestone 8A, 8B, and 7 bundle contracts are already in place. Favor a presentation that helps a reviewer orient quickly, even if the first circuit pane uses a disciplined hybrid of graph, table, and metadata cards rather than a maximal graph-visualization feature set. Do not attempt to create a git commit as part of this ticket.

## FW-M14-005 - Implement the morphology pane with mixed-fidelity geometry rendering, activity overlays, and neuron inspection
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: morphology visualization / mixed fidelity / overlay rendering

### Problem
The roadmap says users should be able to click neurons and inspect them, but the repo still has no single morphology-focused viewer that can render the selected cells with activity overlays while respecting Milestone 11 mixed-fidelity classes. Surface meshes, skeleton approximations, and point fallbacks already exist as upstream concepts, yet there is no unified Milestone 14 pane that can show whichever representation is available, highlight selected neurons, and clearly distinguish between fairness-critical shared readout overlays and wave-only morphology-aware diagnostics. Without this pane, the dashboard cannot actually explain how structure and activity relate.

### Requested Change
Implement the Milestone 14 morphology pane using the packaged dashboard-session inputs and the existing mixed-fidelity morphology abstractions. The pane should render whichever geometry class is available for a selected neuron set, support linked camera focus and neuron inspection, and expose activity overlays that can switch among shared comparison signals, wave-only diagnostics, and other contract-approved overlay families while keeping those scopes visibly separated. Include sensible empty-state and unavailable-state handling so the dashboard remains truthful when a requested overlay or morphology fidelity is not present in the current session.

### Acceptance Criteria
- The morphology pane can render representative fixture neurons across the supported fidelity classes, including at least one surface-resolved case and one reduced-fidelity fallback case.
- A user can select neurons from elsewhere in the dashboard and inspect the corresponding morphology with synchronized highlighting, metadata, and camera focus updates.
- Overlay rendering supports at least the baseline shared-comparison case and one wave-only diagnostic case while labeling unavailable or inapplicable overlays clearly.
- The pane consumes existing geometry, morphology-class, and simulator-state exports through contract-backed discovery helpers rather than hardcoded file lookups.
- Regression coverage includes deterministic fixture tests for geometry discovery, fidelity fallback behavior, overlay normalization, and linked inspection state.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused smoke or integration-style test that renders a representative fixture morphology session, exercises at least one fidelity fallback and one overlay mode, and asserts stable pane metadata plus clear unavailable-state handling

### Notes
Assume `FW-M14-001` through `FW-M14-004` and the Milestone 5, 6, 10, and 11 morphology-related contracts are already in place. Preserve truthfulness over visual flash: if only a reduced geometry exists for a neuron in the active session, the pane should say so rather than fabricating surface detail. Do not attempt to create a git commit as part of this ticket.

## FW-M14-006 - Implement the replay scrubber, time-series pane, and baseline-versus-wave comparison workflow
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: replay / traces / comparison interaction

### Problem
Milestone 14 is explicitly done only when the UI supports replay and comparison, but the repo still has no canonical time scrubber or shared replay model that ties scene, morphology, traces, and analysis together. Simulator bundles already share a timebase and readout catalog, and Milestone 12 already packages comparison-oriented outputs, yet there is no one interaction surface that lets a reviewer scrub time, play or pause, compare baseline versus wave traces on the same cursor, or keep neuron and readout selections coherent while switching between arms. Without this ticket, the dashboard will remain a set of disconnected snapshots rather than an actual analysis interface.

### Requested Change
Implement the Milestone 14 replay and comparison workflow. Add the global time scrubber and playback controls, build the time-series pane for shared readout traces and related comparison views, and support explicit baseline-versus-wave comparison mode on the shared timebase while keeping wave-only diagnostics visibly distinct. The workflow should synchronize the cursor across scene, circuit, morphology, and analysis panes, support selection-driven trace inspection, and fail clearly when a requested comparison is not valid because the current session lacks a compatible arm pair or shared timebase.

### Acceptance Criteria
- One canonical replay control surface drives the active time cursor for all panes in the dashboard and can play, pause, and scrub deterministically on packaged fixture sessions.
- The time-series pane shows shared readout traces or equivalent comparison-ready signals for the active selection and supports baseline-versus-wave comparison on the canonical shared timebase.
- The comparison workflow preserves the fairness boundary by distinguishing shared-comparison traces from wave-only diagnostics instead of merging them into one unlabeled chart.
- Switching selections, overlays, or compared arms updates the pane through the shared dashboard state rather than each pane managing an independent cursor or comparison model.
- Regression coverage validates shared-timebase alignment, comparison-mode normalization, deterministic replay-state serialization, and clear failure handling for incompatible comparison requests.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that loads a representative fixture dashboard session, drives the replay cursor and comparison mode, and asserts synchronized time-series metadata plus expected fairness-boundary labeling

### Notes
Assume `FW-M14-001` through `FW-M14-005` and the Milestone 9 through Milestone 12 comparison contracts are already in place. This ticket should establish the shared replay semantics that later showcase and experiment-orchestration work can trust. Do not attempt to create a git commit as part of this ticket.

## FW-M14-007 - Implement the analysis pane, scientific overlay catalog, and deterministic export tools for images, video, and metrics
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: analysis visualization / overlays / export tooling

### Problem
The dashboard is supposed to surface metrics, heatmaps, ablations, phase maps, and exportable outputs, but the repo currently stops at packaged analysis and validation artifacts plus separate offline reports. There is no interactive analysis pane that can bring together task-summary cards, matrix views, phase-map references, validation-ladder findings, and experiment-level comparisons under one linked dashboard state. There is also no canonical export layer for turning the current dashboard view into deterministic images, videos, or metrics exports. Without this ticket, the Milestone 14 UI may look interactive while still failing the roadmap requirement that the project become understandable and shareable through polished analysis views and exports.

### Requested Change
Implement the Milestone 14 analysis pane together with the first scientific overlay catalog and export workflow. The pane should render packaged Milestone 12 and Milestone 13 outputs such as task-summary cards, comparison cards, matrix-like views, ablation summaries when present, phase-map references, and validation evidence, while keeping shared-comparison content, wave-only diagnostics, and reviewer-oriented validation findings visibly separated. Add deterministic export tools that can capture the current dashboard state as local review artifacts, including at least still-image export, metrics export, and one replay-oriented export path such as a video artifact or deterministic frame sequence suitable for later encoding.

### Acceptance Criteria
- The analysis pane can display representative packaged Milestone 12 and Milestone 13 outputs from the active dashboard session without reparsing raw simulator bundle directories.
- Overlay selection is contract-backed and explicit, with clear labeling for shared-comparison overlays, wave-only diagnostics, validation overlays, and unavailable overlays.
- The export workflow can generate deterministic local artifacts for at least still images, metrics-oriented data export, and one replay-oriented export path from the current dashboard state.
- Exported artifacts are discoverable through documented local commands or metadata-backed output paths rather than hidden temporary files.
- Regression coverage includes at least one fixture workflow that exercises analysis-pane payload discovery, overlay normalization, and deterministic export output paths plus expected summary fields.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that builds a representative analysis-pane session, exercises at least one overlay selection and one export path, and asserts deterministic artifact discovery plus expected export metadata

### Notes
Assume `FW-M14-001` through `FW-M14-006` and the Milestone 12 and Milestone 13 packaging layers are already in place. Keep the first export story honest and reproducible; a deterministic frame-sequence export is acceptable if a full video container proves too heavy for the initial version. Do not attempt to create a git commit as part of this ticket.

## FW-M14-008 - Run a Milestone 14 integration verification pass and publish a dashboard readiness report
- Status: open
- Priority: high
- Source: Milestone 14 roadmap 2026-03-29
- Area: verification / readiness / dashboard audit

### Problem
Even if the individual Milestone 14 tickets land, the repo still needs one explicit integration pass proving that the new dashboard is a coherent, reviewable interface rather than a stack of disconnected pane demos. Without a dedicated readiness ticket, it will be too easy to stop at isolated rendering success while leaving behind hidden contract mismatches, broken bundle discovery, desynchronized replay state, misleading overlay boundaries, or export paths that only work on one hand-crafted fixture. Milestone 15 experiment orchestration and Milestone 16 showcase mode will both depend on this interface being stable and trustworthy.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 14 implementation and publish a concise readiness report in-repo. The pass should exercise the full local dashboard workflow end to end on fixture artifacts and at least one representative manifest or experiment path, verify that the declared dashboard contract matches shipped behavior across scene, circuit, morphology, time-series, and analysis panes, confirm that replay and comparison state stay synchronized, and record any remaining product, scientific, or engineering risks that Milestones 15 and 16 must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 14 dashboard workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across dashboard-session planning, packaged session discovery, app-shell loading, scene-pane rendering, circuit inspection, morphology rendering, replay and time-series synchronization, analysis-pane payload discovery, and export workflow behavior.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 14 is ready to support Milestone 15 experiment orchestration and Milestone 16 showcase mode.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 14 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_14_ui_analysis_dashboard_tickets.md --ticket-id FW-M14-008 --dry-run --runner true`
- A documented end-to-end local Milestone 14 dashboard verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 14 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the dashboard is deterministic, understandable, comparison-ready, and fit to support the next milestones. Do not attempt to create a git commit as part of this ticket.
