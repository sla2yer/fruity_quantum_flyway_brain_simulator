# Milestone 17 Follow-On Tickets

This file is intentionally structured so it remains readable in Markdown and
parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M17-FOLLOW-001 - Add a browser-level smoke for packaged whole-brain context controls and showcase handoff
- Status: open
- Priority: medium
- Source: Milestone 17 readiness follow-on 2026-04-03
- Area: UI verification / browser automation

### Problem
`FW-M17-008` proves deterministic whole-brain context planning, packaging,
dashboard bridge rendering metadata, overlay semantics, summary-only fallback
behavior, and showcase-to-context handoff records from shipped local commands.
That is the right Milestone 17 readiness gate, but it still validates the
packaged HTML and JSON contract surface rather than clicking the dashboard’s
browser-rendered context controls or traversing the showcase handoff in a real
DOM runtime.

### Requested Change
Add one browser-engine smoke for the packaged Milestone 17 review surface. The
test should open a packaged dashboard session with linked whole-brain context,
switch between overview and focused context representations, apply at least one
overlay/facet interaction, and confirm that the packaged showcase handoff can
land on the reserved `showcase_handoff` preset without a backend service.

### Acceptance Criteria
- The repo has one deterministic browser-level smoke for packaged Milestone 17
  context review.
- The smoke exercises context representation switching, at least one overlay or
  facet interaction, and the showcase-to-context handoff.
- The smoke runs in CI-friendly headless mode and does not depend on live
  FlyWire access.

### Verification
- `make milestone17-readiness`
- The new browser-level smoke command or test target

### Reproduction Notes
Run `make milestone17-readiness`, then inspect the packaged dashboard and
whole-brain context bundles under
`data/processed/milestone_17_verification/simulator_results/readiness/milestone_17/generated_fixture/`.
The current readiness report proves the packaged control metadata is coherent,
but it does not yet drive those controls inside a browser engine.

## FW-M17-FOLLOW-002 - Promote the review fixture into a denser scientifically curated whole-brain context pack
- Status: open
- Priority: medium
- Source: Milestone 17 readiness follow-on 2026-04-03
- Area: fixtures / scientific curation

### Problem
The shipped Milestone 17 readiness fixture is intentionally compact and
metadata-driven so the integration gate stays deterministic and fast. It proves
contract coherence, truthfulness boundaries, richer preset packaging, optional
downstream modules, and dashboard/showcase bridge semantics, but it does not
yet claim that the broader female-brain context fixture is the final
scientifically curated review target.

### Requested Change
Add one richer whole-brain review fixture or alternate verification mode that
keeps the current fast readiness gate intact while expanding the curated review
surface. The richer pack should remain local and deterministic, but it should
cover a denser broader-brain neighborhood together with a Grant-reviewed set of
pathway highlights and downstream-module summaries.

### Acceptance Criteria
- The repo retains one fast `make milestone17-readiness` gate.
- A second richer local whole-brain review fixture or mode is available for
  deeper scientific review.
- Documentation distinguishes clearly between the minimum readiness gate and
  the broader curated review workflow.

### Verification
- `make milestone17-readiness`
- The richer whole-brain review command or test target

### Reproduction Notes
Run `make milestone17-readiness`, then inspect
`data/processed/milestone_17_verification/simulator_results/readiness/milestone_17/generated_fixture/`.
The current fixture proves deterministic M17 integration on a compact local
context graph, but it is still a reviewable engineering fixture rather than the
final scientifically curated whole-brain context pack.
