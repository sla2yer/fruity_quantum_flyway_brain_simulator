Work ticket FW-M8B-005: Integrate the retinal sampler with canonical stimulus playback and scene-generator entrypoints.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 8B is not complete if the sampler only works as an isolated Python call. The roadmap explicitly says the same scene should be convertible into retinal input frames consistently, and Milestone 8C will expect a clean handoff into scene playback. Right now there is no script-thin entrypoint that loads a canonical Milestone 8A stimulus bundle or a Milestone 8C scene description, applies the retinal config, and writes a reusable retinal bundle in a deterministic place.

Requested Change:
Add the pipeline and playback integration layer that drives the retinal sampler from canonical visual sources. The implementation should accept a canonical stimulus or scene entrypoint, resolve the required camera or fly pose metadata, invoke the retinal sampling and bundling APIs, and write a reusable retinal bundle whose identity is stable for the same source plus retinal configuration. Keep the workflow local-first and deterministic so later experiment manifests and simulator runs can depend on cached retinal assets instead of replaying world semantics ad hoc.

Acceptance Criteria:
- A documented local command or script can build a retinal bundle from a canonical stimulus or scene input using only local repo artifacts.
- The output location is deterministic for the resolved source visual input plus retinal configuration, making retinal bundles easy to cache, diff, and reference from later pipeline steps.
- The integration path works through library-owned resolution and sampling APIs rather than reimplementing config parsing or projection logic inside scripts.
- The resulting metadata records the upstream source bundle or scene identity so retinal assets remain traceable back to the world-space input that generated them.
- Regression coverage exercises at least one fixture stimulus path and one fixture scene-like path, asserting deterministic bundle identity and replay behavior.

Verification:
- `make test`
- A smoke-style fixture run that records retinal bundles from representative canonical stimulus or scene inputs and asserts deterministic output paths plus metadata lineage

Notes:
Assume the earlier Milestone 8B tickets have landed and that Milestone 8A provides a canonical stimulus entrypoint. Design the public workflow so Milestone 8C can plug into it cleanly rather than inventing a second retinal-sampling path. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
