# Milestone 15 Experiment Orchestration And Ablations Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

Implementation rule for every Milestone 15 ticket:
- Before closing the ticket, add a companion rationale note at `docs/experiment_orchestration_notes/<ticket-id>_rationale.md`.
- That note must explain the rationale behind all material design choices, the testing strategy used, and explicitly call out what is intentionally simplified in the first version plus the clearest expansion paths for later work.

## FW-M15-001 - Freeze a versioned experiment-suite contract, ablation taxonomy, and orchestration design note
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: contracts / docs / orchestration architecture

### Problem
Milestones 9 through 14 already give the repo deterministic simulator bundles, experiment-analysis bundles, validation ladders, and packaged dashboard sessions, but there is still no first-class software contract for the suite-level workflow that Milestone 15 is supposed to make routine. Right now the roadmap names experiment dimensions such as scene type, motion direction, speed, contrast, noise level, active subset, wave kernel, coupling mode, mesh resolution, solver settings, and fidelity class, plus required ablations such as no waves, no lateral coupling, shuffled synapse locations, shuffled morphology, and altered sign or delay assumptions. None of those suite-level concepts currently have stable IDs, lineage semantics, bundle roles, or one canonical place where Jack-owned orchestration stops and Grant-owned scientific ablation choice begins. Without a versioned contract and decisive design note, later automation will sprawl across ad hoc manifest variants, shell scripts, and result folders that are hard to compare or trust.

### Requested Change
Define a library-owned Milestone 15 suite contract and publish a concise design note that locks the orchestration vocabulary. The contract should name the suite identity, canonical experiment-dimension IDs, required ablation family IDs, suite-cell lineage, work-item status semantics, reproducibility hooks, and artifact roles for upstream manifests plus downstream simulator, analysis, validation, dashboard, table, and plot outputs. The design note should explain how the suite layer composes with `simulation_plan.v1`, `experiment_analysis_bundle.v1`, `validation_ladder.v1`, and `dashboard_session.v1`, and it should make the ownership boundary explicit: Jack owns the orchestration surface and reproducibility mechanics, while Grant owns which scientifically meaningful ablation sets are declared through that surface.

### Acceptance Criteria
- There is one canonical Milestone 15 suite contract in library code with explicit identifiers for experiment dimensions, required ablation families, suite-cell lineage, work-item statuses, and suite-level artifact roles.
- The contract records deterministic discovery hooks for upstream manifest inputs and downstream simulator-result bundles, experiment-analysis bundles, validation bundles, dashboard sessions, summary tables, plots, and review artifacts without mutating the earlier milestone contracts.
- A dedicated markdown design note explains suite identity, suite-cell lineage, reproducibility semantics, the taxonomy for the Milestone 15 dimensions and required ablations, storage expectations, and the boundary between orchestration mechanics versus scientific ablation selection.
- `docs/pipeline_notes.md` is updated so the Milestone 15 suite contract sits alongside the existing simulator, analysis, validation, and dashboard contracts.
- Regression coverage verifies deterministic contract serialization, stable dimension and ablation discovery, and normalization of representative fixture suite metadata.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit test that builds fixture suite-contract metadata and asserts deterministic serialization plus stable dimension and ablation discovery

### Notes
This ticket should land first and give the rest of Milestone 15 a stable vocabulary. Reuse the existing simulator, analysis, validation, and dashboard contract language where those layers already answer lineage, fairness-boundary, or artifact-discovery questions. Do not attempt to create a git commit as part of this ticket.

## FW-M15-002 - Extend manifest and config normalization for suite manifests, sweep axes, and ablation declarations
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: planning / config / manifest integration

### Problem
The repo can already normalize one manifest into deterministic simulation, analysis, validation, and dashboard planning surfaces, but it still has no canonical way to declare a whole Milestone 15 suite. There is no shared planning layer for expressing which dimensions should sweep, which dimensions should stay fixed, when dimensions should be zipped versus cross-product expanded, which seed policies should be reused across cells, which ablation families attach to which base conditions, or how output roots should be named. Without one normalized suite-planning surface, every orchestration script will rediscover experiment intent differently, silently disagree about which runs belong together, and make reproducibility harder exactly where Milestone 15 is supposed to improve it.

### Requested Change
Extend the library-owned manifest and config normalization path so local config plus one suite manifest or one experiment manifest with suite extensions resolves into a deterministic Milestone 15 orchestration plan. The normalized plan should identify active experiment dimensions, sweep policies, seed policies, ablation declarations, comparison pairings, stage targets, output roots, and deterministic suite-cell ordering. It should support the roadmap dimensions directly, including scene type, motion direction, speed, contrast, noise level, active subset, wave kernel, coupling mode, mesh resolution, timestep or solver settings, and fidelity class, while also failing clearly when a requested sweep or ablation combination is unsupported, scientifically misleading, or incompatible with the shipped upstream bundle contracts.

### Acceptance Criteria
- There is one canonical API that resolves local config plus a suite-oriented manifest input into a normalized Milestone 15 orchestration plan with stable ordering and explicit defaults.
- The normalized plan records active dimensions, per-dimension sweep semantics, ablation declarations, seed reuse policy, stage targets, comparison pairings, and deterministic output locations needed by Milestone 15 workflows.
- The planner supports explicit control over cross-product versus linked-dimension expansion and fails clearly on unknown dimension IDs, incompatible axis combinations, unsupported ablation declarations, contradictory seed rules, or missing upstream prerequisites.
- Existing simulation, analysis, validation, and dashboard planning layers remain reusable inputs to the suite planner rather than being bypassed by a second filename-guessing or script-local YAML path.
- Regression coverage validates deterministic normalization, override precedence, representative fixture suite-plan resolution, and clear failure handling for unsupported suite requests.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit or integration-style test that resolves a representative fixture suite manifest into a normalized Milestone 15 orchestration plan and asserts deterministic cell ordering plus clear error handling

### Notes
Assume `FW-M15-001` and the Milestone 9 through Milestone 14 planning layers are already in place. Favor one planning surface that execution, reporting, readiness, and later showcase tooling can all reuse rather than a pile of special-purpose suite readers. Do not attempt to create a git commit as part of this ticket.

## FW-M15-003 - Build deterministic suite expansion, work scheduling, and resume-safe batch execution
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: orchestration / execution / workflow automation

### Problem
The repo already has local entrypoints for `simulate`, experiment-level comparison analysis, validation workflows, and dashboard packaging, but Milestone 15 is specifically about running experiments systematically instead of by hand. There is still no canonical batch runner that can take a normalized suite plan, expand it into deterministic work items, execute the required stages in order, persist intermediate status, and resume or retry safely after partial completion. Without a real orchestration workflow, every suite run will devolve into hand-written shell sequences, inconsistent skips, or forgotten analysis and validation steps, which defeats the point of this milestone.

### Requested Change
Implement the library-owned batch execution workflow for Milestone 15. The workflow should consume a normalized suite plan, expand deterministic work items or suite cells, execute the declared stages in a stable order, persist stage-level status and provenance, and support dry-run plus resume-safe behavior for partial reruns. Reuse the existing Milestone 9 through Milestone 14 library entrypoints rather than shelling out blindly wherever a direct library API already exists. The first version may stay local and deterministic rather than introducing distributed scheduling, but it must make stage ordering, rerun semantics, and failure handling explicit enough that large suites stop depending on manual operator memory.

### Acceptance Criteria
- There is one canonical local workflow that consumes a normalized Milestone 15 suite plan and executes deterministic work items for the declared stages.
- Work-item identities, stage ordering, dry-run output, and persisted status semantics are explicit and stable so a partially completed suite can be resumed without reinterpreting prior outputs.
- The implementation records provenance for each executed stage, including the normalized suite-cell identity and the upstream or downstream artifacts attached to that stage.
- Failures, skips, and partial completions are represented explicitly rather than being inferred later from missing files or console output.
- Regression coverage includes at least one fixture workflow that expands a representative suite, exercises dry-run and resume behavior, and asserts deterministic work-item ordering plus clear failure handling.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that resolves a small suite plan, exercises dry-run plus at least one resumed execution path, and asserts stable work-item metadata and status persistence

### Notes
Assume `FW-M15-001` and `FW-M15-002` plus the existing simulation, analysis, validation, and dashboard library workflows are already in place. Keep the first runner boring and reviewable; a deterministic local orchestrator is more valuable here than a premature cluster scheduler. Do not attempt to create a git commit as part of this ticket.

## FW-M15-004 - Implement canonical ablation transform families for the required Milestone 15 manipulations
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: ablation modeling / plan transforms / provenance

### Problem
Milestone 15 names a concrete ablation set, but the repo still has no canonical software surface for realizing those manipulations reproducibly. Right now there is no deterministic transform layer that can take one base suite cell and derive the required variants for no waves, waves only on chosen cell classes, no lateral coupling, shuffled synapse locations, shuffled morphology, coarser geometry, or altered sign or delay assumptions. Without explicit transform semantics, later runs will quietly mean different things when two people say they ran the same ablation, and the resulting comparisons will be hard to interpret or reproduce.

### Requested Change
Build the library-owned ablation transform layer for Milestone 15. It should derive normalized ablation variants from a base suite cell or normalized experiment plan, attach explicit ablation provenance, and keep any ablation-specific RNG or perturbation seed separate from the simulator seed so the causal effect of the ablation remains auditable. The implementation should support the full required roadmap set and should make it obvious where the first version intentionally simplifies a perturbation family, such as bounding the first altered sign or delay assumption modes to a documented subset rather than pretending the whole scientific design space is already covered.

### Acceptance Criteria
- Each required Milestone 15 ablation family has a stable software identity and one deterministic transform path from a base suite cell to a realized ablation variant.
- The implementation supports the roadmap-required ablations: no waves, waves only on chosen cell classes, no lateral coupling, shuffled synapse locations, shuffled morphology, coarser geometry, and altered sign or delay assumptions.
- Every realized ablation variant carries explicit provenance describing which transform was applied, which inputs were perturbed, and which ablation-specific RNG seed or deterministic perturbation policy was used.
- The transform layer fails clearly when an ablation cannot be realized because required prerequisites are missing, such as unavailable cell-class assignments, absent coupling bundles, unavailable geometry variants, or unsupported sign or delay modes.
- Regression coverage includes representative fixture cases for each required ablation family plus at least one clear failure case for a missing prerequisite or unsupported perturbation request.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- Focused fixture-driven tests that realize each required ablation family from deterministic base plans and assert stable provenance plus clear failure behavior

### Notes
Assume `FW-M15-001` through `FW-M15-003`, the Milestone 6 geometry contract, the Milestone 7 coupling contract, and the Milestone 9 through Milestone 12 planning surfaces are already in place. Grant owns deciding which ablations are scientifically most diagnostic; this ticket makes those declared manipulations reproducible in software. Do not attempt to create a git commit as part of this ticket.

## FW-M15-005 - Package suite outputs with deterministic storage conventions, result indexing, and artifact lineage
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: packaging / indexing / storage conventions

### Problem
Even if a suite executes correctly, Milestone 15 still fails if the outputs sprawl across per-experiment directories with no authoritative index tying one suite cell to its simulator bundles, analysis bundle, validation outputs, dashboard session, tables, and plots. Right now the repo has strong per-run and per-experiment packaging layers, but no suite-level storage convention or result index that makes it easy to answer simple questions such as which ablation cell failed, which baseline cell a plot belongs to, or which validation bundle corresponds to one reported summary row. Without a suite-level packaging layer, comparison workflows and readiness checks will keep re-scanning the filesystem instead of reading one deterministic artifact catalog.

### Requested Change
Add the packaging and indexing layer for Milestone 15 suite outputs. Define deterministic output locations, one authoritative suite metadata anchor, shared discovery helpers for suite-cell records and stage artifacts, and a result index that maps normalized dimension values plus ablation identity to downstream simulator, analysis, validation, dashboard, and report artifacts. The first version should expose both machine-friendly discovery and reviewer-friendly inventory surfaces, but it should avoid inventing a second source of truth for experiment-level artifacts that already have their own bundle contracts.

### Acceptance Criteria
- There is one canonical Milestone 15 suite packaging layer with deterministic output paths, metadata-backed discovery, and stable artifact references for suite cells and stage outputs.
- The suite package records explicit lineage from normalized dimension values and ablation identity to the realized simulator, analysis, validation, dashboard, table, and plot artifacts for that cell.
- Failed, skipped, and incomplete cells remain visible in the result index instead of disappearing from the suite inventory.
- The implementation exposes at least one machine-friendly index surface that downstream reporting and readiness workflows can consume without globbing raw directories.
- Regression coverage includes at least one fixture suite that writes deterministic package metadata plus indexed artifact references and asserts stable paths for both successful and incomplete cells.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that packages a representative suite output inventory and asserts deterministic artifact discovery plus expected lineage fields

### Notes
Assume `FW-M15-001` through `FW-M15-004` and the Milestone 12 through Milestone 14 bundle contracts are already in place. This ticket should make result indexing and storage conventions explicit enough that later review tooling never has to guess which artifact belongs to which suite cell. Do not attempt to create a git commit as part of this ticket.

## FW-M15-006 - Build suite-level aggregation, comparison tables, and ablation-aware metric rollups
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: aggregation / comparison analytics / seed rollups

### Problem
Milestone 12 already packages experiment-level summaries and Milestone 13 already packages validation findings, but Milestone 15 is specifically about comparing whole suites and ablations rather than inspecting one experiment at a time. There is still no canonical suite-level workflow that can aggregate across seeds, collapse repeated cells deterministically, line up baseline versus wave or intact versus ablated comparisons, and produce one comparison-ready table surface keyed by the dimensions that matter. Without that rollup layer, result indexing alone will not make the outcomes easy to compare, and every reviewer will end up building bespoke notebooks to answer routine questions about whether an ablation changed the shared metrics, wave diagnostics, or validation status.

### Requested Change
Implement the suite-level aggregation workflow for Milestone 15. The workflow should consume the packaged suite index together with existing experiment-analysis and validation outputs, compute deterministic comparison rows and summary tables across dimensions and ablations, and keep fairness boundaries visible by distinguishing shared-comparison metrics, wave-only diagnostics, and validation findings even when they appear in the same review surface. It should also make seed rollup semantics explicit so repeated runs contribute consistently rather than through implicit averaging hidden inside a plotting helper.

### Acceptance Criteria
- There is one canonical API that consumes a packaged Milestone 15 suite inventory and emits deterministic suite-level comparison rows or tables across declared dimensions and ablation families.
- The rollup semantics for seed aggregation, missing data, baseline-versus-wave pairing, and intact-versus-ablated pairing are explicit and testable.
- Shared-comparison metrics, wave-only diagnostics, and validation findings remain visibly separated in the aggregated outputs rather than being merged into one unlabeled score column.
- The workflow fails clearly when required comparison pairings are missing or when incomplete seed coverage would make a declared comparison misleading.
- Regression coverage includes at least one fixture suite with multiple dimensions, repeated seeds, and ablation variants that asserts deterministic comparison rows plus clear failure handling for incomplete coverage.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that loads a representative packaged suite inventory, computes suite-level rollups, and asserts deterministic comparison rows plus explicit fairness-boundary labeling

### Notes
Assume `FW-M15-001` through `FW-M15-005` and the Milestone 12 plus Milestone 13 packaging layers are already in place. Keep the first aggregation layer honest and inspectable; reviewers should be able to trace any reported suite-level delta back to packaged experiment-level evidence. Do not attempt to create a git commit as part of this ticket.

## FW-M15-007 - Generate deterministic suite reports, summary tables, and auto-generated comparison plots
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: reporting / plots / review tooling

### Problem
Jack explicitly owns summary tables and auto-generated comparison plots for this milestone, but the repo still has no suite-level review surface that turns aggregated results into something a reviewer can scan quickly. Even if the suite index and rollups exist, Milestone 15 is not done until the outputs are easy to compare, which means deterministic reports, stable table exports, and plot catalogs that do not require hand-written notebooks every time someone wants to review a sweep. Without a reporting layer, the suite machinery will technically run while still failing the milestone’s usability goal.

### Requested Change
Add the suite-level reporting workflow for Milestone 15. The implementation should generate deterministic local review artifacts from the packaged suite inventory and suite-level rollups, including summary tables, auto-generated comparison plots across key sweep dimensions and ablation families, and at least one lightweight offline report surface that links the plots back to the underlying suite cells and packaged experiment artifacts. Keep the first version local and reproducible rather than optimizing for a web service; a disciplined static HTML plus JSON and image export story is enough if the outputs remain easy to discover and review.

### Acceptance Criteria
- One documented local workflow can generate deterministic Milestone 15 review artifacts from a packaged suite inventory without reparsing raw per-experiment directories.
- The reporting layer emits summary tables, auto-generated comparison plots, and at least one lightweight offline report or visualization index for suite review.
- Reported plots and tables are metadata-backed and traceable to the underlying suite cells, comparison rows, and packaged experiment-level artifacts rather than being undocumented one-off files.
- The output catalog keeps fairness-critical shared-comparison content visibly separate from wave-only diagnostics and validation findings when those surfaces coexist in the same review artifact set.
- Regression coverage includes at least one fixture workflow that generates representative tables and plots, asserts deterministic output paths and expected summary metadata, and verifies that plot labeling stays stable across reruns.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that builds a representative packaged suite report, exercises at least one table export and one comparison-plot export, and asserts deterministic artifact discovery plus expected summary metadata

### Notes
Assume `FW-M15-001` through `FW-M15-006` are already in place. The first reporting surface should optimize for trust and repeatability, not for maximal visual novelty; deterministic static outputs are acceptable if they make suite review fast and honest. Do not attempt to create a git commit as part of this ticket.

## FW-M15-008 - Run a Milestone 15 integration verification pass and publish an orchestration readiness report
- Status: open
- Priority: high
- Source: Milestone 15 roadmap 2026-03-29
- Area: verification / readiness / orchestration audit

### Problem
Even if the earlier Milestone 15 tickets land individually, the repo still needs one explicit integration pass proving that a full suite can run from manifest-driven declarations, required ablations are reproducible, and the resulting outputs are genuinely easy to compare. Without a dedicated readiness ticket, it will be too easy to stop at isolated planner success, one successful ablation transform, or one nice-looking plot while leaving behind hidden mismatches among suite planning, batch execution, artifact indexing, aggregation, and reporting. Milestone 16 showcase work will depend on this orchestration layer being stable and reviewable.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 15 implementation and publish a concise readiness report in-repo. The pass should exercise the full local suite workflow end to end on fixture artifacts and at least one representative manifest-driven suite path, verify that the declared contract matches shipped behavior across suite planning, batch execution, ablation derivation, suite packaging, rollup computation, and reporting, and record any remaining scientific or engineering risks that later showcase or deeper scientific sweep work must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 15 suite workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across suite-manifest resolution, deterministic work scheduling, ablation transform realization, suite artifact indexing, suite-level rollups, and report or plot generation.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 15 is ready to support Milestone 16 showcase work and larger scientific review loops.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 15 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_15_experiment_orchestration_ablations_tickets.md --ticket-id FW-M15-008 --dry-run --runner true`
- A documented end-to-end local Milestone 15 suite command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 15 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that full suites run from manifest-driven declarations, required ablations are reproducible, and the resulting comparisons are deterministic and reviewable. Do not attempt to create a git commit as part of this ticket.
