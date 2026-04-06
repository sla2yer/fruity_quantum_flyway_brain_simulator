Review work ticket OVR-002: Collapse duplicate CLI-runner orchestration in the review tooling.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

This is a ticket review pass only. Do not implement code.
Earlier backlog tickets may already have changed the surrounding code.
Check whether this ticket is still accurate for the repository's current state and update it if needed.

Rules:
- Keep the same ticket ID.
- Return exactly one ticket in the same markdown ticket format.
- Update the title, priority, area, and sections if the ticket needs refinement.
- If the ticket no longer needs implementation, set `- Status: closed` and explain why.
- Do not create new tickets or broaden this ticket into a larger backlog item.
- Return only the updated single-ticket markdown and do not use code fences.

Existing Ticket:
## OVR-002 - Collapse duplicate CLI-runner orchestration in the review tooling
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: `agent_tickets` / `review_prompt_tickets`

### Problem
The repo carries two near-identical subprocess wrappers for Codex/Codel jobs: one for agent tickets and one for review-prompt jobs. The only real extension point here is runner selection, which is already centralized. Maintaining two staging/streaming/artifact-sync implementations adds ceremony without adding a second meaningful backend.

### Evidence
- [src/flywire_wave/agent_tickets.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L299) and [src/flywire_wave/review_prompt_tickets.py:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L154) both create temp staging dirs, build the same `runner exec --json --cd ... --sandbox ... --output-last-message ...` command, stream output through [src/flywire_wave/agent_tickets.py:224](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L224), and return the same artifact paths.
- Artifact syncing is duplicated in [src/flywire_wave/agent_tickets.py:287](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L287) and [src/flywire_wave/review_prompt_tickets.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L142).
- The review flow at [src/flywire_wave/review_prompt_tickets.py:335](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L335) exists only to run the repo’s `review-tickets` path from [Makefile:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L133), not to support a distinct job-execution platform.

### Requested Change
Introduce one shared CLI prompt-job executor and let both ticket execution and review-prompt execution compose it. Keep the specialization/review sequencing logic, but remove the duplicated subprocess/staging/artifact code.

### Acceptance Criteria
- Only one implementation owns subprocess spawning, stream handling, and artifact-sync for CLI-backed prompt jobs.
- `run_ticket()` and the review workflow still emit the same prompt/stdout/stderr/last-message artifacts and summaries.
- Existing ticket and review tests still pass.

### Verification
- `make test`
- `make smoke`
