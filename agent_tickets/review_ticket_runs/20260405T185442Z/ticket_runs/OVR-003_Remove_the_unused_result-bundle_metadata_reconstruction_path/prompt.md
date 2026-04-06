Work ticket OVR-003: Remove the unused result-bundle metadata reconstruction path.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: overengineering_and_abstraction_load review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original ticket target is now too broad and slightly misplaced. Top-level manifest execution no longer reconstructs bundle metadata itself, but simulator packaging still supports a second "partial arm plan" shape where `result_bundle.metadata` is missing and must be rebuilt from loose arm-plan fields. Current repo-owned planners always materialize normalized bundle metadata, and downstream consumers already assume that normalized shape directly. Keeping the packaging fallback preserves an unused second source of truth for bundle ids, artifact paths, and processed-results-dir resolution in the baseline and surface-wave manifest execution path.

Requested Change:
Require normalized `arm_plan.result_bundle.metadata` in manifest execution packaging and remove the fallback metadata reconstruction branch. Missing bundle metadata should raise a targeted error instead of synthesizing a second metadata representation from `manifest_reference`, `arm_reference`, `determinism`, `selected_assets`, and runtime fields. Keep this scoped to metadata reconstruction; low-level helpers that only tolerate an absent `result_bundle.reference` are out of scope unless they also rebuild metadata.

Acceptance Criteria:
- Manifest-driven packaging requires normalized `arm_plan.result_bundle.metadata`.
- Result packaging no longer rebuilds simulator-result bundle metadata from loose arm-plan fields.
- Missing bundle metadata fails clearly and early.
- Baseline and surface-wave manifest runs preserve the same `bundle_id`, `run_spec_hash`, and artifact paths recorded in planner-produced `result_bundle.reference` / `result_bundle.metadata`.

Verification:
- `make test`
- `make milestone9-readiness`
- `make milestone10-readiness`
