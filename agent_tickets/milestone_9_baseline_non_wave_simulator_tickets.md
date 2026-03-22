# Milestone 9 Baseline Non-Wave Simulator Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M9-001 - Freeze a versioned simulator result bundle contract and fair baseline design note
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: simulator contracts / manifests / docs

### Problem
The repo has a Milestone 1 design lock, manifest schema, coupling bundles, and stimulus-side contracts, but it still has no simulator-owned contract for what one baseline run produces. There is no canonical definition for run-directory layout, per-arm metadata, timebase fields, state-summary payloads, readout traces, comparison-ready metric tables, or how later UI and wave-mode code should discover the same baseline outputs deterministically. Without a versioned result contract and a decisive design note, Milestones 9, 10, 12, 13, and 14 will each invent their own run bundle shape and baseline semantics.

### Requested Change
Define a first-class simulator result bundle contract in library code and document the baseline-model design choices behind it. Centralize run-path construction, metadata serialization, and output discovery so baseline and later `surface_wave` runs can share the same high-level bundle shape. The design note should be decisive: pin down what `P0` and `P1` mean in software terms, define the shared timebase and readout conventions, state what a fair baseline is allowed to add versus what only the wave model may add, and specify the invariants later metrics, UI, and comparison tooling must preserve.

### Acceptance Criteria
- Simulator result-bundle path construction, metadata serialization, and bundle discovery are centralized in library code rather than duplicated inside runner scripts.
- The chosen contract records an explicit simulator-contract version plus the metadata needed to reproduce a run deterministically, including manifest and arm identity, model mode, baseline family, selected asset references, timing, seed, readout catalog, and output artifact inventory.
- A dedicated markdown design note compares the supported baseline families, chooses the default `P0` and `P1` realizations, documents shared readout conventions, and names the invariants later `surface_wave` and UI work must preserve.
- `docs/pipeline_notes.md` is updated so the simulator result contract sits alongside the subset, geometry, coupling, and stimulus contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture baseline run specs.

### Verification
- `make test`
- A focused unit test that builds fixture simulator-run metadata and asserts deterministic bundle serialization plus path discovery

### Notes
This ticket should land first. Reuse the Milestone 1 design-lock language wherever it already answers the fairness question instead of re-litigating the scientific claim in code comments. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-002 - Build manifest-driven simulation plans, typed baseline config normalization, and run discovery helpers
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: planning / config / manifest integration

### Problem
The manifest already declares `model_mode`, `baseline_family`, topology conditions, seeds, stimuli, and must-show outputs, but the repo still has no runtime layer that turns those fields into an executable baseline simulation plan. There is no canonical API that resolves a manifest arm into normalized timing, asset references, baseline parameters, selected roots, output locations, or reproducible run IDs. Without that layer, every runner will re-parse manifests differently and later `baseline` versus `surface_wave` comparisons will drift before the simulation even starts.

### Requested Change
Implement the library-owned simulation planning layer that resolves config and manifest inputs into normalized baseline run specs. The API should consume the existing experiment-manifest structure, validate that the required local assets and config are present, normalize baseline-family parameters and runtime defaults, and expose deterministic discovery helpers for per-arm runs. Keep the representation explicit and future-proof so the same planning surface can later hand the same manifest to the wave engine without changing the manifest schema again.

### Acceptance Criteria
- There is one canonical API that resolves a manifest plus local config into normalized baseline simulation plans with explicit defaults and stable arm ordering.
- The plan records the manifest-level stimulus or retinal input reference, selected circuit or subset identity, coupling sources, timing, seed handling, baseline-family parameters, and deterministic output locations needed to launch a run.
- `model_mode=baseline` arms fail clearly when required local prerequisites are missing, ambiguous, or incompatible, instead of silently guessing at fallback behavior.
- The planning layer is structured so later `surface_wave` runs can reuse the same manifest-resolution path and extend it rather than replace it.
- Regression coverage validates normalization, plan determinism, missing-prerequisite failures, and representative fixture-manifest resolution using only local artifacts.

### Verification
- `make test`
- A focused unit test that resolves a fixture manifest into baseline run plans and asserts normalized output, deterministic IDs, and clear error handling

### Notes
Assume `FW-M9-001` is already in place. Favor script-thin entrypoints and library-owned normalization logic so the same manifest does not acquire a second incompatible execution path later. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-003 - Implement the core simulator execution framework, state containers, and deterministic stepping loop
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: simulator engine / runtime / execution

### Problem
Milestone 9 cannot start from a bag of per-neuron update functions. The repo still lacks the simulator framework itself: there is no canonical runtime object for one experiment arm, no fixed-timestep stepping loop, no typed state container, no lifecycle for initialization versus update versus readout extraction, and no shared execution interface that later `surface_wave` code could plug into. Without that core, baseline implementation will hardcode orchestration details that should have been reusable engine plumbing.

### Requested Change
Build the core simulator execution framework in library code. The framework should own run initialization, fixed-timestep stepping, state storage, deterministic update ordering, lightweight instrumentation hooks, and structured snapshot extraction. Design it so scalar baseline state is easy to implement now, while the same top-level run interface can later host morphology-resolved state for `surface_wave` without rewriting orchestration, serialization, or monitoring logic.

### Acceptance Criteria
- There is a canonical simulator runtime API that can initialize, step, and finalize a run with deterministic ordering and explicit lifecycle boundaries.
- Typed or otherwise explicit state containers represent per-neuron dynamic state, exogenous drive, recurrent input accumulation, and readout-ready summaries without relying on loose dicts passed everywhere.
- The stepping loop exposes the integration timestep, current simulation time, seed or determinism context, and lightweight hooks for logging or metric collection.
- The framework is engine-agnostic enough that a future wave solver can implement the same top-level interface without replacing manifest planning or result-bundle plumbing.
- Regression coverage validates deterministic stepping on local fixture circuits, stable initialization and finalization behavior, and representative snapshot extraction.

### Verification
- `make test`
- A focused simulator-runtime test that steps a small fixture circuit and asserts deterministic state evolution plus lifecycle behavior

### Notes
Assume `FW-M9-001` and `FW-M9-002` have landed. Keep the runtime boring, explicit, and inspectable; later solver work should be able to trust the orchestration layer rather than work around it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-004 - Implement fair P0 and P1 baseline neuron families with shared readout semantics
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: baseline dynamics / model families / readouts

### Problem
The Milestone 1 design lock explicitly names `P0` and `P1`, but the repo still has no actual implementation of either baseline family. There is no library-owned equation set, parameter schema, update rule, normalization convention, or shared readout mapping for the canonical point baseline versus the stronger reduced baseline. Without concrete `P0` and `P1` implementations, later comparisons to `surface_wave` will either be scientifically vague or will drift into script-local one-off baselines that nobody can audit fairly.

### Requested Change
Implement the baseline neuron-family layer that instantiates the canonical `P0` and `P1` models described by the design lock. `P0` should realize the passive leaky linear non-spiking single-compartment baseline, while `P1` should realize the stronger reduced baseline with explicit synaptic integration current or explicit delay structure chosen in `FW-M9-001`. Expose the realized state variables and readout mapping explicitly so downstream metrics compare fair, shared observables rather than apples to oranges.

### Acceptance Criteria
- There is one canonical API that resolves normalized model specs into executable `P0` and `P1` neuron-family implementations.
- `P0` and `P1` use documented, test-covered update equations and parameter semantics rather than hidden heuristics or hardcoded constants in runner code.
- The implementation exposes shared readout extraction so baseline runs can report the same observable family that later `surface_wave` runs will be compared against.
- Invalid, ambiguous, or scientifically disallowed parameterizations fail clearly instead of silently mutating into a different model family.
- Regression coverage validates representative steady-state, impulse-response, and parameter-normalization behavior for both baseline families using local fixtures only.

### Verification
- `make test`
- A focused unit test that instantiates fixture `P0` and `P1` models, steps them under simple drives, and asserts deterministic responses plus shared readout behavior

### Notes
Assume `FW-M9-001` through `FW-M9-003` are already in place. Keep the baseline fair and explicit: the point of this ticket is not maximal biological richness, but a credible comparison family that later reviewers can audit quickly. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-005 - Integrate canonical input streams and Milestone 7 coupling bundles into baseline simulation runs
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: input integration / connectivity / circuit execution

### Problem
Even with a stepping engine and neuron models, Milestone 9 is still incomplete unless the baseline simulator can run the actual connectome-constrained circuit with the repo’s canonical inputs. Right now there is no baseline-side integration path that consumes the selected-root roster, local coupling bundles, topology condition, and canonical time-varying input stream and turns them into recurrent per-neuron updates. Without that integration, the baseline mode is only a toy dynamical system rather than the matched circuit control the roadmap calls for.

### Requested Change
Implement the input and connectivity integration layer that drives the baseline simulator from the repo’s canonical assets. The implementation should resolve the selected circuit, ingest the relevant Milestone 7 coupling bundles, apply the intact or shuffled topology condition from the manifest plan, and feed the simulator with the canonical time-varying input stream expected by the visual-input stack. Keep the integration deterministic, cache-friendly, and asset-contract-aware so the same circuit and same input can later be run through `baseline` and `surface_wave` modes without changing the data handoff surface.

### Acceptance Criteria
- A canonical API can construct one executable baseline circuit run from selected roots, coupling bundles, topology condition, and a canonical input stream using only local repo artifacts.
- Recurrent accumulation, coupling signs, aggregation, and any supported delay or integration-current semantics are applied through library-owned coupling or planning logic rather than reimplemented ad hoc inside the step loop.
- The same resolved circuit and input asset identity always produce the same baseline wiring and drive schedule for a given seed and config.
- Missing or inconsistent prerequisites fail clearly, including absent coupling assets, incompatible root rosters, or unusable input timing.
- Regression coverage validates deterministic circuit execution on small fixture circuits, including at least one intact-versus-shuffled or delay-sensitive case.

### Verification
- `make test`
- A focused integration-style test that runs a small fixture circuit with canonical input and coupling assets and asserts deterministic recurrent state updates

### Notes
Assume the earlier Milestone 9 tickets are already in place and that the relevant local input contracts from upstream milestones exist or have fixture stand-ins. The key deliverable is a matched-circuit control path, not a one-off current injection demo. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-006 - Ship manifest-driven baseline execution, result serialization, logging, metrics, and UI-ready comparison payloads
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: CLI / result bundles / metrics / UI handoff

### Problem
Milestone 9 is not done when a baseline simulation can run only from Python internals. The same experiment manifest must run in baseline mode, baseline outputs must line up with later wave-mode outputs for comparison, and the UI must be able to switch between modes without reverse-engineering custom file layouts. Right now there is no documented command that executes a manifest arm end-to-end, no deterministic result serialization for run logs and metrics, and no UI-facing comparison payload that uses the shared contract described in the roadmap.

### Requested Change
Add the public execution and result-handoff layer for baseline mode. This should include a thin local command or script that resolves a manifest into baseline runs, executes them through the simulator framework, writes the versioned result bundle, records structured logs and provenance, and emits comparison-ready metrics plus UI-facing payloads that follow the shared simulator and UI contracts. The output should be shaped so later `surface_wave` runs can write into the same high-level layout and comparison tooling can switch modes without special-casing baseline internals.

### Acceptance Criteria
- A documented local command or script can execute `model_mode=baseline` manifest arms end-to-end using only local repo artifacts and write outputs into deterministic result-bundle paths.
- The written bundle includes run metadata, structured logs, per-neuron or per-readout summaries, shared output traces, metric tables, and UI-facing payloads needed for side-by-side comparison with future `surface_wave` runs.
- The baseline output schema is aligned with the shared result-bundle and UI contracts so later tooling can switch modes without guessing at filenames or field semantics.
- Result serialization and logging remain deterministic and provenance-rich enough that repeated runs can be diffed and audited locally.
- Regression coverage includes at least one smoke-style fixture manifest run that asserts deterministic output files, summary fields, and UI-payload discovery.

### Verification
- `make test`
- A smoke-style fixture run that executes a baseline manifest arm and asserts deterministic bundle identity, summary metrics, and UI-facing payload structure

### Notes
Assume `FW-M9-001` through `FW-M9-005` are already in place. Favor one clean user-facing execution path over multiple half-overlapping scripts; later wave-mode work should extend this workflow, not compete with it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M9-007 - Run a Milestone 9 integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 9 roadmap 2026-03-21
- Area: verification / review / release readiness

### Problem
Even if the Milestone 9 build tickets land individually, the repo still needs one explicit integration pass that proves baseline mode is a real control simulator and not just a partially wired runtime. Without a dedicated verification ticket, it is too easy to stop at isolated engine tests while leaving behind manifest drift, weak fairness guarantees, mismatched output schemas, missing UI payloads, or hidden determinism failures that would only appear once `surface_wave` implementation starts.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 9 implementation and publish a concise readiness report in-repo. This pass should exercise the full local baseline workflow on fixture assets and at least one representative manifest path, confirm that documentation matches shipped behavior, verify that baseline outputs are comparison-ready for later wave-mode runs, and either fix any gaps directly or record them as explicit follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

### Acceptance Criteria
- The full Milestone 9 baseline workflow is executed end-to-end using the shipped command or commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across manifest planning, runtime execution, `P0` and `P1` behavior, coupling and input integration, result serialization, logging, metrics, and UI-facing payloads.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 9 is ready to support downstream `surface_wave`, metrics, and UI comparison work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_9_baseline_non_wave_simulator_tickets.md --ticket-id FW-M9-007 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 9 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that baseline mode is integrated, deterministic, comparison-ready, and prepared for the later wave engine to plug into the same workflow. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
