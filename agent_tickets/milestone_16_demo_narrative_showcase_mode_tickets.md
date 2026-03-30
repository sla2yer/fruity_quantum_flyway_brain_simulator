# Milestone 16 Demo Narrative And Showcase Mode Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

Implementation rule for every Milestone 16 ticket:
- Before closing the ticket, add a companion rationale note at `docs/showcase_mode_notes/<ticket-id>_rationale.md`.
- That note must explain the rationale behind all material design choices, the testing strategy used, and explicitly call out what is intentionally simplified in the first version plus the clearest expansion paths for later work.

## FW-M16-001 - Freeze a versioned showcase-session contract, narrative-step taxonomy, and scientific-guardrail design note
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: contracts / docs / showcase architecture

### Problem
Milestones 14 and 15 now give the repo deterministic dashboard sessions, suite rollups, review plots, and readiness reports, but there is still no first-class software contract for the polished demo surface that Milestone 16 is supposed to deliver. Right now the roadmap names a specific seven-beat story, owned presentation mechanics such as scripted playback, saved presets, camera transitions, polished UI state, and exportable visuals, plus a scientific constraint that the highlighted effect must remain defensible rather than a misleading artifact. None of those showcase concepts currently have stable step IDs, preset identities, evidence roles, narration cue semantics, or one canonical place where Jack-owned presentation logic stops and Grant-owned scientific story selection begins. Without a versioned contract and one decisive design note, later showcase work will sprawl across dashboard state dumps, suite reports, and ad hoc export scripts that look polished while quietly drifting away from the project’s fairness boundaries.

### Requested Change
Define a library-owned Milestone 16 showcase contract and publish a concise design note that locks the narrative vocabulary. The contract should reserve one explicit `showcase_session.v1` surface with stable identifiers for showcase steps, preset IDs, transition or cue kinds, narrative annotations, evidence references, operator controls, export target roles, and presentation-status semantics. The design note should explain how showcase sessions compose with `dashboard_session.v1`, `experiment_suite.v1`, Milestone 12 analysis outputs, and Milestone 13 validation findings; it should also make the ownership boundary explicit: Jack owns scripted presentation mechanics and export surfaces, while Grant owns which scientific comparison and wave-specific phenomenon are approved for the highlighted story beat.

### Acceptance Criteria
- There is one canonical Milestone 16 showcase contract in library code with explicit identifiers for showcase step IDs, preset IDs, cue kinds, operator controls, evidence roles, and export target roles.
- The contract records deterministic discovery hooks for upstream dashboard sessions, suite-level comparison outputs, validation findings, saved narrative presets, and downstream showcase-owned artifacts without mutating earlier milestone contracts.
- A dedicated markdown design note explains the seven-step showcase flow, the fallback behavior when a requested highlight is unavailable, the handoff between presentation mechanics and scientific approval, and the invariants later showcase tickets must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 16 showcase contract sits alongside the existing dashboard and experiment-suite contracts.
- Regression coverage verifies deterministic contract serialization, stable showcase-step discovery, and normalization of representative fixture showcase metadata.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit test that builds fixture showcase-session metadata and asserts deterministic serialization plus stable showcase-step and artifact-role discovery

### Notes
This ticket should land first and give the rest of Milestone 16 a stable vocabulary. Reuse the existing dashboard, suite, analysis, and validation contract language wherever those layers already answer artifact-discovery, fairness-boundary, or reproducibility questions. Do not attempt to create a git commit as part of this ticket.

## FW-M16-002 - Build deterministic showcase planning and packaging from dashboard sessions, suite evidence, and saved presets
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: planning / packaging / narrative assembly

### Problem
Even with a locked showcase contract, Milestone 16 will stall immediately if there is no canonical way to assemble one polished demo from local artifacts. The repo can already package dashboard sessions and suite-level reports independently, but there is still no shared planner that can turn a manifest, experiment reference, dashboard-session bundle, or packaged suite output into one normalized showcase plan with stable step ordering, explicit narrative defaults, deterministic output paths, and clear failure handling when the required scientific evidence is missing. Without that assembly layer, every showcase build will rediscover artifacts differently, hardcode one handcrafted session, and silently disagree about which baseline arm, wave arm, highlighted readout, or closing analysis panel the demo is actually presenting.

### Requested Change
Add the planning and packaging layer for Milestone 16 showcase sessions. Extend the library-owned planning surface so local config plus a manifest, experiment reference, dashboard-session bundle, suite package, or explicit artifact references resolve into one deterministic showcase plan; then package that plan into the `showcase_session.v1` layout defined by `FW-M16-001`. The normalized plan should identify the scene choice, fly-view or retinal-input surface, active-subset focus targets, activity-propagation views, baseline-versus-wave pairing, approved highlight phenomenon evidence, closing analysis assets, and deterministic showcase output locations needed by the target seven-step flow. Fail clearly when required local artifacts are missing, incomparable, or scientifically unsafe, such as missing shared timebases, absent baseline or wave pairings, highlight metadata without validation evidence, or saved presets that reference unavailable geometry or overlays.

### Acceptance Criteria
- There is one canonical API that resolves local config plus manifest-, experiment-, dashboard-, suite-, or explicit-artifact inputs into a normalized showcase-session plan with stable ordering and explicit defaults.
- The normalized plan records the narrative step sequence, upstream artifact references, approved comparison arms, saved presets, highlight evidence references, operator defaults, and deterministic output locations required for Milestone 16 workflows.
- The packaging layer writes one deterministic showcase-session bundle or equivalent packaged surface that later runtime, rehearsal, and export code can consume without reparsing raw repo directories.
- Planning fails clearly when required local artifacts are missing or incompatible, including absent baseline-versus-wave pairings, missing fly-view or sampled-input assets, missing validation evidence for the nominated highlight, or unsupported preset references.
- Existing dashboard-session and experiment-suite discovery helpers remain reusable inputs to the showcase planner rather than being bypassed by a new filename-guessing implementation.
- Regression coverage validates deterministic normalization, representative fixture showcase-session assembly, override precedence, and clear failure handling for unsupported showcase requests.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused unit or integration-style test that resolves representative fixture dashboard and suite artifacts into one normalized Milestone 16 showcase-session plan and asserts deterministic ordering plus clear error handling

### Notes
Assume `FW-M16-001` plus the shipped Milestone 14 and Milestone 15 packaging layers are already in place. Favor one planning surface that runtime, rehearsal, export, and later whole-brain follow-on work can all reuse rather than a pile of script-local narrative assemblers. Do not attempt to create a git commit as part of this ticket.

## FW-M16-003 - Curate a richer showcase fixture set, narrative preset library, and evidence-backed highlight metadata
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: fixtures / presets / narrative evidence curation

### Problem
The current Milestone 14 and Milestone 15 readiness fixtures are intentionally compact so the integration gates stay deterministic and fast, but Milestone 16 needs a richer local review surface that can actually carry a persuasive story. There is still no curated preset library for scene choice, camera anchors, active-subset focus, comparison pairing, or final analysis handoff, and there is no metadata-backed way to declare which wave-specific phenomenon is approved for highlight, what evidence supports it, or which fallback explanation should appear when the preferred phenomenon is not present in a given showcase package. Without a dedicated curation layer, every later showcase run will depend on one engineer remembering a fragile sequence of manual selections that are hard to rehearse and even harder to defend scientifically.

### Requested Change
Add the first Milestone 16 showcase fixture and preset library on top of the packaged showcase-session surface. The implementation should keep the existing fast readiness gates intact while introducing one richer local showcase fixture or fixture mode that exercises the full story arc with deterministic inputs. Package stable narrative preset IDs for scene choice, fly-view framing, active-subset emphasis, propagation views, comparison pairings, highlight phenomenon references, and final analysis landing states. Highlight metadata should point back to shipped suite and validation evidence so the showcase can present a scientifically approved effect without pretending the presentation layer discovered the science on its own.

### Acceptance Criteria
- The repo retains the existing fast Milestone 14 and Milestone 15 readiness fixtures while adding at least one richer local showcase fixture or mode intended for Milestone 16 rehearsal.
- There is a stable narrative preset library with deterministic preset IDs for the key story beats in the target showcase flow.
- Highlight metadata is evidence-backed and explicit, including the nominated phenomenon ID, supporting suite or validation references, and at least one fallback path when the preferred highlight cannot be shown honestly.
- Documentation distinguishes clearly between the minimum readiness fixtures and the richer showcase fixture or rehearsal workflow.
- Regression coverage includes at least one fixture workflow that packages the richer showcase inputs and asserts deterministic preset discovery plus stable evidence references.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that packages a representative richer showcase fixture, enumerates its narrative presets, and asserts stable highlight-evidence references

### Notes
Assume `FW-M16-001` and `FW-M16-002` plus the shipped Milestone 14 and Milestone 15 readiness surfaces are already in place. This ticket should give the later runtime and polish work a deterministic rehearsal target rather than a one-off local artifact. Do not attempt to create a git commit as part of this ticket.

## FW-M16-004 - Implement the scripted showcase player, step sequencer, and operator-friendly rehearsal controls
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: showcase runtime / control flow / rehearsal UX

### Problem
Milestone 16 is specifically about turning the project into a coherent guided demo rather than a dashboard that an expert can navigate manually. There is currently no canonical showcase runtime that can load a packaged showcase session, move through the seven story beats deterministically, pause or resume without losing synchronization, or let a presenter recover gracefully if the live explanation needs to jump forward or backward. Without a real step sequencer and rehearsal control surface, the final demo will still feel like a pile of debug windows even if all the underlying artifacts are technically present.

### Requested Change
Implement the first working Milestone 16 showcase player around the packaged showcase-session surface. Build the deterministic step sequencer, operator controls, and local command workflow needed to play, pause, seek, skip, resume, and reset the narrative without desynchronizing the underlying dashboard or comparison state. The first version should stay local and deterministic rather than depending on network services. It should support both a guided autoplay mode and a presenter-controlled rehearsal mode, with clear state serialization so a session can be restarted from the same named step or preset.

### Acceptance Criteria
- One canonical runtime or command surface can load a packaged Milestone 16 showcase session and drive the target narrative flow through named steps.
- The step sequencer supports deterministic play, pause, seek, next-step, previous-step, reset, and direct jump-to-step behavior on packaged fixture sessions.
- Guided autoplay and presenter-controlled rehearsal modes share one underlying state model rather than diverging into separate implementations.
- Showcase state serialization is explicit and reusable so a rehearsal or export workflow can resume from a named preset or narrative step.
- Regression coverage validates deterministic step ordering, control-state serialization, resume behavior, and clear failure handling for unsupported step jumps or incomplete upstream session data.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that loads a representative packaged showcase session, drives the sequencer through multiple narrative controls, and asserts synchronized serialized state plus expected step transitions

### Notes
Assume `FW-M16-001` through `FW-M16-003` are already in place. Prefer one canonical local CLI or Make-backed workflow that later export and readiness tickets can reuse rather than a browser-only manual flow. Do not attempt to create a git commit as part of this ticket.

## FW-M16-005 - Add narrative-aware camera choreography, fly-view and subset emphasis, and polished showcase UI state
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: UI choreography / transitions / presentation polish

### Problem
The target showcase flow is not just a list of assets to open; it depends on visual pacing and intentional framing. Even with a packaged session and a scripted player, the demo will still feel improvised if the camera transitions are abrupt, the fly-view or sampled-input panel is not clearly tied to the chosen scene, the active subset is not emphasized at the right moment, or the presentation surface continues to expose every low-level dashboard control while the narrative is running. Without deliberate choreography and polished UI state, the story will be hard for newcomers to follow and the presentation will look like an engineer manually steering an internal tool.

### Requested Change
Implement the Milestone 16 presentation-polish layer for the first four story beats. Add deterministic camera anchors and transitions, fly-view or sampled-input framing cues, active-subset emphasis overlays, and showcase-specific UI-state rules that keep the presentation surface intentional while preserving access to the underlying dashboard when rehearsal mode needs deeper inspection. The implementation should make the scene choice, the fly-view, the active visual subset, and the wave-propagation views feel linked rather than like separate panes that happen to share data.

### Acceptance Criteria
- The packaged showcase workflow can apply deterministic camera anchors and transitions for the early narrative beats without requiring manual control twiddling.
- Fly-view or sampled-input presentation stays visibly linked to the chosen scene and the active-subset emphasis state stays coherent across the relevant panes or views.
- Showcase mode can suppress or reorganize nonessential dashboard controls while preserving a deliberate escape hatch back to the richer inspection surface for rehearsal or debugging.
- Transition timing, annotation placement, and emphasis state are preset-backed rather than hidden in ad hoc client-side constants with no metadata traceability.
- Regression coverage includes at least one fixture workflow that asserts stable camera or annotation metadata, deterministic preset application, and expected UI-mode state transitions.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused fixture workflow that applies representative showcase presets and asserts deterministic camera, annotation, and UI-state metadata for the early story beats

### Notes
Assume `FW-M16-001` through `FW-M16-004` and the shipped Milestone 14 replay semantics are already in place. Avoid a polish pass that quietly duplicates dashboard state rules; the showcase should stay a disciplined layer on top of the earlier session contracts. Do not attempt to create a git commit as part of this ticket.

## FW-M16-006 - Implement the baseline-versus-wave comparison act, the defended highlight effect, and the clean summary-analysis landing state
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: comparison storytelling / scientific evidence / summary synthesis

### Problem
The most important story beats in Milestone 16 happen after the visual setup: the demo has to compare baseline and wave mode, highlight one phenomenon unique to the wave model, and end on a clean summary analysis that supports the claim rather than hand-waving past it. The repo already has comparison-ready dashboard and suite artifacts, but there is still no dedicated showcase layer that can turn those assets into a persuasive, fairness-preserving comparison act. Without that layer, the demo risks either burying the scientific claim in too much detail or overselling a wave-specific artifact without surfacing the evidence and caveats that make the claim defensible.

### Requested Change
Implement the Milestone 16 comparison and closing-analysis workflow. Add the narrative state, presentation views, and evidence hooks needed to move from matched baseline-versus-wave comparison into one explicitly labeled wave-specific highlight effect and then into a clean summary-analysis landing state. The workflow should preserve the fairness boundary by keeping shared-comparison content visibly distinct from wave-only diagnostics and by making the highlight effect traceable to packaged suite and validation evidence. It should also provide clear fallback behavior when the nominated highlight cannot be shown honestly, such as demoting the effect to a caveated note instead of pretending the comparison succeeded.

### Acceptance Criteria
- One canonical showcase workflow can present a matched baseline-versus-wave comparison with stable pairing semantics and explicit labeling of shared-comparison versus wave-only content.
- The highlight-effect surface is evidence-backed, traceable to packaged suite and validation artifacts, and includes explicit caveat or fallback behavior when the preferred effect is unavailable or inconclusive.
- The final summary-analysis landing state presents a clean, newcomer-readable closing view that points back to the underlying evidence rather than becoming a disconnected slide.
- Comparison and highlight presentation fail clearly when the current showcase session lacks a compatible pair, a shared timebase, or approved evidence for the nominated wave-specific effect.
- Regression coverage includes at least one fixture workflow that asserts deterministic comparison metadata, stable evidence linkage, and expected fallback handling for a missing or rejected highlight effect.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A focused integration-style test that drives a representative packaged showcase session through comparison mode, highlight presentation, and final summary-analysis landing state while asserting stable evidence references and fairness-boundary labeling

### Notes
Assume `FW-M16-001` through `FW-M16-005` and the shipped Milestone 12 through Milestone 15 evidence surfaces are already in place. This ticket is where the “why the wave version matters” story becomes concrete, so keep the scientific caveats explicit rather than smoothing them away for presentation polish. Do not attempt to create a git commit as part of this ticket.

## FW-M16-007 - Ship deterministic export, capture, and presenter workflow commands for stills, replay media, and saved rehearsals
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: export tooling / runbooks / presenter operations

### Problem
Jack explicitly owns exportable visuals for this milestone, but the repo still has no one-command presenter workflow that turns the polished showcase into reproducible stills, replay-oriented media, or named rehearsal states. Even if the runtime, choreography, and comparison story all exist, the milestone is still incomplete until the team can build the showcase, rehearse it, export assets for a hackathon presentation, and recover from local environment differences without rediscovering a brittle sequence of UI steps every time. Without deterministic export and presenter operations, the final demo will remain difficult to share, difficult to rehearse, and hard to trust under time pressure.

### Requested Change
Add the Milestone 16 export and presenter-operations workflow. The implementation should expose one documented local command surface for building, opening, rehearsing, and exporting showcase sessions from packaged local artifacts, together with deterministic output locations for still images, replay-oriented media such as frame sequences or video, and saved rehearsal states. Publish a concise presenter runbook that explains the expected commands, the fallback path when the richest local mode is unavailable, and how exported artifacts trace back to the underlying showcase-session metadata.

### Acceptance Criteria
- There is one documented local workflow for building, opening, rehearsing, and exporting a Milestone 16 showcase session from packaged local artifacts.
- The export layer can generate deterministic still images, metrics or metadata exports, and at least one replay-oriented media path such as a frame sequence or video-oriented artifact set.
- Saved rehearsal states or presets are discoverable and reloadable through documented commands rather than being hidden in temporary browser storage.
- Exported artifacts are metadata-backed and traceable to the underlying showcase-session bundle, narrative preset, and evidence references.
- Regression coverage includes at least one fixture workflow that exercises the documented build or export surface and asserts deterministic artifact paths plus expected summary metadata.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- A smoke-style fixture workflow that builds a representative showcase session, exercises at least one rehearsal-state save or reload path, and asserts deterministic still-image plus replay-oriented export discovery

### Notes
Assume `FW-M16-001` through `FW-M16-006` are already in place. Prefer Make-backed wrappers and local scripts that fit the repo’s existing command surface, for example one canonical showcase CLI plus repo wrappers for build, open, export, and later readiness verification. Do not attempt to create a git commit as part of this ticket.

## FW-M16-008 - Run a Milestone 16 integration verification pass and publish a showcase readiness report
- Status: open
- Priority: high
- Source: Milestone 16 roadmap 2026-03-30
- Area: verification / readiness / showcase audit

### Problem
Even if the individual Milestone 16 tickets land, the repo still needs one explicit integration pass proving that the polished demo is a coherent, scientifically defensible capability rather than a stack of disconnected presets and export helpers. Without a dedicated readiness ticket, it will be too easy to stop at a nice-looking autoplay path while leaving behind hidden contract mismatches, broken preset references, misleading highlight effects, export paths that only work on one hand-crafted machine, or a summary-analysis ending that no longer matches the underlying evidence. Milestone 17 whole-brain context work should not start until the core showcase spine is trustworthy.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 16 implementation and publish a concise readiness report in-repo. The pass should exercise the full local showcase workflow end to end on fixture artifacts and at least one representative packaged dashboard or suite-driven showcase path, verify that the declared contract matches shipped behavior across planning, preset packaging, scripted playback, camera choreography, comparison flow, highlight evidence, summary-analysis landing, and export behavior, and record any remaining product, scientific, or engineering risks that later context-expansion work must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

### Acceptance Criteria
- The full Milestone 16 showcase workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across showcase-session planning, richer fixture or preset packaging, scripted playback, camera and annotation choreography, baseline-versus-wave comparison, highlight-evidence presentation, summary-analysis landing state, and export workflow behavior.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 16 is ready to support external demo use and Milestone 17 follow-on context work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 16 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/showcase_mode_notes/FW-M16-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_16_demo_narrative_showcase_mode_tickets.md --ticket-id FW-M16-008 --dry-run --runner true`
- A documented end-to-end local Milestone 16 showcase command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 16 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the demo is deterministic, understandable to newcomers, presentation-ready, and still honest about the evidence it is built on. Do not attempt to create a git commit as part of this ticket.
