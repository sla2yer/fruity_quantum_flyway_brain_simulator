# Milestone 13 Validation Ladder Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

Implementation rule for every Milestone 13 ticket:
- Before closing the ticket, add a companion rationale note at `docs/validation_ladder_notes/<ticket-id>_rationale.md`.
- That note must explain the design choices made, the testing strategy used, and explicitly call out anything intentionally simplified plus the most obvious expansion paths for later work.

## FW-M13-001 - Freeze a versioned validation-ladder contract, validator taxonomy, and criteria-handoff design note
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: contracts / docs / validation architecture

### Problem
Milestones 6, 10, 11, and 12 already give the repo operator QA, wave inspection, mixed-fidelity inspection, and experiment-analysis outputs, but there is still no first-class contract that says what the Milestone 13 validation ladder actually is in software terms. The roadmap names numerical, morphology, circuit, and task sanity layers, yet none of those layers currently have stable validator IDs, evidence scopes, result-status semantics, or one canonical place where machine-generated findings stop and Grant-reviewed scientific interpretation begins. Without a versioned validation contract and one decisive design note, later validation work will sprawl across scripts, readiness reports, and notebooks, and the team will lose the ability to compare one validation run against another with confidence.

### Requested Change
Define a library-owned Milestone 13 validation contract and publish a concise design note that locks the ladder vocabulary. The contract should name the validation layers, validator IDs, result-status semantics, criteria-profile references, artifact-discovery helpers, and the boundary between machine-checkable diagnostics versus reviewer-adjudicated plausibility decisions. Keep the contract aligned with the existing operator, simulator-result, mixed-fidelity, and experiment-analysis contracts so validation can compose with those layers instead of bypassing them.

### Acceptance Criteria
- There is one canonical validation contract in library code with explicit identifiers for the four Milestone 13 layers and their first validator families.
- The contract records stable validator IDs, evidence scopes, result-status semantics, criteria-profile references, and deterministic artifact-discovery helpers for validation outputs.
- A dedicated markdown design note explains the ladder structure, the boundary between automated findings and Grant-owned scientific interpretation, and which invariants later validation tickets must preserve.
- `docs/pipeline_notes.md` is updated so the validation ladder sits alongside the existing geometry, coupling, simulator, mixed-fidelity, and analysis contracts.
- Regression coverage verifies deterministic contract serialization, stable validator discovery, and normalization of representative fixture validator metadata.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit test that builds fixture validation-contract metadata and asserts deterministic serialization plus validator discovery

### Notes
This ticket should land first and give the rest of Milestone 13 a stable vocabulary. Reuse Milestone 6, Milestone 10, Milestone 11, and Milestone 12 contract language where those milestones already define status semantics, fairness boundaries, or artifact discovery. Do not attempt to create a git commit as part of this ticket.

## FW-M13-002 - Extend manifest and config normalization for validation plans, perturbation suites, and criteria profiles
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: planning / config / validation orchestration

### Problem
The repo can already normalize execution plans and experiment-analysis plans, but there is still no canonical place to declare which validation layers should run, which bundles or manifests they should consume, which perturbation suites belong to each layer, how seed sweeps or geometry variants should be grouped, or which criteria profile should be applied to a given validation pass. Without a shared planning surface, every validator script will rediscover inputs differently, thresholds will drift across reports, and regression comparisons will quietly stop meaning the same thing over time.

### Requested Change
Extend the library-owned planning layer so local config plus a manifest or bundle reference resolves into a deterministic Milestone 13 validation plan. The normalized plan should identify active layers and validators, target experiment arms or result bundles, perturbation suites such as timestep sweeps, geometry variants, sign or delay perturbations, and noise robustness checks, plus the criteria-profile references and deterministic output locations required for a repeatable validation run. Keep the representation explicit enough that CLI workflows, regression scripts, readiness checks, and later dashboard work can all consume the same validation intent.

### Acceptance Criteria
- There is one canonical API that resolves local config plus manifest or bundle inputs into a normalized validation plan with stable ordering and explicit defaults.
- The normalized plan records active validation layers, target artifact references, perturbation suites, comparison groups, criteria-profile references, and deterministic output locations needed by the Milestone 13 workflows.
- The planner fails clearly when required local prerequisites are missing, such as absent analysis bundles, unsupported geometry variants, incomplete seed coverage, or unknown criteria-profile identifiers.
- Existing execution and Milestone 12 analysis workflows remain reusable inputs to the validation planner rather than forcing a parallel manifest-resolution path.
- Regression coverage validates deterministic normalization, override precedence, representative fixture validation-plan resolution, and clear failure handling for unsupported validation requests.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit or integration-style test that resolves a fixture manifest or result-bundle reference into a normalized Milestone 13 validation plan and asserts deterministic ordering plus clear error handling

### Notes
Assume `FW-M13-001` and the Milestone 9 through Milestone 12 planning layers are already in place. Favor one planning surface that every later validator can reuse rather than a pile of special-purpose YAML readers or ad hoc CLI defaults. Do not attempt to create a git commit as part of this ticket.

## FW-M13-003 - Build the numerical-sanity validation suite for stability, operator checks, boundary behavior, and mesh-resolution sensitivity
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: numerical validation / solver QA / operator diagnostics

### Problem
Milestone 6 already checks operator construction quality and Milestone 10 already ships wave-inspection tooling, but the repo still lacks one canonical numerical-sanity suite that can prove the live simulator is behaving sensibly as a dynamical system. There is no reusable validator layer for timestep stability, energy or amplitude behavior, boundary-condition behavior, operator correctness under the live runtime assumptions, or sensitivity to mesh-resolution changes. Without that suite, solver regressions will show up only as vague visual differences or late task-level failures, which is too slow and too ambiguous for a serious validation ladder.

### Requested Change
Implement the Milestone 13 numerical-sanity validators as reusable library workflows on top of the normalized validation plan. The suite should exercise timestep sweeps, energy or amplitude tripwires, boundary-condition comparisons, operator-health checks, and mesh-resolution or coarse-versus-fine sensitivity using only local fixtures and shipped local assets. Make the resulting diagnostics explicit and reviewable so a failure says which numerical assumption broke, on which root or fixture, under which perturbation, rather than just reporting that one run looked unstable.

### Acceptance Criteria
- There is a canonical numerical-validation API that can evaluate timestep stability, energy or amplitude behavior, boundary-condition behavior, operator correctness, and mesh-resolution sensitivity on local fixtures or cached local assets.
- The validators emit normalized finding records that include validator ID, measured quantity, comparison basis or expected envelope, status, and actionable diagnostic metadata.
- The numerical suite can compare perturbation variants deterministically without requiring live FlyWire access, including at least one timestep-sweep path and one resolution-sensitivity path.
- At least one documented local workflow can run the numerical-sanity suite and write deterministic local report artifacts that later packaging and readiness code can reuse.
- Regression coverage includes representative stable and unstable fixture cases so the suite catches at least one intentional numerical tripwire rather than only happy paths.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- Focused fixture-driven tests that run the numerical validators against deterministic operator and solver fixtures and assert stable finding IDs, statuses, and diagnostics

### Notes
Assume `FW-M13-001`, `FW-M13-002`, the Milestone 6 operator assets, and the Milestone 10 wave runtime are already in place. Keep the first suite explicit and auditable: numerical trust comes from clear evidence, not from a black-box “looks stable” score. Do not attempt to create a git commit as part of this ticket.

## FW-M13-004 - Build the morphology-sanity validation suite for shape effects, bottlenecks, and representation sensitivity
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: morphology validation / geometry sensitivity / approximation QA

### Problem
The repo already knows how to build geometry bundles, compare fine versus coarse operators, and inspect mixed-fidelity surrogates, but it still has no first-class validator that asks whether morphology is affecting propagation in the expected ways. There is no canonical workflow for shape-dependent propagation, bottleneck and branching effects, simplification sensitivity, or patchification sensitivity. Without a morphology-sanity suite, the validation ladder cannot tell the difference between a model that is numerically stable yet morphology-blind and a model that is actually responding to geometry in a meaningful way.

### Requested Change
Implement the Milestone 13 morphology-sanity validators as reusable local workflows that compare matched morphology variants and summarize how propagation changes with structure. The suite should make bottlenecks, branching, simplification, and patchification sensitivity explicit, reusing the Milestone 5 geometry descriptors, Milestone 6 operator artifacts, Milestone 10 runtime, and Milestone 11 mixed-fidelity inspection surfaces where appropriate. The output should name which morphological variant was compared, what behavior changed, and whether the change stayed within expected, review-level, or blocking bounds.

### Acceptance Criteria
- There is a canonical morphology-validation API or workflow that can compare matched morphology variants and report shape-dependent propagation, bottleneck or branching effects, simplification sensitivity, and patchification sensitivity.
- The implementation reuses existing geometry, operator, and mixed-fidelity artifact discovery rather than inventing a separate morphology-input stack.
- Validation outputs record variant provenance, comparison metrics, status semantics, and localized diagnostics that identify which root, branch, patch set, or simplification variant drove the finding.
- At least one documented local workflow can run the morphology-sanity suite on deterministic fixtures or shipped local assets without requiring live FlyWire access.
- Regression coverage includes representative fixture cases for branching or bottleneck behavior and at least one simplification or patchification sensitivity comparison.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- Focused fixture or smoke-style tests that compare matched morphology variants and assert deterministic morphology-sanity findings plus clear provenance metadata

### Notes
Assume `FW-M13-001` through `FW-M13-003`, the Milestone 5 geometry bundle contract, the Milestone 6 operator pipeline, and the Milestone 11 mixed-fidelity inspection surfaces are already in place. The goal is not to prove full biological truth; it is to make morphology sensitivity explicit, reviewable, and regression-checkable. Do not attempt to create a git commit as part of this ticket.

## FW-M13-005 - Build the circuit-sanity validation suite for delays, signs, aggregation, and motion-pathway asymmetry
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: circuit validation / coupling QA / stimulus-response motifs

### Problem
Milestone 7 established coupling semantics and Milestone 12 established experiment-level readout analysis, but the repo still lacks a validator layer that proves those coupling semantics behave plausibly when the simulator actually runs a circuit. There is no canonical workflow for checking delay structure, sign behavior, aggregation behavior, or pathway asymmetry under motion stimuli. Without a circuit-sanity suite, later users can observe a task-level effect without knowing whether it came from sensible circuit mechanics or from one accidental sign flip, one broken delay quantization path, or one aggregation bug buried inside the runtime.

### Requested Change
Implement the Milestone 13 circuit-sanity validators as reusable motif-level and small-circuit workflows. The suite should exercise representative delay, sign, and aggregation cases and at least one pathway-asymmetry case under canonical motion stimuli, using existing local coupling bundles, simulator execution, and Milestone 12 readout-analysis outputs. Make expected-versus-observed circuit relationships explicit so a failing validation run tells the reviewer which edge family, motif, or pathway lost plausibility and how.

### Acceptance Criteria
- There is a canonical circuit-validation API or workflow that can evaluate plausible delay structure, sign behavior, aggregation behavior, and pathway asymmetry under deterministic local stimuli.
- The suite reuses the Milestone 7 coupling contract, Milestone 10 and Milestone 11 runtime execution paths, and Milestone 12 shared-readout analysis outputs rather than bypassing them.
- Validation outputs record motif or edge provenance, expected relationship, observed relationship, status, and actionable diagnostics for broken or ambiguous cases.
- Missing or incompatible coupling, readout, or stimulus prerequisites fail clearly instead of producing silently biased circuit findings.
- Regression coverage includes representative pass and fail fixture cases for delay, sign, or aggregation behavior and at least one deterministic motion-pathway asymmetry check.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- Focused fixture-driven tests that run small-circuit validation motifs and assert deterministic circuit-sanity findings, edge provenance, and clear failure messaging

### Notes
Assume `FW-M13-001` through `FW-M13-004`, the Milestone 7 coupling pipeline, and the Milestone 12 analysis layer are already in place. Keep the first circuit suite small but decisive: it should make coupling plausibility inspectable before later tasks bury the cause. Do not attempt to create a git commit as part of this ticket.

## FW-M13-006 - Build the task-sanity validation suite for stable outputs, reproducible arm differences, and perturbation robustness
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: task validation / experiment robustness / regression evidence

### Problem
Milestone 12 can already turn local result bundles into experiment-level comparisons, but Milestone 13 is not complete until those task-level outputs themselves become validated. There is still no canonical workflow that asks whether task outputs are stable across seeds, whether baseline-versus-wave differences are reproducible rather than anecdotal, or whether those differences survive modest perturbation and noise. Without a task-sanity suite, the repo can emit attractive comparison panels while still failing the basic question of whether the claimed effect is robust enough to trust.

### Requested Change
Implement the Milestone 13 task-sanity validators as reusable experiment-level workflows on top of the normalized validation plan and Milestone 12 analysis bundles. The suite should measure output stability, reproducibility of baseline-versus-wave differences, and robustness under declared perturbation or noise sweeps while preserving the fairness boundary between shared-comparison metrics and wave-only diagnostics. Make seed coverage, perturbation coverage, and effect-consistency reporting explicit so later reviewers can see whether a claimed task effect is stable, review-level, or blocking.

### Acceptance Criteria
- There is a canonical task-validation API or workflow that consumes Milestone 12 experiment-analysis outputs and computes deterministic task-sanity findings for stability, reproducibility, and perturbation robustness.
- The workflow supports seed aggregation, perturbation or noise sweeps, and explicit comparison of baseline versus wave or intact versus ablated arms where those pairings are declared by the validation plan.
- Validation outputs keep fairness-critical shared metrics visibly separate from wave-only diagnostics while still allowing both to coexist in one review artifact.
- Missing seed coverage, contradictory task outcomes, or incompatible analysis inventories fail clearly instead of silently degrading the validation result.
- Regression coverage includes at least one fixture experiment with multiple arms and seeds that asserts deterministic task-sanity summaries under both clean and perturbed conditions.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that loads deterministic experiment-analysis outputs, runs the task-sanity suite, and asserts stable findings for seed consistency and perturbation robustness

### Notes
Assume `FW-M13-001` through `FW-M13-005` and the Milestone 12 analysis bundle workflow are already in place. The goal here is experiment-level confidence, not a new downstream decoder boundary. Do not attempt to create a git commit as part of this ticket.

## FW-M13-007 - Ship packaged validation reports, regression baselines, and CI-friendly validation commands
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: packaging / reports / regression tooling / CI

### Problem
Even if all four validation layers exist, Milestone 13 will still be weak unless the findings are easy to rerun, compare, and review. Right now there is no canonical validation-bundle layout, no shared discovery helper for per-layer findings, no deterministic regression baseline story, and no single local command surface that Jack can wire into smoke automation or CI. Without that packaging layer, validation results will sprawl across ad hoc JSON, CSV, Markdown, and notebook fragments, and model changes will remain hard to regression-check even when the underlying validators are sound.

### Requested Change
Add the packaging and regression layer for Milestone 13 validation outputs. Define deterministic output locations and shared discovery helpers for per-layer findings, aggregate summaries, and review artifacts; add at least one lightweight offline report workflow plus notebook-friendly exports; and expose a documented local command surface suitable for smoke automation and CI, such as a dedicated validation-ladder script or Make target. Preserve the distinction between raw layer findings, summarized gates, and reviewer-facing reports so future dashboard work can consume stable artifacts without reparsing one-off report files.

### Acceptance Criteria
- There is a canonical packaging layer for Milestone 13 validation outputs with deterministic paths, metadata-backed discovery, and stable export formats for per-layer findings, regression summaries, and review artifacts.
- At least one documented local command or script can run the packaged validation ladder end to end on local fixtures and produce deterministic report outputs without live FlyWire access.
- The implementation includes notebook-friendly or tabular exports plus at least one lightweight offline report surface that helps reviewers inspect validation findings outside raw JSON.
- A CI-friendly smoke command or Make target exists for a reduced local validation pass so model changes can be regression-checked automatically when feasible.
- Regression coverage includes at least one smoke-style fixture workflow that generates packaged Milestone 13 outputs and asserts deterministic paths plus expected summary fields.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that runs the packaged validation ladder, writes deterministic outputs, and asserts artifact discovery plus expected summary fields

### Notes
Assume `FW-M13-001` through `FW-M13-006` are already in place. This ticket is where Jack’s automation and reporting ownership becomes concrete: make the ladder easy to rerun, review, and gate without turning every validation pass into a bespoke notebook session. Do not attempt to create a git commit as part of this ticket.

## FW-M13-008 - Run a Milestone 13 integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 13 roadmap 2026-03-26
- Area: verification / readiness / validation audit

### Problem
Even if the individual Milestone 13 tickets land, the repo still needs one explicit integration pass proving that the validation ladder is a coherent, reusable capability rather than a stack of disconnected checks. Without a dedicated readiness ticket, it will be too easy to stop at isolated validator success while leaving behind hidden contract mismatches, broken report discovery, unreviewable failure output, or task-level conclusions that are no longer traceable back to the lower ladder layers.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 13 implementation and publish a concise readiness report in-repo. The pass should exercise the full validation ladder end to end on local fixtures and at least one representative manifest path, verify that the declared contract matches shipped behavior across numerical, morphology, circuit, and task layers, confirm that findings are packaged for regression use, and record any remaining scientific or engineering risks that later milestones must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 13 validation workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic report location.
- The verification pass checks contract compatibility across validation-plan resolution, numerical-sanity validators, morphology-sanity validators, circuit-sanity validators, task-sanity validators, packaged exports, and regression-command discovery.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 13 is ready to support downstream dashboard and experiment-orchestration work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 13 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_13_validation_ladder_tickets.md --ticket-id FW-M13-008 --dry-run --runner true`
- A documented end-to-end local Milestone 13 validation command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 13 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the full validation ladder is deterministic, actionable, and fit to catch regressions before later milestones build on it. Do not attempt to create a git commit as part of this ticket.
