# Milestone 14 Follow-On Tickets

## FW-M14-FOLLOW-001 - Add a browser-engine smoke that drives linked dashboard controls on packaged local sessions
- Status: open
- Priority: medium
- Source: Milestone 14 readiness follow-on 2026-03-29
- Area: UI verification / browser automation

### Problem
FW-M14-008 now proves deterministic dashboard packaging, session discovery,
pane payload coherence, and export behavior from shipped local commands. That
is the right Milestone 14 readiness gate, but it still validates the packaged
HTML and JSON contract surface rather than clicking the JavaScript controls in
a real browser engine. Milestone 16 showcase mode should not rely forever on
manual browser sanity checks for linked replay, selection, and overlay controls.

### Requested Change
Add one browser-engine smoke test for the packaged offline dashboard. The test
should open the generated `app/index.html` for a representative packaged
session, change comparison mode, active overlay, selected neuron, selected
readout, and replay cursor through the real DOM controls, and confirm that the
linked pane summaries update consistently without requiring a backend service.

### Acceptance Criteria
- The repo has one deterministic browser-level smoke over a packaged Milestone
  14 session.
- The smoke exercises at least comparison-mode, overlay, neuron, readout, and
  replay-cursor updates.
- The smoke runs in CI-friendly headless mode and does not depend on live
  FlyWire access.

### Verification
- `make milestone14-readiness`
- The new browser-level smoke command or test target

### Reproduction Notes
Run `make milestone14-readiness`, then inspect the generated app shell and
bootstrap under
`data/processed/milestone_14_verification/simulator_results/readiness/milestone_14/generated_fixture/out/simulator_results/dashboard_sessions/`.
The current readiness report proves packaged control state and export paths are
coherent, but it does not yet drive those controls inside a browser engine.

## FW-M14-FOLLOW-002 - Promote the readiness fixture into a richer retinal-backed dashboard stress session
- Status: open
- Priority: medium
- Source: Milestone 14 readiness follow-on 2026-03-29
- Area: fixtures / showcase readiness

### Problem
The shipped Milestone 14 readiness fixture is intentionally compact so the
integration gate stays deterministic and fast. It proves scene, circuit,
morphology, replay, analysis, and export coherence on a small
stimulus-driven session with one shared readout and a small selected subset.
Milestone 16 showcase mode will need broader narrative pressure: denser circuit
context, richer morphology variation, and ideally a retinal-backed scene source.

### Requested Change
Add a richer Milestone 14 stress fixture or alternate verification mode that
keeps the current fast readiness gate intact while expanding the review surface
for showcase-oriented dashboard work. The richer session should remain local and
deterministic, but it should cover a denser circuit neighborhood and at least
one retinal-backed scene source.

### Acceptance Criteria
- The repo retains one fast `make milestone14-readiness` gate.
- A second richer local dashboard fixture or mode is available for deeper
  showcase-oriented review.
- Documentation distinguishes clearly between the minimum readiness gate and the
  broader showcase/stress workflow.

### Verification
- `make milestone14-readiness`
- The richer local dashboard review command or test target

### Reproduction Notes
Run `make milestone14-readiness`, then inspect
`data/processed/milestone_14_verification/simulator_results/readiness/milestone_14/generated_fixture/`.
The current fixture proves five-pane integration on a compact stimulus-driven
session, but it does not yet stress a retinal-backed scene or a larger
showcase-like circuit layout.
