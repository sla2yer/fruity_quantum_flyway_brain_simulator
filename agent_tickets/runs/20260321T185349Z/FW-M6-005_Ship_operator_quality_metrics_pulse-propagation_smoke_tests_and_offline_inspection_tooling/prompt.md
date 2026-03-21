Work ticket FW-M6-005: Ship operator quality metrics, pulse-propagation smoke tests, and offline inspection tooling.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 6 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 6 is only complete if the team can initialize a pulse on one neuron, verify that surface propagation behaves stably enough for later engine work, compare coarse and fine operators quantitatively, and inspect the results without digging through raw arrays. Right now there is no standard harness that exercises those numerical behaviors, no operator quality report, and no offline visualization flow for reviewing what the assembled operators are actually doing on the mesh.

Requested Change:
Add a Milestone 6 validation and inspection workflow that consumes local operator bundles and produces actionable diagnostics. The workflow should initialize localized test fields, run a lightweight stability-oriented evolution or repeated operator application suitable for pre-engine validation, compute operator quality metrics, and generate an offline report that overlays relevant outputs on the mesh and patch decomposition. The goal is not to build the final wave engine; it is to make operator quality, pulse localization, and coarse-versus-fine behavior inspectable and regression-testable before Milestone 10 begins.

Acceptance Criteria:
- A documented local command or script can generate an operator QA report for fixture assets or previously built neuron bundles without requiring FlyWire access.
- The report includes at least pulse initialization, boundary-mask inspection, coarse-versus-fine projection or reconstruction views, and a compact summary of operator quality metrics with pass, warn, or fail semantics.
- Numerical sanity checks cover the properties the design note names as stability-relevant, such as symmetry, nullspace expectations, energy behavior under the chosen smoke-test evolution, or another documented equivalent.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected output files and summary fields.
- Docs explain how this workflow should gate later Milestone 10 engine work and what a reviewer should look for when operator quality fails.

Verification:
- `make test`
- A smoke-style fixture run that produces an operator QA report and asserts the summary fields plus deterministic output paths

Notes:
Assume the earlier Milestone 6 tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that can be attached to run logs without special infrastructure.
