# Milestone 7 Synapse Coupling Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M7-001 - Freeze a versioned synapse asset contract and inter-neuron coupling design note
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: coupling contracts / manifests / docs

### Problem
The repo currently stops at per-neuron geometry and operator bundles plus an aggregated connectivity registry. Milestone 7 needs a first-class handoff contract for synapse-level data and inter-neuron coupling artifacts, but there is no canonical definition for where synapse-derived assets live, how downstream code discovers them, how coupling topology is encoded, or how sign, delay, aggregation, and morphology fallback decisions are documented. Without a versioned contract and a decisive design note, later simulator and UI work will bind itself to ad hoc filenames, undocumented semantics, and incompatible assumptions about what a "coupling edge" means.

### Requested Change
Define a first-class synapse and coupling contract for Milestone 7 and document the design choices behind it. Centralize asset naming and manifest metadata in library code, extend the processed manifest so downstream consumers can discover the local synapse registry plus any per-root or per-edge coupling artifacts without hardcoded paths, and add a markdown design note that compares the viable coupling-topology families before committing to the default. The design note should be decisive: choose the default among point-to-point, patch-to-patch, and distributed patch-cloud coupling, define the fallback hierarchy for surface, skeleton, and point-neuron representations, and state how sign, delay, missing geometry, and multi-synapse aggregation must be represented for later simulator code.

### Acceptance Criteria
- Synapse and coupling path construction is centralized in library code rather than being reimplemented inside scripts.
- The processed manifest records an explicit synapse-contract or coupling-contract version plus discoverable pointers to the local synapse registry, anchor-map artifacts, coupling bundles, and the design-note version they conform to.
- A dedicated markdown design note compares the supported coupling-topology families, chooses the default, names the supported fallback modes, and documents the invariants later milestones must preserve when consuming the coupling bundle.
- `docs/pipeline_notes.md` is updated so the Milestone 7 contract sits alongside the existing geometry and operator contracts.
- Regression coverage verifies deterministic contract serialization, manifest discovery, and compatibility for existing geometry or operator consumers that should continue to work unchanged.

### Verification
- `make test`
- A focused unit test that builds fixture synapse or coupling metadata and asserts deterministic manifest serialization plus bundle discovery

### Notes
This ticket should land first. Keep the contract boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the coupling model.

## FW-M7-002 - Build a canonical local synapse registry from per-synapse source snapshots and selected roots
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: registry / synapse ingestion / provenance

### Problem
`build_registry` currently produces neuron and connectivity registries, but the connectivity table is edge-aggregated and does not retain the per-synapse locations Milestone 7 needs. There is no canonical local artifact for synapse rows, no config or provenance plumbing for synapse-level source snapshots, and no stable way to materialize a reproducible subset-scoped synapse table without depending on live FlyWire access at simulator runtime.

### Requested Change
Extend the registry layer so the repo can ingest synapse-level source snapshots into a canonical local synapse registry and keep it aligned with the selected subset. Normalize column names and dtypes, capture source provenance, and preserve the fields needed for later anchor mapping and coupling assembly, such as presynaptic and postsynaptic root IDs, synapse identifiers when available, synapse coordinates or anchorable geometry fields, neuropil context, and any neurotransmitter or sign-related source fields. The implementation should make subset-scoped synapse extraction reproducible and auditable without breaking existing neuron or connectivity registry workflows.

### Acceptance Criteria
- Config and provenance plumbing expose an explicit synapse source path plus a canonical local synapse-registry artifact owned by library code.
- The synapse loader validates a documented minimum column set and fails clearly when required localization fields are missing or malformed.
- The repo can materialize a synapse registry restricted to the active selected-root subset or another requested root set without re-querying FlyWire live.
- Existing aggregated connectivity outputs continue to work, and any new relationship between the edge-level connectivity registry and the synapse-level registry is documented and test-covered.
- Regression coverage exercises healthy fixture ingestion, malformed-source rejection, and deterministic subset extraction using local test data only.

### Verification
- `make test`
- A focused unit or integration-style test that builds a fixture synapse registry and asserts normalized fields, provenance, and subset filtering behavior

### Notes
Favor a format and loader shape that are friendly to local fixture tests and offline inspection. The key deliverable is not only having more rows; it is having a reproducible, audited local synapse table that later mapping work can trust.

## FW-M7-003 - Map synapse locations onto surface patches and skeleton anchors with deterministic fallback metadata
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: anchor mapping / geometry / lookup structures

### Problem
Milestone 6 gives the repo per-neuron geometry, patch, and operator bundles, but nothing yet translates synapse locations into addresses on those state spaces. The roadmap explicitly calls for locating nearest patches or skeleton nodes and building fast lookup structures, yet the repo has no artifact or API that says where a postsynaptic landing sits on the receiving surface, where a presynaptic readout should be sampled, or how mapping quality and fallback decisions should be recorded when surface geometry is missing or unsuitable.

### Requested Change
Implement the synapse-anchor mapping layer that consumes the local synapse registry plus geometry bundles and emits deterministic lookup artifacts. Postsynaptic synapses should map to receiving-surface anchors using the default resolution chosen in `FW-M7-001`, while presynaptic sites should map to the corresponding readout anchors on the source neuron. The implementation must support the documented fallback hierarchy for surface, skeleton, and point-neuron representations, serialize mapping distances and residuals, and provide fast query helpers for common access patterns such as inbound synapses to a root, outbound synapses from a root, and all mapped synapses for one edge.

### Acceptance Criteria
- A first-class mapping artifact or sidecar is written for the mapped roots or edges and is discoverable from the manifest or coupling contract.
- Each mapped synapse records presynaptic and postsynaptic anchor information, chosen anchor type and resolution, mapping quality metrics, and any fallback or blocked-prerequisite reason.
- Library helpers support efficient edge-level and root-level lookups without requiring downstream simulator code to scan the entire raw synapse table.
- Missing or low-quality mappings surface as structured statuses rather than silent drops, and those statuses are documented.
- Regression coverage validates deterministic mapping behavior on fixture meshes, plus at least one fallback case that uses a skeleton or reduced anchor when a surface anchor is unavailable.

### Verification
- `make test`
- A fixture-driven test that maps synthetic synapses onto a small mesh and optional skeleton and asserts anchor assignments, lookup outputs, and fallback metadata

### Notes
Assume `FW-M7-001` and `FW-M7-002` have landed. Keep the raw nearest-neighbor mechanics inspectable and deterministic; later physics work will only be credible if the localization layer is easy to audit.

## FW-M7-004 - Assemble versioned inter-neuron coupling bundles with configurable kernels, delays, signs, and aggregation rules
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: coupling assembly / config / simulator handoff

### Problem
Even with synapse rows and anchor maps in place, the repo would still lack the actual object Milestone 7 promises: a simulator-readable definition of how activity transfers between neurons. There is no versioned bundle that captures which presynaptic anchors are read, which postsynaptic anchors are driven, whether the transfer is point-like or distributed, how synaptic sign is represented, how delays are computed, how multiple synapses on one edge aggregate, or how those rules should modify downstream surface state.

### Requested Change
Build the coupling assembly layer that turns mapped synapses into versioned inter-neuron coupling bundles. Use the topology mode, kernel family, and fallback rules chosen in `FW-M7-001`; group mapped synapses by edge; apply configurable sign handling, delay models, and aggregation rules; and emit a coupling artifact that downstream simulator code can consume without reverse-engineering raw synapse rows. Keep the bundle library-owned and script-thin, and make the configuration explicit enough that later baseline and wave simulators can share the same coupling metadata even if they interpret it differently.

### Acceptance Criteria
- A first-class coupling bundle artifact is written for each relevant edge or root pair using the canonical contract rather than ad hoc filenames.
- The bundle records presynaptic readout anchors, postsynaptic landing anchors, coupling-topology mode, kernel family, sign semantics, delay model, aggregation rule, and any normalization or weight totals needed to reproduce the transfer.
- Config plumbing exposes stable defaults while still allowing the supported coupling topology, sign, delay, and aggregation modes to be chosen explicitly and recorded in metadata.
- Downstream code can discover and load the bundle through library helpers instead of reconstructing coupling from raw synapse rows or implicit script conventions.
- Regression coverage validates deterministic bundle serialization plus the implemented semantics for sign handling, delay assignment, and multiple-synapse aggregation on fixture edges.

### Verification
- `make test`
- A focused fixture test that assembles one or more edge-level coupling bundles and asserts payload invariants, deterministic serialization, and the documented sign or delay semantics

### Notes
Assume `FW-M7-001` through `FW-M7-003` are already in place. The main requirement is not merely having another archive; it is having a coupling handoff that later simulator work can treat as a stable, inspectable contract.

## FW-M7-005 - Ship offline coupling inspection and QA tooling so any connectome edge can be visualized and audited
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: validation / visualization / developer tooling

### Problem
Milestone 7 is only complete if any edge can be inspected and visualized, but the repo currently has no standard workflow for reviewing mapped synapses or inter-neuron transfers offline. A developer could manually open registries and bundle archives, yet there is no repeatable report that shows where an edge reads from the presynaptic neuron, where it lands on the postsynaptic state space, how many synapses were aggregated, what delays or signs were assigned, or whether mapping quality is trustworthy enough for later simulator work.

### Requested Change
Add an offline coupling inspection and QA workflow that consumes local synapse registries, anchor maps, geometry or operator bundles, and coupling artifacts to produce review-friendly reports. The workflow should support inspecting a single edge or a small selected set of edges, render the presynaptic readout and postsynaptic landing geometry in a deterministic output directory, summarize aggregation and delay statistics, and emit compact pass, warn, or fail checks for mapping coverage and coupling integrity. The goal is not to build the full UI; it is to make the Milestone 7 handoff inspectable and regression-testable before simulator work begins.

### Acceptance Criteria
- A documented local command or script can generate a coupling inspection report for one edge or a small edge set using only local cached artifacts and no FlyWire access.
- The report includes at least an edge summary, mapped-synapse or aggregate-landing visualization, presynaptic readout summary, aggregation statistics, delay or sign summary, and coupling QA flags.
- Output paths are deterministic so reports can be attached to run logs or compared across runs.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected summary fields and output files.
- Docs explain how the report should be used to review Milestone 7 outputs and what a reviewer should look for when mapping coverage or coupling quality fails.

### Verification
- `make test`
- A smoke-style fixture run that generates a coupling inspection report and asserts the summary fields plus deterministic output paths

### Notes
Assume the earlier Milestone 7 tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that does not require interactive infrastructure to be useful.

## FW-M7-006 - Run a Milestone 7 integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 7 roadmap 2026-03-21
- Area: verification / review / release readiness

### Problem
Even if the Milestone 7 build tickets land individually, the repo still needs one explicit integration pass that verifies the pieces work together as a coherent synapse-to-coupling pipeline. Without a dedicated verification ticket, it is too easy to stop at local success on isolated subtasks while leaving behind contract drift, partial manifest updates, broken inspection paths, weak regression coverage, or mismatches between synapse ingestion, anchor mapping, coupling assembly, and the documentation that later simulator milestones will rely on.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 7 implementation and publish a concise readiness report in-repo. This pass should exercise the full local workflow on fixture assets and at least one realistic cached subset, confirm that documentation matches shipped behavior, identify any mismatches or scientific risks, and either close them directly or record them as follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

### Acceptance Criteria
- The full Milestone 7 workflow is executed end-to-end using the shipped commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across the synapse registry, anchor mapping artifacts, coupling bundles, inspection tooling, manifest discovery, and fallback behavior for mixed morphology classes.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 7 is ready to support downstream simulator and input-stack work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_7_synapse_coupling_tickets.md --ticket-id FW-M7-006 --dry-run`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 7 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the synapse-to-coupling milestone is integrated, documented, and ready for downstream simulator work.
