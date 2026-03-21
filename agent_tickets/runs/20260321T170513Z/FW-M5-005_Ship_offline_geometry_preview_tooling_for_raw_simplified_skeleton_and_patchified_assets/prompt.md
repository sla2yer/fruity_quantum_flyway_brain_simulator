Work ticket FW-M5-005: Ship offline geometry preview tooling for raw, simplified, skeleton, and patchified assets.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: Milestone 5 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 5 is not done until raw, simplified, and patchified geometry can be visualized together, but the repo currently offers no standard preview workflow for that. A developer can inspect files manually, yet there is no repeatable tool that turns a built bundle into a quick sanity-check report for a chosen subset of neurons.

Requested Change:
Add offline preview tooling that consumes already-built local geometry bundles and generates an inspection-friendly report for one or more root IDs. The tool can be a script, notebook, or small library-backed report generator, but it should standardize how the team compares raw mesh, simplified mesh, skeleton, surface graph, and patch graph views without requiring live FlyWire access.

Acceptance Criteria:
- A documented local preview workflow exists for one or more root IDs using only files produced by the pipeline.
- The preview output renders or summarizes raw mesh, simplified mesh, skeleton availability, surface graph structure, and patch graph structure in one place.
- Preview artifacts are written to a deterministic output location so they can be linked from run logs or shared during reviews.
- README or pipeline docs explain how to generate the preview and what a reviewer should look for.
- At least one smoke-style automated test covers preview generation from fixture assets.

Verification:
- `make test`
- A smoke-style test or scripted fixture run that generates preview output from local stub assets

Notes:
Assume the earlier Milestone 5 tickets have already landed. Favor a lightweight offline artifact such as HTML, Markdown plus images, or another review-friendly format that does not require interactive infrastructure to be useful.
