# Milestone 10 Surface-Wave Engine Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M10-001 - Freeze a versioned surface-wave model contract, parameter schema, and stability design note
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: wave model / contracts / docs

### Problem
Milestone 9 gives the repo a baseline simulator runtime and result-bundle contract, while Milestones 6 and 7 provide operator and coupling assets, but the repo still has no first-class contract for the wave model itself. There is no canonical definition for the chosen model family, state variable names and units, parameter presets, solver-mode identifiers, synaptic source semantics, recovery-state semantics, optional anisotropy or branching modifiers, or which stability assumptions later tickets are allowed to rely on. Without a versioned wave-model contract and a decisive design note, the actual equations will drift into solver internals, manifest parsing will become inconsistent, and later validation work will struggle to distinguish scientific intent from implementation accident.

### Requested Change
Define a first-class surface-wave model contract in library code and document the numerical and scientific choices behind it. Centralize wave-model naming, parameter normalization and serialization, contract-version metadata, and design-note discovery so later planning, execution, and result tooling can resolve one canonical `surface_wave` family without hardcoded strings. The design note should compare the candidate model families named in the roadmap, choose the default family for Milestone 10, define the state variables, propagation term, damping term, recovery or refractory behavior, synaptic source injection semantics, nonlinearities, optional anisotropy and branching extensions, and state what counts as physically meaningful behavior versus a numerical artifact.

### Acceptance Criteria
- Wave-model identifiers, parameter path construction, and metadata serialization are centralized in library code rather than duplicated inside scripts or solver modules.
- The chosen contract records an explicit wave-model contract version plus the normalized parameters and defaults needed to reproduce a `surface_wave` run deterministically, including state-variable definitions, solver family, damping and recovery settings, nonlinearity mode, anisotropy mode, and branching mode.
- A dedicated markdown design note compares the viable Milestone 10 model families, chooses the default, documents the stability-relevant assumptions and parameter ranges, and names the invariants later execution, metrics, and validation tickets must preserve.
- `docs/pipeline_notes.md` is updated so the wave-model contract sits alongside the geometry, operator, coupling, stimulus, retinal, and simulator contracts already in the repo.
- Regression coverage verifies deterministic contract serialization, stable model discovery, and compatibility of normalized fixture parameter bundles.

### Verification
- `make test`
- A focused unit test that builds fixture wave-model metadata and asserts deterministic contract serialization plus discovery

### Notes
This ticket should land first. Reuse Milestone 1, Milestone 6, and Milestone 9 language where those documents already answer fairness or stability questions instead of forking duplicate definitions. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-002 - Extend manifest-driven simulation planning and config normalization for `model_mode=surface_wave`
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: planning / config / manifest integration

### Problem
The repo now has baseline-oriented simulation planning, but there is still no canonical planning layer that turns a manifest arm into an executable wave run. A `surface_wave` arm needs operator assets, coupling assets, input references, resolution choices, solver defaults, parameter presets, and stability guardrails resolved together, yet none of that is normalized today. Without a shared planning API, each runner will parse `surface_wave` manifests differently, miss prerequisites in inconsistent ways, and encode wave-only assumptions directly into CLI scripts.

### Requested Change
Extend the library-owned simulation planning layer so manifests and config can resolve `model_mode=surface_wave` arms into normalized wave execution plans. The API should consume the existing experiment-manifest structure, validate required local prerequisites, normalize the chosen wave-model parameters and runtime defaults, resolve operator and coupling asset references, and assign deterministic run identities and output locations. Keep the representation explicit enough that later sweep, validation, and mixed-fidelity tickets can reuse the same planning surface instead of inventing a second wave-specific execution path.

### Acceptance Criteria
- There is one canonical API that resolves a manifest plus local config into normalized `surface_wave` run plans with explicit defaults and stable arm ordering.
- The normalized plan records the manifest-level input reference, selected roots, operator assets, coupling assets, topology condition, timebase, integration timestep, seed handling, model parameters, and deterministic output locations needed to launch a wave run.
- `model_mode=surface_wave` arms fail clearly when required local prerequisites are missing, ambiguous, or scientifically incompatible, including absent operators, incompatible coupling anchors, or unstable timestep settings for the chosen solver mode.
- The same manifest-resolution path remains shared with baseline planning so later comparison tooling can treat baseline and wave runs as sibling modes rather than separate systems.
- Regression coverage validates normalization, plan determinism, missing-prerequisite failures, and representative fixture-manifest resolution using only local artifacts.

### Verification
- `make test`
- A focused unit test that resolves a fixture manifest into `surface_wave` run plans and asserts normalized output, deterministic IDs, and clear error handling

### Notes
Assume `FW-M10-001` and the Milestone 9 planning layer are already in place. Favor one planning surface that extends the existing simulator contract rather than a parallel wave-only loader that would drift immediately. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-003 - Implement single-neuron surface-wave state containers, sparse stepping kernels, and a stability-aware integrator
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: solver core / sparse numerics / runtime

### Problem
Milestone 10 cannot begin with multi-neuron wiring if the repo still lacks the actual single-neuron wave solver. The current simulator framework has no morphology-resolved state container, no canonical sparse operator application path for surface or patch state, no stability-aware time integrator for the chosen model family, and no deterministic stepping semantics for a distributed field state. Without that core, later tickets will either duplicate low-level solver logic or couple together incomplete one-off kernels that are too opaque to trust scientifically.

### Requested Change
Implement the first working single-neuron wave-solver core in library code. Build explicit state containers for the chosen field and auxiliary state variables, add sparse operator application against the Milestone 6 assets, and implement the chosen stability-aware integration method with deterministic stepping order and inspectable runtime metadata. The implementation should support localized pulse initialization, propagation and damping on real operator bundles or fixture stand-ins, boundary handling chosen by the contract, and lightweight per-step diagnostics that later validation work can reuse.

### Acceptance Criteria
- A canonical solver API can initialize, step, and finalize a single-neuron `surface_wave` state using the repo's operator assets or deterministic fixture operators.
- The implementation uses explicit state containers for the distributed field and any auxiliary variables rather than loose dictionaries of arrays passed through the runtime.
- Sparse operator application, boundary handling, and the chosen integration method are owned by library code and expose enough metadata for a reviewer to recover the realized solver mode and timestep assumptions.
- At least one localized pulse or impulse-style smoke case demonstrates stable single-neuron propagation and decay on fixture assets in a deterministic, test-covered way.
- Regression coverage validates deterministic stepping, stable initialization and finalization behavior, and representative single-neuron propagation behavior on local fixtures.

### Verification
- `make test`
- A focused solver test that initializes a localized single-neuron wave state, steps it for several iterations, and asserts deterministic propagation and damping behavior

### Notes
Assume `FW-M10-001`, `FW-M10-002`, and the Milestone 6 operator pipeline are already in place. Keep the first solver core inspectable and boring; a reviewer should be able to see exactly which operator, timestep, and update path produced a given trajectory. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-004 - Add recovery, nonlinearity, anisotropy, and branching-aware wave mechanics with explicit guardrails
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: model dynamics / anisotropy / morphology-aware mechanics

### Problem
A purely linear propagation kernel is not enough to satisfy the roadmap's required model ingredients. Milestone 10 explicitly calls for recovery or refractory behavior, nonlinearities, optional anisotropy, and optional branching effects, yet the repo currently has no disciplined way to represent any of those in a scientifically reviewable form. If they are added ad hoc inside the step loop, the team will not be able to tell whether a changed output came from the intended model family, a hidden numerical trick, or a morphology-specific tuning loophole.

### Requested Change
Extend the wave-solver core with the additional model mechanics required by the chosen Milestone 10 family. Implement the documented recovery or refractory state evolution, the chosen nonlinearity or saturation behavior, optional anisotropy that consumes the Milestone 6 operator metadata or anisotropy settings, and a narrow but real branching-aware modifier path grounded in existing geometry descriptors rather than freeform heuristics. Make the supported combinations explicit, validate them during planning or initialization, and expose enough runtime metadata and diagnostics that later sweep and validation tooling can distinguish intended model features from disabled or identity modes.

### Acceptance Criteria
- The chosen `surface_wave` family can run with documented recovery or refractory behavior and nonlinear response enabled through normalized config rather than hidden internal constants.
- Optional anisotropy and branching-aware modifiers are real implemented modes with test coverage, while identity anisotropy and disabled branching reproduce the simpler solver behavior within documented tolerances.
- Invalid or scientifically disallowed parameter combinations fail clearly instead of silently mutating into another realized model.
- Runtime metadata records which optional mechanics were active for a run, including recovery mode, nonlinearity mode, anisotropy mode, and branching modifier mode.
- Regression coverage validates representative recovery dynamics, bounded nonlinear behavior, anisotropy identity equivalence, and at least one branch-sensitive fixture case using local assets only.

### Verification
- `make test`
- A focused solver test module that exercises recovery dynamics, nonlinear bounds, anisotropy identity behavior, and a small branch-sensitive fixture case

### Notes
Assume `FW-M10-001` through `FW-M10-003` are already in place. Keep the first branching and anisotropy extensions intentionally narrow and explicit so they remain scientifically auditable. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-005 - Integrate synaptic source injection and inter-neuron coupling so multi-neuron wave propagation is executable
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: coupling execution / source injection / circuit dynamics

### Problem
Milestone 10 is not complete when a single neuron can support a wave in isolation. The roadmap requires multi-neuron propagation, which means the engine must consume the Milestone 7 coupling bundle, sample presynaptic wave readouts, apply delays and signs deterministically, and inject the resulting source terms onto the postsynaptic state space. Right now there is no wave-side coupling executor, no canonical definition of how a presynaptic surface state becomes a postsynaptic source, and no deterministic update ordering for a coupled morphology-resolved circuit.

### Requested Change
Implement the coupling execution layer that turns Milestone 7 coupling artifacts into live inter-neuron wave sources. The implementation should resolve presynaptic sampling anchors and postsynaptic landing anchors, apply the documented delay, sign, kernel, and aggregation semantics, and inject those contributions into the wave solver through library-owned logic rather than script-local glue. Keep the update ordering deterministic, support the topology conditions already used by the simulator manifests, and make the realized coupling metadata discoverable in run outputs for later comparison and debugging.

### Acceptance Criteria
- A canonical API can construct and execute a coupled multi-neuron `surface_wave` circuit from selected roots, operator bundles, and Milestone 7 coupling assets using only local repo artifacts.
- Presynaptic readout sampling, postsynaptic source injection, delay handling, sign semantics, and aggregation are applied through library-owned coupling logic rather than reimplemented ad hoc inside runner scripts.
- The same resolved circuit, coupling assets, and seed produce the same realized injection schedule and multi-neuron state evolution deterministically.
- Missing or incompatible anchors, unusable delay metadata, or unsupported mixed-resolution combinations fail clearly instead of being silently skipped.
- Regression coverage validates deterministic multi-neuron propagation on a small fixture circuit, including at least one coupling-sensitive or delay-sensitive case.

### Verification
- `make test`
- A focused integration-style test that runs a small coupled fixture circuit and asserts deterministic inter-neuron source injection plus multi-neuron propagation behavior

### Notes
Assume `FW-M10-001` through `FW-M10-004` and the Milestone 7 coupling pipeline are already in place. The main requirement is a stable connectome-constrained wave handoff, not a one-off coupling demo. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-006 - Integrate canonical visual input streams, manifest-driven `surface_wave` execution, and shared result-bundle serialization
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: input integration / CLI / result bundles

### Problem
The milestone's done-when clause explicitly says the engine must run under actual visual input, but the repo still has no public path that executes `surface_wave` runs end to end from the experiment manifest. Without a manifest-driven execution path, the wave solver will remain an internal kernel that cannot be compared fairly against baseline mode, cannot feed the UI, and cannot prove that the same circuit and same input stream are reaching both simulator modes through a shared workflow.

### Requested Change
Extend the simulator execution entrypoint so `model_mode=surface_wave` manifest arms can run end to end using the repo's canonical local input stack. The implementation should resolve the normalized wave plan, consume the agreed input representation from the upstream visual-input milestones, execute the wave solver through the shared runtime, and write outputs into the shared simulator result-bundle layout introduced in Milestone 9. Preserve comparable readouts, provenance, logs, and UI-facing payloads so later metrics and dashboard work can switch between baseline and wave runs without reverse-engineering a second result schema.

### Acceptance Criteria
- A documented local command or script can execute `model_mode=surface_wave` manifest arms end to end using only local repo artifacts and write outputs into deterministic result-bundle paths.
- The written bundle follows the shared simulator result contract while adding the wave-specific metadata, state summaries, or snapshot references needed to interpret morphology-resolved runs.
- The same manifest and local asset identity produce reproducible `surface_wave` output locations, provenance fields, logs, and comparison-ready readouts for a given seed.
- The execution path reuses library-owned planning, runtime, and serialization helpers rather than implementing a parallel script-local output layout.
- Regression coverage includes at least one smoke-style fixture manifest run that asserts deterministic bundle identity, shared readout payloads, and discovery of wave-specific outputs.

### Verification
- `make test`
- A smoke-style fixture run that executes a `surface_wave` manifest arm and asserts deterministic result-bundle paths, summary fields, and comparison-ready payload discovery

### Notes
Assume `FW-M10-001` through `FW-M10-005`, the Milestone 9 simulator contract, and the relevant upstream local input contracts are already in place. Favor one clean public execution path over multiple partially overlapping scripts; later mixed-fidelity and analysis work should extend this workflow rather than compete with it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-007 - Ship systematic parameter sweeps, stability diagnostics, and offline wave inspection tooling
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: sweeps / validation / developer tooling

### Problem
Milestone 10 is only complete if parameters can be swept systematically and if the team can inspect whether the realized wave behavior is physically meaningful rather than numerically suspicious. Right now the repo has no standard local workflow for sweeping the new model parameters, no deterministic stability or artifact diagnostics, and no offline inspection report that shows how single-neuron and coupled wave trajectories behave over time. Without that tooling, the team will be forced to judge the engine from raw arrays or one-off notebooks, which is too weak a foundation for Milestones 12 and 13.

### Requested Change
Add a parameter-sweep and wave-inspection workflow that consumes normalized `surface_wave` plans and emits deterministic reports. The workflow should support grid or preset-based parameter exploration, repeatable seed handling, compact diagnostics for stability and artifact detection, representative state snapshots or traces, and summary metrics such as wavefront speed, damping behavior, coherence, energy-like quantities, or other contract-approved diagnostics that make the solver's behavior reviewable. Output paths should be deterministic and lightweight enough for local audit and regression testing.

### Acceptance Criteria
- A documented local command or script can run a deterministic local parameter sweep over one or more `surface_wave` plans without requiring live FlyWire access.
- The sweep outputs record the explored parameter combinations, seed context, stability or artifact flags, representative readouts, and deterministic report paths suitable for later review or comparison.
- An offline inspection report is generated in a review-friendly format such as Markdown plus images, HTML, or another lightweight local artifact that summarizes single-neuron and multi-neuron wave behavior.
- The implementation surfaces clear pass, warn, or fail conditions for obviously unstable, degenerate, or numerically suspicious runs rather than leaving every interpretation to manual inspection.
- At least one smoke-style automated test generates a fixture sweep or inspection report and asserts deterministic output paths plus expected summary fields.

### Verification
- `make test`
- A smoke-style fixture run that executes a small `surface_wave` parameter sweep and asserts deterministic report contents, summary diagnostics, and output paths

### Notes
Assume `FW-M10-001` through `FW-M10-006` are already in place. This is not the final UI; it is the local audit layer that helps Grant and Jack decide whether the engine is stable, meaningful, and ready for formal metrics work. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M10-008 - Run a Milestone 10 integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 10 roadmap 2026-03-22
- Area: verification / review / release readiness

### Problem
Even if the individual Milestone 10 build tickets land, the repo still needs one explicit integration pass that proves the wave engine is a coherent simulator mode rather than a collection of disconnected solver components. Without a dedicated readiness ticket, it is too easy to stop at isolated solver success while leaving behind manifest drift, hidden contract mismatches, weak stability checks, broken result-bundle compatibility, or undocumented gaps between the single-neuron kernel, coupled execution, visual-input integration, and sweep tooling.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 10 implementation and publish a concise readiness report in-repo. This pass should exercise the full local `surface_wave` workflow on fixture assets and at least one representative manifest path, confirm that documentation matches shipped behavior, verify that outputs remain comparison-ready for baseline mode, identify any numerical or scientific risks that remain open, and either fix those gaps directly or record them as explicit follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

### Acceptance Criteria
- The full Milestone 10 `surface_wave` workflow is executed end to end using the shipped commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across wave-model discovery, manifest planning, single-neuron solver behavior, recovery and nonlinearity modes, anisotropy and branching options, coupling execution, canonical input integration, result serialization, and parameter-sweep or inspection tooling.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 10 is ready to support downstream mixed-fidelity, metrics, validation, and UI milestones.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_10_surface_wave_engine_tickets.md --ticket-id FW-M10-008 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 10 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that `surface_wave` mode is integrated, deterministic, scientifically reviewable, and ready for downstream milestones. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
