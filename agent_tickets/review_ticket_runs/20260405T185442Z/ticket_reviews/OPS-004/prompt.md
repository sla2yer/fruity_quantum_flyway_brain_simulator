Review work ticket OPS-004: `make review-tickets` leaves failed prompt jobs without a trustworthy error artifact.
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
## OPS-004 - `make review-tickets` leaves failed prompt jobs without a trustworthy error artifact
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/run_review_prompt_tickets.py` / `src/flywire_wave/review_prompt_tickets.py`

### Problem
The review-ticket runner advertises per-job artifacts including `stderr.log`, but the implementation merges child stderr into stdout and then writes an empty `stderr.log`. On failure, the top-level script only prints the summary path, so operators still have to dig through JSON to discover which prompt set failed and which log file actually has the diagnostics.

### Evidence
- [README.md:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L133) documents the review-run artifact layout as an operator-facing surface.
- [src/flywire_wave/review_prompt_tickets.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L16) declares `stderr.log` as a standard artifact.
- [src/flywire_wave/review_prompt_tickets.py:199](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L199) launches child jobs with `stderr=subprocess.STDOUT`, and [src/flywire_wave/review_prompt_tickets.py:219](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L219) creates an empty `stderr.log` if none exists.
- [scripts/run_review_prompt_tickets.py:176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L176) only prints the summary path and optional combined ticket path after the run, not the failing prompt-set log paths.
- [tests/test_review_prompt_tickets.py:74](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L74) and [tests/test_run_review_prompt_tickets.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_run_review_prompt_tickets.py#L29) only cover fake successful jobs and dry-run; the real failure-triage path is untested.

### Requested Change
Make the failure artifacts honest and directly discoverable. Either capture real child stderr separately, or stop advertising `stderr.log` and point operators to the actual combined log. Also print a short end-of-run failure summary listing the failed prompt-set slugs and the exact artifact paths to inspect.

### Acceptance Criteria
A failed specialization or review job leaves at least one non-empty, clearly named error artifact for that prompt set.
The end-of-run console output lists failed prompt sets and the relevant `stdout.jsonl`, `stderr.log`, or `last_message.md` paths.
Automated coverage includes a failing runner path rather than only dry-run and fake-success cases.

### Verification
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set error_handling_and_operability --runner <failing-stub>'`.
Confirm that the command exits non-zero, prints the failed prompt-set slug and artifact paths, and leaves a non-empty error artifact for that failed job.
Confirm that a successful run still writes the documented review artifacts under `agent_tickets/review_runs/<timestamp>/`.

## file_length_and_cohesion

# File Length And Cohesion Review Tickets
