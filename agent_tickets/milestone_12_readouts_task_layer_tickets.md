# Milestone 12 Readouts / Task Layer Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M12-001 - Freeze a versioned readout-analysis contract, task taxonomy, and Milestone 12 design note
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: contracts / docs / analysis architecture

### Problem
Milestones 9 through 11 already give the repo deterministic simulator result bundles, shared readout catalogs, `surface_wave` extension artifacts, and mixed-fidelity execution, but there is still no first-class contract for the analysis layer that sits on top of those outputs. The roadmap names direction selectivity, ON/OFF selectivity, optic-flow estimate, motion-vector estimate, latency, synchrony or coherence, phase-gradient statistics, wavefront speed or curvature, and patch activation entropy, yet none of those higher-level quantities currently have one canonical software identity, dependency surface, unit convention, scope rule, or discovery path. Without a versioned readout-analysis contract and decisive design note, later metric code will drift across execution helpers, inspection scripts, readiness reports, and UI payloads, and the team will lose the fairness guarantee that the same declared readout means the same observable across baseline and wave runs.

### Requested Change
Define a library-owned Milestone 12 readout-analysis contract and publish a concise design note that locks the metric taxonomy. The contract should distinguish among shared comparison readouts, derived task readouts, wave-only diagnostics, and experiment-level comparison outputs; define stable metric IDs, units, scopes, required source artifacts, and canonical discovery helpers; and state which quantities are allowed to depend only on shared readouts versus which may consume wave-only patch or phase artifacts. The design note should stay tightly aligned with the locked Milestone 1 hypothesis, the T4a/T5a terminal readout boundary, and the existing `simulator_result_bundle.v1` invariants, while also naming the first task families, null-test hooks, and UI-facing outputs Milestone 12 must support.

### Acceptance Criteria
- There is one canonical readout-analysis contract in library code with explicit identifiers and normalization helpers for shared readout metrics, derived task metrics, wave-only diagnostics, and experiment-level comparison outputs.
- The contract records stable metric IDs, units, scope rules, required source artifact classes, and fairness notes that explain whether a quantity must be computable from the shared readout catalog or may consume wave-only extension artifacts.
- A dedicated markdown design note explains the first supported metric families for Milestone 12, names the locked readout stop point and fairness invariants, and specifies how null-direction suppression, latency, direction selectivity, ON/OFF selectivity, motion-vector or optic-flow estimates, and wave-structure diagnostics should be interpreted.
- `docs/pipeline_notes.md` is updated so the Milestone 12 analysis contract sits alongside the existing geometry, coupling, retinal, simulator, and `surface_wave` contracts.
- Regression coverage verifies deterministic contract serialization, stable metric discovery, and normalization of representative fixture metric definitions.

### Verification
- `make test`
- A focused unit test that builds fixture analysis-contract metadata and asserts deterministic serialization plus discovery of metric and output definitions

### Notes
This ticket should land first and give the rest of Milestone 12 a stable vocabulary. Reuse Milestone 1, Milestone 9, and Milestone 10 language where those milestones already define fairness, shared readout semantics, and result-bundle invariants. Do not attempt to create a git commit as part of this ticket.

## FW-M12-002 - Extend manifest planning and config normalization for active readouts, analysis windows, comparison groups, and null-test declarations
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: planning / config / manifest integration

### Problem
The manifest and planning layers already carry `primary_metric`, `companion_metrics`, output targets, comparison arms, and timebase information, but they still do not resolve those declarations into one normalized task-analysis plan. There is no canonical place to define which readouts are active for a run, which stimulus windows should be analyzed, how ON versus OFF or preferred versus null conditions should be paired, how seed sweeps roll up into experiment-level task summaries, or which null tests are required for a given experiment. Without a shared planning surface, later analysis scripts will reinterpret manifest intent differently, duplicate compatibility checks, and quietly disagree about what one “task metric” actually consumed.

### Requested Change
Extend the library-owned manifest and config normalization path so a manifest plus local config resolves into a deterministic Milestone 12 analysis plan. The normalized plan should identify active readouts, derived task-readout recipes, analysis windows, condition-pair definitions, comparison groups, seed-aggregation rules, null-test declarations, and declared output targets for both per-run and experiment-level outputs. Keep the representation explicit enough that execution, offline analysis, readiness workflows, and later UI work can all discover the same analysis intent without inventing separate script-local configuration schemes.

### Acceptance Criteria
- There is one canonical API that resolves a manifest plus local config into a normalized readout-analysis plan with stable ordering and explicit defaults.
- The normalized plan records active shared readouts, derived task-readout recipes, analysis windows, condition-pair or arm-pair definitions, null-test declarations, and seed-aggregation rules needed by Milestone 12 workflows.
- The planner fails clearly when a manifest requests unsupported metric IDs, incompatible condition pairing, missing readout dependencies, or output targets that cannot be realized from local artifacts.
- Existing baseline, `surface_wave`, and mixed-fidelity arm planning remain compatible with the new analysis-plan layer instead of forcing a second manifest-resolution path.
- Regression coverage validates deterministic normalization, manifest override precedence, representative fixture analysis-plan resolution, and clear failure handling for incompatible metric requests.

### Verification
- `make test`
- A focused unit or integration-style test that resolves a fixture manifest into a normalized Milestone 12 analysis plan and asserts deterministic readout ordering plus clear error handling

### Notes
Assume `FW-M12-001` and the Milestone 9 through Milestone 11 planning layers are already in place. Favor one planning surface that execution, analysis, readiness, and UI code can all reuse rather than a pile of special-purpose YAML readers. Do not attempt to create a git commit as part of this ticket.

## FW-M12-003 - Build reusable shared-readout analysis kernels for latency, ON/OFF selectivity, and direction selectivity
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: readout kernels / comparison metrics / time-series analysis

### Problem
The current simulator execution path only emits generic per-readout summary rows such as endpoint, min, max, mean, and peak time, which is not enough to support the actual scientific observables named in the roadmap. There is still no reusable library layer that can take shared comparison readout traces on the canonical timebase and turn them into fair, deterministic latency estimates, ON/OFF polarity comparisons, or direction-selectivity summaries. Without those kernels, every later report or notebook will rebuild slightly different onset detection, windowing, normalization, and condition-pairing logic, which makes cross-arm comparisons fragile and hard to trust.

### Requested Change
Implement the first reusable Milestone 12 analysis kernels for shared readout traces. The library should consume normalized readout-analysis plans plus shared simulator result bundles and produce deterministic metric rows or structured summaries for latency, ON/OFF selectivity, and direction selectivity using only the shared comparison readout surface available to both baselines and wave runs. Make onset detection, baseline subtraction, preferred-versus-null pairing, and no-signal handling explicit and testable so the resulting metrics are reviewable rather than being buried inside one-off scripts.

### Acceptance Criteria
- There is a canonical analysis API that consumes shared readout traces on the declared simulator timebase and computes deterministic latency, ON/OFF selectivity, and direction-selectivity outputs.
- The implementation makes condition pairing, windowing, onset or peak selection, no-signal handling, and unit conventions explicit rather than relying on ad hoc caller behavior.
- The resulting metrics preserve Milestone 1 fairness constraints by operating on shared readout semantics rather than wave-only hidden state.
- The analysis output is compatible with the Milestone 12 contract and can be serialized into comparison-ready metric rows or structured summaries without special-case UI logic.
- Regression coverage validates representative preferred-versus-null, ON-versus-OFF, and latency fixture cases, including at least one edge case with ambiguous onset or flat responses.

### Verification
- `make test`
- Focused fixture-driven tests that feed deterministic readout traces through the shared-readout kernels and assert stable latency, polarity, and selectivity outputs

### Notes
Assume `FW-M12-001` and `FW-M12-002` are already in place. Keep the first kernels boring and inspectable; later reviewers should be able to trace every reported latency or selectivity number back to declared windows and shared trace samples. Do not attempt to create a git commit as part of this ticket.

## FW-M12-004 - Implement motion-vector and optic-flow task decoders on a fair, canonical task interface
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: task decoders / motion estimation / analysis APIs

### Problem
Milestone 12 explicitly calls for optic-flow estimates and motion-vector estimates, but the repo still has no decoder layer that can turn multi-condition readout evidence into a task-level motion estimate. The current vertical slice is still centered on a local motion patch and T4a/T5a terminal readouts, which is fine, but there is no shared interface that says how a decoder consumes shared readouts, stimulus metadata, or retinotopic context to produce a motion estimate without granting the wave model a special-purpose downstream decoder unavailable to the baselines. Without a canonical task-decoder layer, these metrics will either stay unimplemented or appear as one-off analysis code that is impossible to compare fairly.

### Requested Change
Build the first library-owned task-decoder interface for Milestone 12 and ship deterministic motion-vector and optic-flow estimators through that interface. The implementation should consume only declared shared readouts plus the normalized task-analysis plan and any allowed local context such as stimulus direction labels or retinotopic geometry metadata, and it should emit explicit task outputs with stable units, conventions, and diagnostic metadata. Support the current local motion-patch vertical slice first, but keep the interface extensible enough that later larger-field optic-flow tasks can reuse it without changing the contract.

### Acceptance Criteria
- There is a canonical task-decoder API that consumes normalized task inputs and emits deterministic motion-vector and optic-flow outputs with explicit units and conventions.
- The decoder interface explains which inputs are required, which quantities are derived purely from shared readouts, and what minimum condition structure must exist for a motion estimate to be considered valid.
- The implementation fails clearly when the manifest or result bundle does not provide enough directional or retinotopic context to realize the requested task metric.
- The resulting task outputs are compatible with the Milestone 12 analysis contract and discoverable through shared helpers rather than hidden inside one report generator.
- Regression coverage validates analytic or fixture cases with known motion direction, including at least one insufficient-context failure case and one deterministic small-patch success case.

### Verification
- `make test`
- A focused task-decoder test module that feeds known directional fixtures through the canonical decoder interface and asserts deterministic motion-vector or optic-flow estimates plus clear failure behavior

### Notes
Assume `FW-M12-001` through `FW-M12-003`, the Milestone 8 stimulus and retinal contracts, and the locked Milestone 1 fairness rules are already in place. The key guardrail is that task decoders may be richer than raw readouts without becoming wave-only cheats. Do not attempt to create a git commit as part of this ticket.

## FW-M12-005 - Implement wave-structure diagnostics for synchrony, coherence, phase gradients, wavefront speed or curvature, and patch activation entropy
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: wave diagnostics / spatial analysis / morphology-aware metrics

### Problem
The roadmap also calls for wave-specific structure metrics such as synchrony or coherence, phase-gradient statistics, wavefront speed or curvature, and patch activation entropy, but the repo currently exposes those ideas only partially through Milestone 10 inspection helpers. There is still no reusable, contract-backed analysis layer that turns wave patch traces, state summaries, or `surface_wave` extension artifacts into deterministic diagnostics with declared semantics. Without that layer, the same wave run could be described differently by inspection tooling, readiness reports, and later UI code, and mixed-fidelity follow-on work would have no stable interface for reporting wave structure.

### Requested Change
Implement the reusable Milestone 12 wave-diagnostic kernels that consume wave-capable result bundles and emit deterministic morphology-aware metrics. Reuse the existing Milestone 10 inspection logic where it already provides a good starting point, but refactor the relevant computations into contract-backed analysis functions that can be called by offline reports, experiment-level comparison workflows, and later UI data preparation. Keep these diagnostics explicitly separate from the shared comparison readout catalog so fairness remains visible: they are allowed wave-only diagnostics, not hidden replacements for the shared readout surface.

### Acceptance Criteria
- There is a canonical analysis API for synchrony or coherence, phase-gradient statistics, wavefront speed or curvature, and patch activation entropy using declared wave-side artifact dependencies.
- The implementation reuses or factors existing inspection-time computations where reasonable while moving the durable semantics into library-owned analysis helpers.
- The resulting outputs are discoverable through the Milestone 12 contract as wave-only diagnostics and do not mutate the meaning of shared readout IDs or shared comparison metrics.
- The implementation handles absent or incompatible wave artifacts clearly, including mixed-fidelity runs where only some roots expose wave-resolved patch or phase information.
- Regression coverage validates deterministic diagnostics on representative fixture patch-trace or phase-like cases, including at least one clear failure path for missing wave artifacts.

### Verification
- `make test`
- Focused fixture-driven tests that compute synchrony, phase-gradient, wavefront, and entropy diagnostics from deterministic wave artifact payloads

### Notes
Assume `FW-M12-001` through `FW-M12-004` and the Milestone 10 wave-inspection outputs are already in place. The goal is a reusable wave-diagnostics layer, not another one-off inspection script. Do not attempt to create a git commit as part of this ticket.

## FW-M12-006 - Build experiment-level comparison orchestration, null tests, seed aggregation, and at least one automated task score
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: comparison workflows / task layer / experiment analytics

### Problem
Per-run simulator bundles and per-run metrics tables already exist, but Milestone 12 is not complete until baseline-versus-wave comparisons become quantitative at the experiment level. Right now there is no library-owned workflow that loads the deterministic bundle set for one manifest, groups the intended arm comparisons, aggregates across seed sweeps, evaluates geometry-sensitive null tests, or emits a clean task-level summary that says whether the wave model changed a shared observable in the way the roadmap actually cares about. Without that orchestration layer, the repo can produce traces and metric rows forever without ever turning them into a task metric that tests the hypothesis.

### Requested Change
Implement the Milestone 12 task-layer workflow that loads normalized analysis plans plus local result bundles and emits experiment-level comparison outputs. The workflow should compare baseline versus `surface_wave`, intact versus shuffled, and where available `P0` versus `P1`; aggregate repeated seeds deterministically; run declared null tests and sanity checks; and compute at least one automated task score aligned with the locked Milestone 1 evidence ladder. Make the result explicit enough that later Milestone 13 validation and Milestone 14 UI work can consume the same experiment summary rather than reverse-engineering multiple bundle directories by hand.

### Acceptance Criteria
- A canonical local workflow can discover the relevant bundle set for one experiment and compute deterministic experiment-level comparison summaries from the normalized Milestone 12 analysis plan.
- The workflow records comparison pairing, seed aggregation, null-test outcomes, and at least one automated task score aligned with the Milestone 1 hypothesis, such as a geometry-sensitive null-direction suppression or latency effect that is tracked across intact versus shuffled or baseline-strength comparisons.
- Missing bundles, incompatible readout inventories, or incomplete seed coverage fail clearly instead of producing silently biased summaries.
- The resulting outputs are local-artifact-first, comparison-ready, and discoverable through shared helpers rather than requiring bespoke notebook glue.
- Regression coverage includes at least one fixture experiment with multiple arms and seed runs that asserts deterministic task summaries, null-test flags, and comparison grouping.

### Verification
- `make test`
- A smoke-style fixture workflow that loads multiple deterministic result bundles, runs the experiment-level task-analysis pipeline, and asserts stable comparison summaries plus at least one automated task score

### Notes
Assume `FW-M12-001` through `FW-M12-005`, the Milestone 9 result-bundle contract, and the Milestone 10 execution workflow are already in place. This ticket is the core of the task layer: traces become experiment-level evidence here. Do not attempt to create a git commit as part of this ticket.

## FW-M12-007 - Integrate standard analysis packaging, export formats, and UI-facing comparison payloads for Milestone 12 outputs
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: result packaging / export formats / UI handoff

### Problem
The current simulator workflow writes per-run bundles with generic metrics and a lightweight UI comparison payload, but it still does not package Milestone 12 analysis outputs in a stable, discoverable way. There is no canonical experiment-level analysis bundle, no durable export format for task summaries, null-test tables, heatmap-like matrices, or phase-map references, and no agreed payload shape that later UI work can consume without reparsing raw metric rows. Without a packaging layer, Milestone 12 outputs will sprawl across ad hoc JSON, CSV, and HTML files that later readiness or dashboard work cannot discover reliably.

### Requested Change
Add the standard packaging and export layer for Milestone 12 outputs. Define deterministic output locations and shared discovery helpers for experiment-level analysis artifacts, extend the existing UI-facing payloads so they can reference task summaries and analysis visualizations, and ship at least one lightweight offline report or visualization entrypoint that proves the packaged outputs are reviewable outside notebooks. Preserve the existing `simulator_result_bundle.v1` invariants for per-run artifacts while layering Milestone 12 exports on top through explicit metadata and discovery rather than filename guessing.

### Acceptance Criteria
- There is a canonical packaging layer for Milestone 12 analysis outputs with deterministic paths, metadata-backed discovery, and stable export formats for experiment-level summaries.
- Existing per-run result bundles remain compatible, while new analysis outputs are exposed through explicit artifact inventories or companion metadata rather than undocumented side effects.
- The UI-facing payload story is extended so later Milestone 14 code can discover task summaries, comparison cards, and analysis visualizations without reparsing raw bundle directories.
- A documented local command or script can generate a lightweight offline report or visualization from the packaged Milestone 12 outputs using only local artifacts.
- Regression coverage includes at least one smoke-style fixture workflow that generates packaged Milestone 12 analysis outputs and asserts deterministic paths plus expected summary fields.

### Verification
- `make test`
- A smoke-style fixture workflow that packages Milestone 12 experiment analysis outputs and asserts deterministic artifact discovery plus expected UI-facing payload fields

### Notes
Assume `FW-M12-001` through `FW-M12-006` are already in place. This is not the final dashboard from Milestone 14; it is the disciplined packaging layer that keeps Milestone 12 outputs stable and inspectable. Do not attempt to create a git commit as part of this ticket.

## FW-M12-008 - Run a Milestone 12 integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 12 roadmap 2026-03-22
- Area: verification / readiness / release audit

### Problem
Even if the earlier Milestone 12 tickets land individually, the repo still needs one explicit integration pass showing that readout analysis, task decoding, wave diagnostics, comparison orchestration, export packaging, and UI-facing payloads actually work together as one coherent layer. Without a dedicated readiness ticket, it will be too easy to stop at isolated metric kernels or one successful report while leaving behind hidden contract mismatches, fairness regressions, broken discovery paths, or analysis outputs that only work for a single hand-crafted fixture.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 12 implementation and publish a concise readiness report in-repo. The pass should exercise the full local workflow on fixture assets and at least one representative experiment manifest, verify that the declared analysis contract matches shipped behavior, confirm that baseline-versus-wave comparisons are quantitative rather than purely visual, and record any remaining scientific or engineering risks that Milestones 13 and 14 must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on issues rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 12 workflow is executed end to end using shipped local commands and fixture artifacts, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across analysis-plan resolution, shared-readout kernels, task decoders, wave-diagnostic kernels, experiment-level comparison orchestration, packaged exports, and UI-facing payload discovery.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 12 is ready to support the Milestone 13 validation ladder and Milestone 14 dashboard work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 12 integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_12_readouts_task_layer_tickets.md --ticket-id FW-M12-008 --dry-run --runner true`
- A documented end-to-end local Milestone 12 verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 12 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that readouts, task metrics, null tests, wave diagnostics, packaging, and UI handoff all agree on the same experiment story. Do not attempt to create a git commit as part of this ticket.
