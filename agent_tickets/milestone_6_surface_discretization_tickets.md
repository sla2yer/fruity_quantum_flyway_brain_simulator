# Milestone 6 Surface Discretization Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M6-001 - Freeze a versioned operator bundle contract and discretization design note
- Status: open
- Priority: high
- Source: Milestone 6 roadmap 2026-03-21
- Area: operators / contracts / docs

### Problem
Milestone 5 produces geometry bundles that are useful preprocessing artifacts, but they are not yet a stable numerical-operator contract. The repo has no canonical definition for which operator family is being used, which auxiliary matrices and geometry fields must be serialized, how boundary handling is represented, or how downstream code should discover coarse-versus-fine transfer structures. Without a versioned contract and an explicit design note, later simulator work will bind itself to ad hoc archive keys and undocumented mathematical assumptions.

### Requested Change
Define a first-class operator bundle contract for Milestone 6 and document the numerical design choices behind it. The implementation should centralize artifact naming and metadata in library code, extend the processed manifest so downstream consumers can discover operator assets without hardcoded filenames, and add a markdown design note that compares the viable discretization families before committing to the default. The design note should be decisive: pick the default fine-surface discretization, explain when fallback behavior is allowed, state which quantities should be conserved or damped, and record the stability-relevant assumptions the later wave engine will inherit.

### Acceptance Criteria
- Operator bundle path and metadata construction are centralized in library code rather than being reimplemented inside scripts.
- The processed manifest records an explicit operator-contract version plus per-root metadata for discretization family, normalization or mass treatment, boundary-condition mode, geodesic-neighborhood settings, and transfer-operator availability.
- A dedicated markdown design note compares graph-based and mesh-based operator families, explains the chosen default, names the fallback cases, and documents the stability-relevant properties later milestones must preserve.
- Existing geometry-bundle consumers either continue to work unchanged or a documented compatibility shim keeps current Milestone 5 workflows intact while the repo migrates.
- Regression coverage verifies deterministic contract serialization, manifest fields, and operator-bundle discovery for fixture assets.

### Verification
- `make test`
- A focused unit test that parses fixture operator metadata and asserts deterministic manifest serialization

### Notes
This ticket should land first. Keep the contract boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the operator choice.

## FW-M6-002 - Assemble fine-surface operators with geodesic neighborhoods, tangent frames, and boundary masks
- Status: open
- Priority: high
- Source: Milestone 6 roadmap 2026-03-21
- Area: fine operators / mesh numerics / sparse assembly

### Problem
The current processed surface graph is still a Milestone 5 scaffold. It exposes simplified mesh connectivity and a uniform graph Laplacian, but it does not yet provide the numerical objects Milestone 6 actually needs: geodesic neighborhoods, boundary masks, local tangent frames, metric-aware weights, or a surface operator whose supporting geometry is explicit enough to debug and validate. That leaves the repo unable to build a simulation-ready single-neuron surface state without rewriting the existing graph archive by hand.

### Requested Change
Implement the fine-surface operator builder that turns a simplified mesh bundle into a numerically meaningful fine-resolution operator artifact. Use the discretization family chosen in `FW-M6-001`, and serialize the supporting geometry needed to inspect or reuse the operator later: adjacency and edge geometry, local areas or mass terms, normals and tangent frames, geodesic-neighborhood structures, and boundary masks. Keep sparse assembly in library code, make the script layer an orchestrator only, and ensure the output is deterministic for the same mesh and config.

### Acceptance Criteria
- A first-class fine-operator artifact is written for each processed neuron bundle using only local Milestone 5 assets.
- The artifact includes the chosen surface operator matrix plus the supporting arrays needed to interpret it, including boundary masks, local frames, and neighborhood or metric data required by the selected discretization.
- The implementation exposes enough metadata to distinguish operator family, weighting scheme, orientation convention, and any mass or area normalization applied during assembly.
- Regression coverage validates structural invariants on fixture meshes, such as matrix shape, sparsity consistency, deterministic output, and expected symmetry or definiteness properties for the chosen operator family.
- The build path remains library-owned and script-thin, with no duplicate sparse-assembly logic in CLI wrappers.

### Verification
- `make test`
- A fixture-driven test suite that assembles fine operators for one or more small meshes and asserts matrix invariants plus supporting-array integrity

### Notes
Assume `FW-M6-001` is already in place. Favor inspectable sparse formats and explicit metadata over opaque archives that require reverse-engineering at read time.

## FW-M6-003 - Construct coarse patch operators and fine-to-coarse transfer operators that stay consistent with the fine surface
- Status: open
- Priority: high
- Source: Milestone 6 roadmap 2026-03-21
- Area: coarse operators / transfer maps / multiresolution numerics

### Problem
Milestone 5's patch graph is a useful coarse partition, but it is still only a topological summary. There is no formally defined restriction or prolongation operator, no coarse mass treatment, and no guarantee that the coarse patch dynamics are meaningfully derived from the fine surface discretization rather than just sharing a vaguely similar graph shape. Without transfer operators and consistency checks, the repo cannot compare coarse and fine evolution honestly.

### Requested Change
Build the coarse operator layer as a real multiresolution discretization derived from the fine surface operator. Introduce fine-to-coarse and coarse-to-fine transfer operators, define the coarse operator assembly rule, serialize the mass or area terms needed for the coarse state, and emit comparison metrics that quantify how well coarse application matches fine application after transfer. The implementation should make it easy for later simulator code to project states between resolutions without reconstructing the math from raw patch-membership arrays.

### Acceptance Criteria
- The processed operator bundle includes first-class transfer-operator artifacts or arrays in addition to the coarse patch operator itself.
- The coarse operator is derived through a documented scheme tied to the fine discretization, rather than being assembled through an unrelated ad hoc graph rule.
- Transfer operators preserve constant fields and mass or area totals within documented tolerances for fixture meshes.
- The build step emits coarse-versus-fine comparison metrics such as transfer residuals, Rayleigh-quotient drift, or another documented quality measure appropriate to the chosen discretization.
- Regression coverage validates deterministic transfer construction, patch coverage assumptions, and coarse-versus-fine consistency on local fixture assets.

### Verification
- `make test`
- A focused fixture test that builds fine and coarse operators together, applies transfer in both directions, and asserts the documented consistency tolerances

### Notes
Assume `FW-M6-001` and `FW-M6-002` have landed. The core requirement is not just having a patch graph; it is having a coarse model that downstream code can trust as a principled reduction of the fine one.

## FW-M6-004 - Add configurable boundary-condition and anisotropy plumbing to operator assembly
- Status: open
- Priority: medium
- Source: Milestone 6 roadmap 2026-03-21
- Area: operator configuration / anisotropy / boundary handling

### Problem
The roadmap explicitly calls for boundary masks and optional anisotropy tensors, but the current pipeline has no stable way to describe or assemble either. If Milestone 6 ships only a hardcoded isotropic operator with implicit boundary behavior, Milestones 10 and 13 will have to reopen the asset contract and retroactively guess how directional propagation or boundary semantics were supposed to work.

### Requested Change
Extend the operator config and assembly API so boundary-condition handling and optional anisotropy are explicit, versioned, and inspectable. Default behavior should remain simple and isotropic, but the bundle contract must reserve a clean path for directional conductivity or wave-speed modifiers expressed in local tangent coordinates. Serialize whichever coefficients or tensors are needed to reproduce the assembled operator, and document the supported modes and guardrails in repo docs.

### Acceptance Criteria
- Config and manifest plumbing expose explicit boundary-condition and anisotropy settings with stable defaults that preserve existing isotropic behavior.
- Operator metadata records the active boundary mode, anisotropy model, and any per-vertex, per-edge, or per-patch coefficients used during assembly.
- Identity anisotropy reproduces the isotropic operator exactly or within a documented numerical tolerance enforced by tests.
- At least one nontrivial anisotropic fixture case is covered by regression tests, along with boundary-handling behavior that demonstrates the implemented semantics are real rather than metadata-only.
- Documentation explains the supported anisotropy and boundary modes, their intended use, and the guardrails that keep them from becoming an arbitrary tuning escape hatch.

### Verification
- `make test`
- A targeted test module that compares isotropic and anisotropic assemblies on a fixture mesh and asserts the documented boundary-mode behavior

### Notes
Keep the first anisotropy model intentionally narrow. A diagonal tensor in the local tangent basis is enough if it creates a stable extension point without forcing a premature full constitutive-model framework.

## FW-M6-005 - Ship operator quality metrics, pulse-propagation smoke tests, and offline inspection tooling
- Status: open
- Priority: high
- Source: Milestone 6 roadmap 2026-03-21
- Area: validation / visualization / developer tooling

### Problem
Milestone 6 is only complete if the team can initialize a pulse on one neuron, verify that surface propagation behaves stably enough for later engine work, compare coarse and fine operators quantitatively, and inspect the results without digging through raw arrays. Right now there is no standard harness that exercises those numerical behaviors, no operator quality report, and no offline visualization flow for reviewing what the assembled operators are actually doing on the mesh.

### Requested Change
Add a Milestone 6 validation and inspection workflow that consumes local operator bundles and produces actionable diagnostics. The workflow should initialize localized test fields, run a lightweight stability-oriented evolution or repeated operator application suitable for pre-engine validation, compute operator quality metrics, and generate an offline report that overlays relevant outputs on the mesh and patch decomposition. The goal is not to build the final wave engine; it is to make operator quality, pulse localization, and coarse-versus-fine behavior inspectable and regression-testable before Milestone 10 begins.

### Acceptance Criteria
- A documented local command or script can generate an operator QA report for fixture assets or previously built neuron bundles without requiring FlyWire access.
- The report includes at least pulse initialization, boundary-mask inspection, coarse-versus-fine projection or reconstruction views, and a compact summary of operator quality metrics with pass, warn, or fail semantics.
- Numerical sanity checks cover the properties the design note names as stability-relevant, such as symmetry, nullspace expectations, energy behavior under the chosen smoke-test evolution, or another documented equivalent.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected output files and summary fields.
- Docs explain how this workflow should gate later Milestone 10 engine work and what a reviewer should look for when operator quality fails.

### Verification
- `make test`
- A smoke-style fixture run that produces an operator QA report and asserts the summary fields plus deterministic output paths

### Notes
Assume the earlier Milestone 6 tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that can be attached to run logs without special infrastructure.

## FW-M6-006 - Run a Milestone 6 implementation verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 6 roadmap 2026-03-21
- Area: verification / review / release readiness

### Problem
Even if the Milestone 6 build tickets land individually, the repo still needs one explicit follow-up pass that verifies the pieces work together as a coherent operator pipeline. Without a dedicated implementation-verification ticket, it is too easy to stop at local success on isolated subtasks while leaving behind contract drift, missing docs, broken report paths, weak regression coverage, or untested assumptions between fine operators, coarse operators, transfer maps, and QA tooling.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 6 implementation and publish a concise readiness report in-repo. This pass should exercise the full operator pipeline on fixture assets and at least one realistic local bundle, confirm that documentation matches the shipped behavior, identify any mismatches or scientific risks, and either close them directly or record them as follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

### Acceptance Criteria
- The full Milestone 6 workflow is executed end-to-end using the shipped commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across geometry assets, fine operators, coarse operators, transfer operators, boundary handling, anisotropy settings, and QA report generation.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 6 is ready to support Milestone 10 engine work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_6_surface_discretization_tickets.md --ticket-id FW-M6-006 --dry-run`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 6 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the milestone is integrated, documented, and ready for downstream simulator work.
