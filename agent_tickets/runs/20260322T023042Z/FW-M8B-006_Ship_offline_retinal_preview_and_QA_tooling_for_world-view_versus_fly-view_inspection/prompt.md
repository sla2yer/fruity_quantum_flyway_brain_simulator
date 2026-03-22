Work ticket FW-M8B-006: Ship offline retinal preview and QA tooling for world-view versus fly-view inspection.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The milestone’s done-when clause explicitly says you should be able to visualize both the world scene and the sampled fly-view representation, but the repo currently has no standard offline inspection workflow for that. A developer could dump arrays manually, yet there is no deterministic report that shows the source view, lattice or detector coverage, the sampled retinal representation, timing context, or whether the sampler is behaving plausibly enough for later simulator and UI work.

Requested Change:
Add an offline retinal preview and QA workflow that consumes a source stimulus or scene plus a retinal bundle and emits a review-friendly report. The workflow should render the world-facing input alongside the fly-view or sampled representation, make the detector layout or sampling lattice inspectable, summarize key metadata such as field of view and timing, and surface compact pass, warn, or fail checks for obvious problems such as missing coverage, inconsistent frame counts, or invalid detector values. The goal is not to build the final UI; it is to make Milestone 8B outputs inspectable and auditable before deeper simulator work begins.

Acceptance Criteria:
- A documented local command or script can generate a retinal inspection report for one source input and retinal bundle using only local cached artifacts.
- The report includes at least a world-view preview, a fly-view or sampled retinal representation, detector or lattice layout context, timing or frame summary, and QA flags.
- Output paths are deterministic so reports can be attached to run logs or compared across runs.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected summary fields and output files.
- Docs explain how the report should be used to review Milestone 8B outputs and what a reviewer should look for when retinal coverage or sampling quality fails.

Verification:
- `make test`
- A smoke-style fixture run that generates a retinal inspection report and asserts summary fields plus deterministic output paths

Notes:
Assume the earlier Milestone 8B tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that does not require interactive infrastructure to be useful. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
