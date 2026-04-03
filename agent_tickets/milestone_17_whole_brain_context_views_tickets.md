# Milestone 17 Whole-Brain Context View Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

Implementation rule for every Milestone 17 ticket:
- Before closing the ticket, add a companion rationale note at `docs/whole_brain_context_notes/<ticket-id>_rationale.md`.
- That note must explain the rationale behind all material design choices, the testing strategy used, and explicitly call out what is intentionally simplified in the first version plus the clearest expansion paths for later work.

## FW-M17-001 - Freeze a versioned whole-brain-context session contract, query taxonomy, and context-view design note
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: contracts / docs / context-view architecture

### Problem
Milestones 14 through 16 now give the repo deterministic dashboard sessions, showcase sessions, bundle discovery, and a compact connectivity context around the active visual subset, but there is still no first-class software contract for the larger female-brain context view that Milestone 17 is supposed to add. Right now the roadmap names whole-brain connectivity context views, upstream and downstream graph overlays, context-only nodes, and optional simplified downstream readout modules, yet none of those concepts have stable query IDs, node-role semantics, overlay identities, graph-budget rules, or one canonical place where Jack-owned UI and query mechanics stop and Grant-owned scientific pathway selection begins. Without a versioned contract and one decisive design note, later whole-brain work will sprawl across ad hoc graph exports, dashboard-only JSON patches, and one-off showcase presets that quietly disagree about what counts as active, context-only, pathway-relevant, or intentionally out of scope.

### Requested Change
Define a library-owned Milestone 17 context-view contract and publish a concise design note that locks the vocabulary. The contract should reserve one explicit `whole_brain_context_session.v1` surface with stable identifiers for query profile IDs, node and edge role IDs, context-layer IDs, overlay IDs, graph-budget or reduction profile IDs, metadata facet IDs, and optional downstream-module role IDs. The design note should explain how whole-brain context sessions compose with subset-selection outputs, the local synapse registry, `dashboard_session.v1`, and `showcase_session.v1`, while making the ownership boundary explicit: Jack owns deterministic context packaging, scalable UI semantics, and linked interaction mechanics, while Grant owns which broader relationships and downstream pathways are scientifically worth surfacing.

### Acceptance Criteria
- There is one canonical Milestone 17 context-view contract in library code with explicit identifiers for query profiles, node roles, edge roles, reduction profiles, overlay IDs, metadata facets, and optional downstream-module roles.
- The contract records deterministic discovery hooks for upstream subset-selection artifacts, local registry or synapse inputs, packaged dashboard sessions, packaged showcase sessions, and downstream context-view-owned artifacts without mutating earlier milestone contracts.
- The contract makes the active-versus-context boundary explicit, including stable semantics for active selected nodes, context-only nodes, pathway-highlight nodes, and optional downstream-module records.
- A dedicated markdown design note explains the default local delivery model, query taxonomy, graph-budget expectations, fairness or truthfulness boundaries, and which invariants later Milestone 17 tickets must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 17 context-view contract sits alongside the existing dashboard and showcase contracts.
- Regression coverage verifies deterministic contract serialization, stable query-profile and node-role discovery, and normalization of representative fixture whole-brain-context metadata.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit test that builds fixture whole-brain-context metadata and asserts deterministic serialization plus stable query-profile, overlay, and node-role discovery

### Notes
This ticket should land first and give the rest of Milestone 17 a stable vocabulary. Reuse the existing dashboard-session and showcase-session contract language wherever those layers already answer artifact-discovery, replay-state, or fairness-boundary questions. Do not attempt to create a git commit as part of this ticket.

## FW-M17-002 - Build deterministic whole-brain-context planning and packaging from subset, registry, dashboard, and showcase artifacts
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: planning / packaging / artifact composition

### Problem
Even with a locked context-view contract, Milestone 17 will stall immediately if there is no canonical way to assemble one larger-brain context session from local artifacts. The repo can already package subset manifests, dashboard sessions, and showcase sessions independently, but there is still no shared planner that can take a manifest, selection preset, packaged dashboard session, packaged showcase session, or explicit artifact references and normalize them into one context-view plan with stable query ordering, deterministic output paths, explicit defaults, and clear failure handling when the required registry or synapse evidence is missing. Without that planning layer, every whole-brain review will rediscover the active anchors differently, hardcode a local context radius, and silently disagree about which upstream and downstream relationships are actually being shown.

### Requested Change
Add the planning and packaging layer for Milestone 17 context sessions. Extend the library-owned planning surface so local config plus a manifest-, subset-, dashboard-, showcase-, or explicit-artifact input resolves into one deterministic `whole_brain_context_session.v1` plan. The normalized plan should identify the active subset anchors, selected query profiles, graph-budget profile, registry and synapse sources, active-versus-context labeling rules, optional downstream-module requests, linked dashboard or showcase references, and deterministic context-session output locations. Fail clearly when required local artifacts are missing, incompatible, or ambiguous, such as absent active-root resolution, missing local synapse registry inputs, unsupported query-profile combinations, dashboard sessions that reference a different active subset, or showcase sessions whose selected subset cannot be traced back to local context inputs.

### Acceptance Criteria
- There is one canonical API that resolves local config plus manifest-, subset-, dashboard-, showcase-, or explicit-artifact inputs into a normalized Milestone 17 context-session plan with stable ordering and explicit defaults.
- The normalized plan records active anchors, selected query profiles, reduction budgets, metadata facet requests, optional downstream-module requests, linked upstream session references, and deterministic output locations required for Milestone 17 workflows.
- The packaging layer writes one deterministic context-session bundle or equivalent packaged surface that later query execution, dashboard UI, showcase handoff, and export code can consume without rescanning raw repo directories.
- Planning fails clearly when required local artifacts are missing or incompatible, including absent active-root identities, missing registry or synapse data, unsupported query-profile combinations, or dashboard or showcase references that do not match the resolved active subset.
- Existing subset, dashboard-session, and showcase-session discovery helpers remain reusable inputs to the context planner rather than being bypassed by a new filename-guessing implementation.
- Regression coverage validates deterministic normalization, representative fixture context-session assembly, override precedence, and clear failure handling for unsupported whole-brain-context requests.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit or integration-style test that resolves representative fixture subset, dashboard, or showcase artifacts into one normalized Milestone 17 context-session plan and asserts deterministic ordering plus clear error handling

### Notes
Assume `FW-M17-001` plus the shipped Milestone 4, Milestone 14, and Milestone 16 packaging layers are already in place. Favor one planning surface that the context query engine, dashboard shell, showcase presets, and later export or readiness work can all reuse rather than a pile of script-local context assemblers. Do not attempt to create a git commit as part of this ticket.

## FW-M17-003 - Implement the whole-brain context-query engine, reduction profiles, and scalable graph payload assembly
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: graph queries / reduction logic / scalable payloads

### Problem
Milestone 17 explicitly calls for whole-brain connectivity context views plus upstream and downstream overlays, but the repo still has no deterministic query engine that can derive those views from the local metadata surfaces it already owns. The current dashboard circuit context is intentionally compact and subset-centered. There is no canonical way to execute bounded upstream or downstream traversals, rank context-only nodes, build focused path overlays, or reduce larger graph neighborhoods into reviewable payloads that stay truthful without exploding into an unreadable whole-brain hairball. Without a shared query and reduction layer, every later view will either be too small to answer the milestone or too large to be useful.

### Requested Change
Implement the library-owned context-query engine for Milestone 17. The engine should consume a normalized context-session plan plus local registry and synapse inputs, execute deterministic upstream or downstream traversals, and assemble scalable graph payloads for overview, focused-subgraph, and pathway-highlight use cases. Support explicit reduction profiles, such as hop limits, node-count budgets, edge-ranking policies, neuropil or cell-class filters, and pathway-focused extracts, while keeping active selected nodes visibly distinct from context-only nodes. The first version should stay local and metadata-driven rather than attempting live FlyWire queries, whole-brain meshing, or full interactive graph-database behavior.

### Acceptance Criteria
- There is one canonical local query API that executes deterministic upstream, downstream, and mixed context queries from a normalized Milestone 17 context-session plan.
- The implementation supports explicit reduction controls, including hop limits, node-count budgets, edge- or synapse-ranking policies, and at least one pathway-focused extraction mode.
- The resulting graph payloads preserve stable node and edge identities, active-versus-context labeling, and enough metadata for later dashboard and showcase surfaces to render overview and focused views without re-querying raw source files.
- Query execution fails clearly when required inputs are missing or when a requested query cannot be realized within the declared contract rules.
- Regression coverage includes representative fixture queries for upstream, downstream, and pathway-focused context plus deterministic ranking or reduction behavior.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- Focused fixture-driven tests that execute representative Milestone 17 context queries and assert deterministic node or edge ordering, reduction behavior, and clear failure handling

### Notes
Assume `FW-M17-001` and `FW-M17-002` are already in place. Keep the first query engine boring and inspectable: deterministic local graph extraction is more valuable here than introducing live services, speculative caching layers, or a maximal graph-visualization stack. Do not attempt to create a git commit as part of this ticket.

## FW-M17-004 - Curate a richer whole-brain context fixture set, query-profile presets, and review-oriented packaging paths
- Status: completed
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: fixtures / presets / review workflows

### Problem
The shipped dashboard and showcase fixtures are intentionally compact so readiness gates stay deterministic and fast, but Milestone 17 needs a richer local review surface that can actually stress larger context queries. There is still no curated fixture or alternate mode that packages the active visual subset together with a meaningful broader context graph, no stable preset IDs for common upstream and downstream review questions, and no clear distinction between the minimum fast gate versus the richer local workflow a reviewer should use when evaluating whole-brain context behavior. Without a dedicated curation layer, later Milestone 17 work will depend on fragile hand-built local artifacts that are difficult to compare or reproduce.

### Requested Change
Add the first Milestone 17 context fixture and query-preset library on top of the packaged context-session surface. Keep the existing fast readiness gates intact while introducing at least one richer local context fixture or alternate mode that exercises a broader graph neighborhood. Package stable preset IDs for overview, upstream halo, downstream halo, pathway-focus, and dashboard or showcase handoff states. The fixture should stay local and deterministic, and documentation should make it obvious which fixture path is the compact gate versus the richer whole-brain review path.

### Acceptance Criteria
- The repo retains the existing fast dashboard or showcase readiness fixtures while adding at least one richer local whole-brain-context fixture or mode intended for Milestone 17 review.
- There is a stable query-preset library with deterministic preset IDs for overview, upstream, downstream, pathway-focus, and handoff-oriented context views.
- Documentation distinguishes clearly between the minimum readiness fixtures and the richer Milestone 17 review workflow.
- The richer fixture packages enough context metadata and graph payload breadth to exercise context-only nodes, directional overlays, and at least one pathway-focused review case.
- Regression coverage includes at least one fixture workflow that packages the richer context inputs and asserts deterministic preset discovery plus stable graph-payload references.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that packages a representative richer Milestone 17 context fixture, enumerates its query presets, and asserts stable graph-payload and metadata references

### Notes
Assume `FW-M17-001` through `FW-M17-003` plus the shipped Milestone 14 and Milestone 16 fixture surfaces are already in place. This ticket should give the later UI and showcase handoff work a deterministic review target rather than a one-off local graph export. Do not attempt to create a git commit as part of this ticket.

## FW-M17-005 - Extend the dashboard circuit experience with scalable whole-brain context representations, context-only nodes, and linked inspection
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: dashboard UX / circuit views / linked state

### Problem
Milestone 14 already introduced the circuit pane and linked neuron inspection, but that pane is still fundamentally a compact subset-context view. Milestone 17 needs the active visual circuit to sit inside a larger female-brain context without bloating the simulator or overwhelming the reviewer. There is currently no canonical dashboard experience that can load a packaged whole-brain-context session, render context-only nodes distinctly from the active simulated subset, switch between overview and focused context representations, and keep selections linked to the existing morphology, time-series, analysis, and showcase-ready state models. Without that extension, the milestone remains only a back-end graph exercise.

### Requested Change
Extend the dashboard-owned circuit experience to consume packaged whole-brain-context sessions and render scalable context representations. The implementation should support at least one larger overview representation plus one focused subgraph or pathway representation, visibly distinguish active selected nodes from context-only nodes, and keep linked neuron selection or hover semantics coherent with the existing dashboard session model. The first version may stay within the self-contained static-app architecture rather than introducing a new service, but it must make the context story understandable without resorting to raw JSON inspection.

### Acceptance Criteria
- One canonical dashboard workflow can load a packaged Milestone 17 context session and render at least one overview context representation plus one focused context representation.
- Active selected nodes, context-only nodes, and highlighted pathway nodes remain visibly distinct and traceable through packaged metadata rather than ad hoc client-side heuristics.
- Linked selection and hover behavior stays coherent with the existing dashboard state model and propagates cleanly into morphology, time-series, and analysis surfaces where applicable.
- The dashboard handles unavailable or oversized context payloads honestly, for example by degrading to summary cards or focused extracts instead of pretending the full graph rendered successfully.
- Regression coverage includes at least one fixture workflow that exercises context-view rendering metadata, context-only-node styling state, and linked inspection behavior.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused smoke or integration-style test that loads a representative packaged Milestone 17 context session, applies linked inspection actions, and asserts stable overview or focused-view metadata plus clear unavailable-state handling

### Notes
Assume `FW-M17-001` through `FW-M17-004` and the shipped Milestone 14 dashboard shell are already in place. Preserve the existing self-contained local app model unless a stronger reason emerges in the design note; Milestone 17 is about better context, not a platform rewrite. Do not attempt to create a git commit as part of this ticket.

## FW-M17-006 - Add upstream and downstream graph overlays, metadata facets, and active-to-context pathway explanation workflows
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: overlays / metadata linking / pathway explanation

### Problem
The roadmap calls out upstream and downstream graph overlays plus linking the active subset to whole-brain metadata, but the repo still has no dedicated explanation layer that can turn the packaged context graph into something interpretable. Even with a dashboard-capable view, reviewers will still struggle if they cannot switch among upstream and downstream overlays, filter by meaningful metadata facets such as cell class or neuropil, or follow a highlighted path from the active subset to a broader context target without losing track of what is simulated versus context-only. Without explicit overlay and explanation workflows, the larger graph will be present but not legible.

### Requested Change
Implement the Milestone 17 overlay and pathway-explanation layer. Add deterministic overlay IDs and interaction flows for upstream emphasis, downstream emphasis, bidirectional context, metadata-facet filtering, and at least one active-to-context pathway explanation mode. Package the supporting summary metadata so the UI and showcase layers can render not just nodes and edges, but also reviewer-readable explanations of why a highlighted context relationship appears, what metadata facet grouped it, and whether the relationship is part of the active simulator subset or a context-only extension.

### Acceptance Criteria
- The packaged Milestone 17 workflow supports explicit upstream, downstream, and mixed-context overlays together with at least one pathway-explanation mode.
- Metadata-facet filtering is deterministic and traceable, with at least cell-class and neuropil-style facet support or equivalent local metadata categories already present in the repo.
- The overlay and explanation layer keeps the active-versus-context boundary explicit so context-only relationships are not silently presented as simulated dynamics.
- The implementation records enough packaged summary metadata for reviewer-readable captions, counts, or explanation cards rather than forcing the UI to reconstruct meaning from raw graph topology alone.
- Regression coverage includes at least one fixture workflow that exercises overlay switching, metadata-facet filtering, and pathway explanation metadata while asserting deterministic output.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused fixture workflow that applies representative Milestone 17 overlays and facet filters, then asserts deterministic pathway-explanation metadata and expected active-versus-context labeling

### Notes
Assume `FW-M17-001` through `FW-M17-005` are already in place. Favor explanations that make the graph easier to trust and discuss, even if the first version uses disciplined captions, counts, and highlighted extracts rather than a maximal interactive analytics surface. Do not attempt to create a git commit as part of this ticket.

## FW-M17-007 - Implement optional simplified downstream readout modules and showcase-aware context handoff
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: downstream modules / showcase integration / scientific interpretation

### Problem
Milestone 17 explicitly allows optional simplified downstream readout modules, but the repo still has no canonical way to represent that idea without overpromising biological detail or violating the fairness boundaries established in earlier milestones. There is no shared software surface for declaring which downstream modules are simplified summaries, which are just context-oriented interpretation aids, how they connect back to the active subset and larger graph, or how the Milestone 16 showcase should hand off into a Milestone 17 context view without feeling like a disconnected side quest. Without a disciplined downstream-module layer, this part of the milestone risks either being skipped or turning into an uncontrolled new decoder stack.

### Requested Change
Add the optional simplified downstream-module layer for Milestone 17 together with a showcase-aware handoff surface. The implementation should define one canonical way to package simplified downstream targets or module summaries as context-view artifacts, keep them explicitly labeled as simplified and optional, and connect them back to the active subset, the packaged context graph, and any relevant dashboard or showcase presets. The first version should stay conservative: a small number of metadata-backed downstream summary modules is preferable to an ambitious but under-specified new simulation layer.

### Acceptance Criteria
- There is one canonical software surface for optional simplified downstream-module records inside the packaged Milestone 17 context workflow.
- Downstream modules are explicitly labeled as simplified, optional, and context-oriented rather than being presented as new fully simulated biological claims.
- The implementation packages enough metadata to trace each downstream module back to the active subset anchors, the relevant context query or pathway, and any linked dashboard or showcase preset.
- The Milestone 16 showcase workflow or preset library can hand off cleanly into at least one Milestone 17 context view without duplicating context-query logic in the showcase layer.
- Regression coverage includes at least one fixture workflow that packages representative simplified downstream-module metadata and asserts deterministic showcase or dashboard handoff references.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that packages representative simplified downstream-module metadata, resolves a showcase-aware handoff or preset, and asserts stable lineage plus explicit simplification labels

### Notes
Assume `FW-M17-001` through `FW-M17-006`, the shipped Milestone 12 shared-readout semantics, and the Milestone 16 showcase packaging surfaces are already in place. Keep the first downstream-module layer honest and narrow: context-oriented summaries are in scope, a stealth Milestone 18 simulator expansion is not. Do not attempt to create a git commit as part of this ticket.

## FW-M17-008 - Run a Milestone 17 integration verification pass and publish a whole-brain-context readiness report
- Status: open
- Priority: high
- Source: Milestone 17 roadmap 2026-03-30
- Area: verification / readiness / context-view audit

### Problem
Even if the individual Milestone 17 tickets land, the repo still needs one explicit integration pass proving that whole-brain context is now a coherent, deterministic, reviewable capability rather than a pile of graph extracts and UI affordances. Without a dedicated readiness ticket, it will be too easy to stop at local query success or one attractive overview while leaving behind contract mismatches, broken preset references, misleading context-only labeling, oversized payload failure cases, weak showcase handoff semantics, or optional downstream modules that no longer trace back to the packaged context graph. This milestone should end with confidence that the active visual circuit can really be placed in larger brain context without bloating the simulator.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 17 implementation and publish a concise readiness report in-repo. The pass should exercise the full local whole-brain-context workflow end to end on fixture artifacts and at least one representative dashboard- or showcase-driven context path, verify that the declared contract matches shipped behavior across context-session planning, query execution, reduction profiles, richer fixture packaging, scalable dashboard views, overlay and pathway explanations, optional downstream-module packaging, and showcase handoff behavior, and record any remaining scientific or engineering risks that later milestones must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 17 context workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across context-session planning, deterministic query execution, reduction-profile behavior, richer context-fixture packaging, scalable dashboard rendering, overlay and pathway explanation semantics, optional downstream-module packaging, and showcase handoff behavior.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 17 is ready to support broader scientific review and later follow-on work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 17 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/whole_brain_context_notes/FW-M17-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_17_whole_brain_context_views_tickets.md --ticket-id FW-M17-008 --dry-run --runner true`
- A documented end-to-end local Milestone 17 context-view command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 17 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the active visual subset now sits inside a larger female-brain context through deterministic local workflows, explicit truthfulness boundaries, and reviewable artifacts rather than simulator bloat. Do not attempt to create a git commit as part of this ticket.
