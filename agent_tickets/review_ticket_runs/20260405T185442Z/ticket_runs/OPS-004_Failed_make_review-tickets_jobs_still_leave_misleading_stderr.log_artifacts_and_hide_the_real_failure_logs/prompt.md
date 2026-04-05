Work ticket OPS-004: Failed `make review-tickets` jobs still leave misleading `stderr.log` artifacts and hide the real failure logs.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: error_handling_and_operability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original ticket needs refinement, not closure. The README no longer promises per-job `stderr.log` artifacts, so this is no longer a docs-contract bug. The remaining issue is operational: `run_prompt_job()` still declares `stderr.log`, but it routes child stderr into stdout and then creates an empty `stderr.log`. When specialization or review fails, `make review-tickets` exits non-zero and prints stage progress plus `Summary written to ...`, but it still does not print a final per-failure artifact summary. Operators must open `summary.json` and then chase `stdout.jsonl` by hand to find the real diagnostics.

Requested Change:
Keep scope limited to `make review-tickets`. Make the failure artifacts truthful and directly discoverable for specialization and review jobs. Either capture real child stderr separately, or stop materializing `stderr.log` and clearly document and report the combined log that actually contains diagnostics. Add an end-of-run failure summary that prints each failed prompt-set slug, stage, return code, and the exact artifact path or paths to inspect.

Acceptance Criteria:
A failed specialization or review job leaves at least one clearly named, non-empty diagnostic artifact whose filename matches the stream it actually contains.
The end-of-run console output lists every failed prompt set with its stage, return code, and the relevant artifact paths instead of only pointing to `summary.json`.
Automated coverage includes at least one failing `review-tickets` path and asserts both the non-zero exit and the failure-summary and artifact behavior.
Successful runs still write the documented review-run outputs under `agent_tickets/review_runs/<timestamp>/` without regressing combined ticket generation.

Verification:
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set efficiency_and_modularity --runner <failing-stub> --output-dir /tmp/review-tickets-fail'`.
Confirm the command exits non-zero, prints the failing prompt set, stage, return code, and artifact path or paths to inspect, and that the named diagnostic artifact is non-empty and trustworthy.
Confirm a successful run still writes `specialization/<prompt-set>/specialized_prompt.md`, `reviews/<prompt-set>/tickets.md`, `combined_tickets.md`, and `summary.json` under the chosen review-run directory.
