## OPS-004 - Failed `make review-tickets` jobs still leave misleading `stderr.log` artifacts and hide the real failure logs
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/run_review_prompt_tickets.py` / `src/flywire_wave/review_prompt_tickets.py` / review-ticket tests

### Problem
The original ticket needs refinement, not closure. The README no longer promises per-job `stderr.log` artifacts, so this is no longer a docs-contract bug. The remaining issue is operational: `run_prompt_job()` still declares `stderr.log`, but it routes child stderr into stdout and then creates an empty `stderr.log`. When specialization or review fails, `make review-tickets` exits non-zero and prints stage progress plus `Summary written to ...`, but it still does not print a final per-failure artifact summary. Operators must open `summary.json` and then chase `stdout.jsonl` by hand to find the real diagnostics.

### Evidence
- [README.md:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L133) now documents only top-level review-run outputs, so OPS-004 should no longer claim that the README advertises per-job `stderr.log`.
- [src/flywire_wave/review_prompt_tickets.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L16) still lists `stderr.log` as a standard prompt-job artifact.
- [src/flywire_wave/review_prompt_tickets.py:261](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L261), [src/flywire_wave/review_prompt_tickets.py:293](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L293), and [src/flywire_wave/review_prompt_tickets.py:309](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L309) show the runner creates `stderr.log`, launches child jobs with `stderr=subprocess.STDOUT`, and backfills an empty `stderr.log` when none exists.
- [src/flywire_wave/review_prompt_tickets.py:688](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L688) and [src/flywire_wave/review_prompt_tickets.py:689](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L689) record stage results in `summary.json`, but the console surface does not expose those artifact paths directly.
- [scripts/run_review_prompt_tickets.py:176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L176) and [scripts/run_review_prompt_tickets.py:177](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L177) only print the summary path and optional combined ticket path after the run.
- [tests/test_review_prompt_tickets.py:134](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L134) and [tests/test_review_prompt_tickets.py:253](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L253) cover successful workflow and refresh paths only, and [tests/test_run_review_prompt_tickets.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_run_review_prompt_tickets.py#L29) covers only `--dry-run`.
- Observed on April 5, 2026: running `python3 scripts/run_review_prompt_tickets.py --prompt-set efficiency_and_modularity --runner <failing-stub> --output-dir /tmp/...` exited `1`, printed only `Summary written to ...`, and left empty `specialization/efficiency_and_modularity/stderr.log` and `last_message.md` while the only failure text lived in `stdout.jsonl`.

### Requested Change
Keep scope limited to `make review-tickets`. Make the failure artifacts truthful and directly discoverable for specialization and review jobs. Either capture real child stderr separately, or stop materializing `stderr.log` and clearly document and report the combined log that actually contains diagnostics. Add an end-of-run failure summary that prints each failed prompt-set slug, stage, return code, and the exact artifact path or paths to inspect.

### Acceptance Criteria
A failed specialization or review job leaves at least one clearly named, non-empty diagnostic artifact whose filename matches the stream it actually contains.
The end-of-run console output lists every failed prompt set with its stage, return code, and the relevant artifact paths instead of only pointing to `summary.json`.
Automated coverage includes at least one failing `review-tickets` path and asserts both the non-zero exit and the failure-summary and artifact behavior.
Successful runs still write the documented review-run outputs under `agent_tickets/review_runs/<timestamp>/` without regressing combined ticket generation.

### Verification
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set efficiency_and_modularity --runner <failing-stub> --output-dir /tmp/review-tickets-fail'`.
Confirm the command exits non-zero, prints the failing prompt set, stage, return code, and artifact path or paths to inspect, and that the named diagnostic artifact is non-empty and trustworthy.
Confirm a successful run still writes `specialization/<prompt-set>/specialized_prompt.md`, `reviews/<prompt-set>/tickets.md`, `combined_tickets.md`, and `summary.json` under the chosen review-run directory.