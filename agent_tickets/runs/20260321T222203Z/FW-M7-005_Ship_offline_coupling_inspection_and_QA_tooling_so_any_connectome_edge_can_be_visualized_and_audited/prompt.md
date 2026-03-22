Work ticket FW-M7-005: Ship offline coupling inspection and QA tooling so any connectome edge can be visualized and audited.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 7 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 7 is only complete if any edge can be inspected and visualized, but the repo currently has no standard workflow for reviewing mapped synapses or inter-neuron transfers offline. A developer could manually open registries and bundle archives, yet there is no repeatable report that shows where an edge reads from the presynaptic neuron, where it lands on the postsynaptic state space, how many synapses were aggregated, what delays or signs were assigned, or whether mapping quality is trustworthy enough for later simulator work.

Requested Change:
Add an offline coupling inspection and QA workflow that consumes local synapse registries, anchor maps, geometry or operator bundles, and coupling artifacts to produce review-friendly reports. The workflow should support inspecting a single edge or a small selected set of edges, render the presynaptic readout and postsynaptic landing geometry in a deterministic output directory, summarize aggregation and delay statistics, and emit compact pass, warn, or fail checks for mapping coverage and coupling integrity. The goal is not to build the full UI; it is to make the Milestone 7 handoff inspectable and regression-testable before simulator work begins.

Acceptance Criteria:
- A documented local command or script can generate a coupling inspection report for one edge or a small edge set using only local cached artifacts and no FlyWire access.
- The report includes at least an edge summary, mapped-synapse or aggregate-landing visualization, presynaptic readout summary, aggregation statistics, delay or sign summary, and coupling QA flags.
- Output paths are deterministic so reports can be attached to run logs or compared across runs.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected summary fields and output files.
- Docs explain how the report should be used to review Milestone 7 outputs and what a reviewer should look for when mapping coverage or coupling quality fails.

Verification:
- `make test`
- A smoke-style fixture run that generates a coupling inspection report and asserts the summary fields plus deterministic output paths

Notes:
Assume the earlier Milestone 7 tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that does not require interactive infrastructure to be useful.
