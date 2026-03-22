Work ticket FW-M8A-006: Ship deterministic stimulus recording, replay, and offline preview tooling for reusable bundles.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The milestone’s done-when clause explicitly says stimuli must be recordable and replayable, but the repo currently has no standard workflow that turns a resolved stimulus spec into a reusable local artifact. A developer could rerun the generator code manually, yet there is no deterministic output directory, no static preview artifact, no replay harness, and no guarantee that "the same stimulus" today will still mean the same thing when Milestone 8B or later experiment runs depend on it.

Requested Change:
Add a script-thin recording and replay workflow that consumes a canonical stimulus spec, writes a reusable local stimulus bundle, and generates an offline preview artifact. The workflow should serialize the metadata needed for exact reuse, persist either the canonical cached frame sequence or the documented hybrid representation chosen in `FW-M8A-001`, and provide a replay path that can drive later retinal or experiment code without recomputing semantics ad hoc. Output paths should be deterministic, and the preview should make it easy to inspect timing and spatial content for one or more representative frames.

Acceptance Criteria:
- A documented local command or script can build a reusable stimulus bundle from config or manifest input and replay it offline with no live external dependencies.
- The output location is deterministic for the resolved stimulus identity, making bundles easy to cache, diff, and reference from later pipeline steps.
- The bundle includes enough metadata to reproduce the stimulus exactly, including timing, normalized parameters, contract version, and whichever cached data the chosen representation model requires.
- A static preview artifact is generated in a review-friendly format such as Markdown plus images, HTML, or another lightweight offline format.
- At least one smoke-style automated test generates a fixture stimulus bundle twice and asserts deterministic metadata, replay behavior, and preview output paths.

Verification:
- `make test`
- A smoke-style fixture run that records and replays one or more canonical stimuli and asserts deterministic bundle contents plus preview outputs

Notes:
Assume `FW-M8A-001` through `FW-M8A-005` are already in place. Keep the workflow lightweight and local-first so later milestones can depend on cached stimulus assets without needing a heavier rendering stack. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
