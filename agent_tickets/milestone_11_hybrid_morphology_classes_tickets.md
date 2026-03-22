# Milestone 11 Hybrid Morphology Classes Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M11-001 - Freeze a versioned hybrid-morphology contract, fidelity taxonomy, and approximation design note
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: contracts / docs / architecture

### Problem
The repo now has strong contracts for geometry bundles, coupling bundles, retinal input, baseline execution, and `surface_wave` execution, but there is still no first-class contract for mixed morphology fidelity inside one simulator run. Role labels such as `surface_simulated`, `skeleton_simulated`, and `point_simulated` already exist in registry and coupling code, yet they do not currently define one canonical simulator-facing meaning for required assets, state layout, coupling anchor resolution, readout semantics, approximation limits, or promotion and demotion rules. Without a versioned hybrid contract, Milestone 11 work will drift across planner code, runtime glue, and result serialization, and it will be too easy to implement a mixed run that is operationally convenient but scientifically ambiguous.

### Requested Change
Define a library-owned hybrid-morphology contract and publish a concise design note that locks the Milestone 11 vocabulary. The contract should name the supported simulator-facing morphology classes, their required and optional local assets, their state and readout semantics, the allowed cross-class coupling routes, and the invariants that must remain stable when a neuron is promoted from point to skeleton to surface fidelity. Prefer extending the existing `surface_wave` planning and execution path with per-root morphology-class metadata instead of introducing a separate top-level simulator mode, unless a hard compatibility blocker is discovered and documented.

### Acceptance Criteria
- There is one canonical hybrid-morphology contract in library code with explicit identifiers for `surface_neuron`, `skeleton_neuron`, and `point_neuron` or equivalently named normalized classes.
- The contract records, per class, the required assets, realized state space, readout surface, coupling anchor resolution, serialization requirements, and approximation notes needed for deterministic planning and review.
- A dedicated markdown design note explains what each fidelity class is allowed to approximate, which semantics must remain invariant across promotion and demotion, and which behaviors are intentionally class-specific.
- `docs/pipeline_notes.md` is updated so mixed morphology sits alongside the existing geometry, coupling, retinal, and simulator contracts rather than living only in code comments.
- Regression coverage verifies deterministic contract serialization, stable class discovery, and normalization of representative fixture class metadata.

### Verification
- `make test`
- A focused unit test that builds fixture hybrid-morphology metadata and asserts deterministic contract serialization plus class discovery

### Notes
This ticket should land first and give the later tickets a stable vocabulary. Reuse Milestone 7, Milestone 9, and Milestone 10 contract language where those milestones already define anchor semantics, shared readouts, and result-bundle expectations. Do not attempt to create a git commit as part of this ticket.

## FW-M11-002 - Extend manifest planning and config normalization for per-root fidelity assignment in mixed runs
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: planning / config / manifest integration

### Problem
The current simulation planner can resolve baseline and `surface_wave` arms, but it still assumes one morphology-state strategy per arm. In particular, the wave-side planning path hardcodes one surface-oriented state resolution, one coupling anchor resolution, and one operator inventory story for every selected root. That prevents a single run from cleanly mixing full surface neurons with skeleton approximations and point placeholders, and it leaves no canonical place to express class overrides from registry defaults, manifest arms, or future scheduler-driven promotion rules.

### Requested Change
Extend the library-owned planning layer so a manifest plus config resolves into a deterministic mixed-fidelity execution plan with explicit per-root fidelity assignment. Normalize the chosen morphology class for each selected root, validate the required local assets for that class, record the realized approximation route, and preserve stable arm ordering and result-bundle identity. The planner should support registry-default roles, arm-level overrides, and a narrow policy surface for future promotion and demotion logic without forcing every caller to invent its own class-resolution code.

### Acceptance Criteria
- There is one canonical API that resolves a manifest plus local config into normalized per-root morphology assignments for a mixed run.
- The normalized arm plan records, for each selected root, the realized morphology class, required local asset references, state and coupling resolution, and any approximation-policy provenance needed to explain why that class was chosen.
- The planner fails clearly when a requested class lacks required local prerequisites, such as missing operator bundles for surface neurons, missing usable skeleton assets for skeleton neurons, or incompatible coupling expectations for point placeholders.
- Existing baseline and pure-surface plans remain supported without forcing callers to fork into a separate planning workflow.
- Regression coverage validates deterministic per-root assignment, class override precedence, missing-prerequisite failures, and representative fixture-manifest resolution using local artifacts only.

### Verification
- `make test`
- A focused unit or integration-style test that resolves a fixture manifest into a mixed-fidelity arm plan and asserts deterministic per-root class assignment plus clear error handling

### Notes
Assume `FW-M11-001` and the Milestone 9 through Milestone 10 planning layers are already in place. Keep the first implementation strict and explicit: later tickets should inherit normalized fidelity assignments from one planner surface rather than negotiating them independently. Do not attempt to create a git commit as part of this ticket.

## FW-M11-003 - Refactor the wave runtime around a pluggable morphology-class interface while preserving current surface behavior
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: runtime architecture / solver integration

### Problem
The current `surface_wave` runtime is organized around a surface-only execution path with `SingleNeuronSurfaceWaveSolver`, surface operator bundles, and patch-cloud coupling semantics baked directly into the circuit assembly. That is a good Milestone 10 implementation, but it is not yet a stable architecture for Milestone 11 because adding a skeleton or point class would currently require threading special cases through the same surface-specific code paths. Without a shared morphology-class runtime interface, every later fidelity class will either duplicate simulator plumbing or force a risky rewrite after functionality already lands.

### Requested Change
Refactor the mixed-fidelity runtime around a narrow pluggable morphology-class interface and migrate the existing surface implementation onto it first. The interface should cover initialization, stepping, state export, readout export, source injection, and coupling-facing projection in a way that remains deterministic and inspectable. Preserve current surface-run behavior and result compatibility while making it possible for later tickets to add skeleton and point implementations without changing the surrounding simulator architecture again.

### Acceptance Criteria
- There is a library-owned morphology-class runtime interface or adapter layer that the simulator uses instead of calling the surface solver directly as a special case.
- The existing surface implementation is migrated onto that interface without regressing current pure-surface fixture behavior beyond documented tolerances.
- The runtime exposes enough shared metadata that later classes can serialize comparable state summaries, readouts, and coupling projections without inventing their own ad hoc result formats.
- Pure-surface `surface_wave` arms remain executable through the refactored runtime using the same public command surface and deterministic result-bundle layout.
- Regression coverage verifies that the refactor preserves representative Milestone 10 surface behavior and that the new interface is sufficient to host at least one lightweight stub class in tests.

### Verification
- `make test`
- Focused regression tests that run a representative pure-surface fixture before and after the refactor path and assert deterministic compatibility through the new interface

### Notes
Assume `FW-M11-001` and `FW-M11-002` are already in place. The main deliverable is architectural headroom with no Milestone 10 behavior loss: make the runtime more general without making the current surface path harder to reason about. Do not attempt to create a git commit as part of this ticket.

## FW-M11-004 - Build the skeleton-neuron asset handoff, graph approximation, and deterministic skeleton runtime adapter
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: skeleton assets / graph dynamics / approximation runtime

### Problem
The repo already fetches raw SWC skeletons and uses skeleton anchors for coupling fallback, but it still has no simulator-facing skeleton morphology class. There is no canonical processed skeleton-graph handoff for runtime consumption, no deterministic skeleton-state container, and no graph-based approximation path that can stand in for a surface neuron while still participating in the same simulator architecture. Without that, Milestone 11 would claim skeleton support while actually treating skeletons only as coupling-localization helpers.

### Requested Change
Implement the first real skeleton-neuron approximation path end to end. Add a deterministic skeleton asset handoff suitable for runtime use, define the graph operator or reduced propagation structure required by the chosen approximation strategy, and implement a skeleton runtime adapter that conforms to the shared morphology-class interface from `FW-M11-003`. The resulting class should support initialization, stepping, source injection, readout export, and coupling projection using only local cached artifacts and documented approximation semantics.

### Acceptance Criteria
- There is a canonical runtime-discoverable skeleton asset representation or bundle that a mixed-fidelity plan can reference deterministically.
- The skeleton-neuron implementation exposes an explicit state container, graph or reduced operator payload, and documented readout semantics rather than loose script-local arrays.
- A mixed-fidelity plan can include at least one skeleton neuron that runs through the shared simulator lifecycle alongside surface-class peers.
- Missing, invalid, or scientifically unsupported skeleton inputs fail clearly instead of silently degrading to point behavior.
- Regression coverage validates deterministic skeleton-asset discovery, stable single-neuron skeleton stepping on local fixtures, and compatibility with the shared morphology-class runtime interface.

### Verification
- `make test`
- A focused fixture test that builds or loads a small skeleton asset, runs the skeleton adapter for several steps, and asserts deterministic state and readout behavior

### Notes
Assume `FW-M11-001` through `FW-M11-003` are already in place. Keep the first skeleton approximation narrow, well documented, and easy to audit; later biological tuning and richer branch-sensitive behavior can build on that stable contract. Do not attempt to create a git commit as part of this ticket.

## FW-M11-005 - Add the point-neuron placeholder class and fidelity-agnostic state serialization for mixed runs
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: point placeholders / serialization / result contracts

### Problem
Point-level placeholders already exist as a concept in registry roles and baseline simulator logic, but mixed-fidelity wave-side execution still lacks a first-class point-neuron class inside the same runtime. There is also no fidelity-agnostic state serialization layer that can tell downstream tooling how to load surface, skeleton, and point state from one run without hardcoding class-specific file rules. If Milestone 11 adds point placeholders only as internal shortcuts, downstream readout, validation, and UI work will inherit an opaque special case instead of a stable mixed-class contract.

### Requested Change
Implement the point-neuron morphology class inside the shared mixed-fidelity runtime and add fidelity-agnostic state and readout serialization for mixed runs. Reuse existing baseline family behavior where that is scientifically appropriate, but normalize it through the Milestone 11 contract so a point placeholder can coexist with surface and skeleton neurons in one result bundle. The written outputs should let later metrics, validation, and UI code discover per-root class, state summary, and readout payloads without reverse-engineering runtime internals.

### Acceptance Criteria
- A mixed-fidelity plan can include one or more point-neuron placeholders that execute through the shared morphology-class runtime rather than a separate baseline-only path.
- Result-bundle metadata records the realized morphology class for every root and points to class-appropriate but contract-consistent state and readout artifacts.
- Shared state-summary and readout loading helpers can consume mixed runs without the caller having to guess which roots were surface, skeleton, or point implementations.
- Constant or repeated fixture input produces stable point-class output structure and deterministic serialization across repeated runs.
- Regression coverage validates mixed-run serialization, deterministic point-class behavior, and discovery of per-root fidelity metadata through library helpers.

### Verification
- `make test`
- A focused integration-style test that runs a small mixed fixture containing at least one point placeholder and asserts deterministic mixed-class serialization plus helper-based discovery

### Notes
Assume `FW-M11-001` through `FW-M11-004` are already in place. Favor one clear result contract over a pile of class-specific one-off files; later Milestone 12 and Milestone 14 tooling should be able to load mixed runs through shared helpers first. Do not attempt to create a git commit as part of this ticket.

## FW-M11-006 - Implement cross-class coupling routing and canonical source-projection semantics for surface, skeleton, and point neurons
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: coupling execution / routing / mixed representations

### Problem
Milestone 7 defined a fallback-aware coupling contract, but the live simulator still lacks execution-time routing between mixed morphology classes. Today the wave runtime assumes surface patch clouds on both sides of a coupling component, while a real Milestone 11 run must support combinations such as surface-to-skeleton, skeleton-to-surface, skeleton-to-point, and point-to-surface without changing the scientific sign, delay, and aggregation semantics. Without a canonical router, mixed-fidelity execution will either ignore class mismatches or quietly mutate coupling meaning across code paths.

### Requested Change
Build the library-owned coupling router that converts normalized coupling assets into executable source-projection and target-injection operations across all supported morphology-class pairs. Preserve the Milestone 7 sign, delay, aggregation, and fallback hierarchy semantics while making the class-to-class translation explicit and testable. The router should explain which representation pair was realized for each executed component and fail clearly when a requested cross-class route is unsupported or scientifically disallowed.

### Acceptance Criteria
- A canonical runtime layer can execute coupling between the supported morphology-class pairs using the normalized hybrid plan and existing coupling assets.
- Sign handling, delay handling, aggregation, and fallback behavior remain aligned with the Milestone 7 coupling contract rather than being redefined separately for each class pair.
- Runtime metadata records the realized source class, target class, projection route, and any fallback or blocked reason for each executed coupling component or component family.
- Unsupported or ambiguous cross-class routes fail clearly instead of silently dropping the connection or mutating it into an unrelated approximation.
- Regression coverage validates deterministic execution for representative surface-to-skeleton, skeleton-to-point, and point-to-surface or point-to-skeleton fixture cases using local artifacts only.

### Verification
- `make test`
- A focused mixed-coupling test module that exercises representative class-pair routes and asserts deterministic routing metadata plus sign and delay preservation

### Notes
Assume `FW-M11-001` through `FW-M11-005` and the Milestone 7 coupling pipeline are already in place. Keep the first router explicit and auditable: later work can broaden approximation families, but this ticket should make the realized translation path obvious for every executed edge. Do not attempt to create a git commit as part of this ticket.

## FW-M11-007 - Add surrogate-preservation audits, promotion and demotion policy hooks, and offline mixed-fidelity inspection tooling
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: policy / inspection / approximation QA

### Problem
Milestone 11 is not finished when mixed classes merely execute. The roadmap explicitly requires rules for when a neuron should be promoted or demoted in fidelity and checks that lower-fidelity surrogates preserve the needed behavior. Right now the repo has no policy hook for those decisions, no shared audit workflow that compares surrogate behavior against a higher-fidelity reference, and no offline report that helps reviewers decide whether a mixed-fidelity plan is scientifically defensible.

### Requested Change
Implement the first policy and audit layer for mixed fidelity. Add a narrow, deterministic policy surface that can express promotion and demotion recommendations from local descriptors, config, or manifest context, and pair it with an offline inspection workflow that compares surrogate behavior against a declared reference class on local fixtures. The inspection output should surface where a point or skeleton surrogate is acceptable, where it materially diverges, and which roots should be promoted before later readout or validation milestones rely on them.

### Acceptance Criteria
- There is a documented policy hook for fidelity selection or promotion and demotion recommendations that downstream planners can consume deterministically.
- A local inspection workflow can compare a mixed-fidelity run or per-root surrogate against a declared higher-fidelity reference and write a deterministic review artifact.
- The inspection output records per-root fidelity choice, surrogate-versus-reference comparison metrics, blocking versus review-level deviations, and any recommended promotion targets.
- The implementation stays local-artifact-only and does not require live FlyWire access for the audit workflow.
- Automated coverage validates deterministic policy normalization, deterministic report paths, and at least one fixture case where a lower-fidelity surrogate is flagged for review or promotion.

### Verification
- `make test`
- A smoke-style fixture run that executes the mixed-fidelity inspection workflow and asserts deterministic report contents, policy metadata, and promotion-review flags

### Notes
Assume `FW-M11-001` through `FW-M11-006` are already in place. This is not the final validation ladder from Milestone 13; it is the first approximation-audit layer that keeps Milestone 11 honest and gives Grant a structured place to review surrogate quality. Do not attempt to create a git commit as part of this ticket.

## FW-M11-008 - Run a Milestone 11 mixed-fidelity integration pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 11 roadmap 2026-03-22
- Area: verification / readiness / release audit

### Problem
Even if the earlier Milestone 11 tickets land, the repo still needs one explicit integration pass proving that mixed fidelity is a coherent simulator capability rather than a pile of partially compatible adapters. Without a dedicated readiness ticket, it will be too easy to stop once one surface root, one skeleton root, and one point placeholder can all run independently, while leaving behind hidden planner drift, broken cross-class routing, unreadable result bundles, or undocumented gaps between fidelity policy and executed behavior.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 11 implementation and publish a concise readiness report in-repo. The pass should exercise the full local mixed-fidelity workflow on fixture assets, verify that planning, runtime execution, cross-class coupling, result serialization, and inspection tooling agree with the published contract, and identify any remaining scientific or engineering risks that later milestones must respect. Fix any discovered contract mismatches directly where reasonable, and record the rest as explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 11 mixed-fidelity workflow is executed end to end using shipped local commands and fixture assets, with outputs captured in a deterministic report location.
- The verification pass checks contract compatibility across per-root fidelity planning, runtime adapter behavior, skeleton and point execution, cross-class coupling routing, mixed-class serialization, and surrogate-preservation inspection.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether mixed fidelity is ready to support downstream readouts, validation, and UI work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same mixed-fidelity integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_11_hybrid_morphology_classes_tickets.md --ticket-id FW-M11-008 --dry-run --runner true`
- A documented end-to-end local mixed-fidelity verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 11 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that surface, skeleton, and point classes coexist in one deterministic workflow and that upgrading a neuron does not require rewriting the simulator. Do not attempt to create a git commit as part of this ticket.
