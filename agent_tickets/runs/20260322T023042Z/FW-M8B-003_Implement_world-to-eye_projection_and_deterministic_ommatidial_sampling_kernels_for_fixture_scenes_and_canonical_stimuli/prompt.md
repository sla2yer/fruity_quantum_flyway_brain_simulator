Work ticket FW-M8B-003: Implement world-to-eye projection and deterministic ommatidial sampling kernels for fixture scenes and canonical stimuli.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even with a lattice spec, Milestone 8B still lacks the actual physics-facing step that turns a world-space visual field into detector responses. The repo has no canonical projection code that evaluates a scene or stimulus from the fly’s viewpoint, applies the chosen sampling kernel or acceptance model, and produces stable per-ommatidium values. Without that, the same moving edge or scene could be interpreted differently by each downstream consumer, which would break the milestone’s requirement that the same scene convert into retinal input consistently.

Requested Change:
Implement the retinal projection and sampling layer that consumes the normalized eye or lattice spec plus a world-facing visual source and emits deterministic per-detector samples. Support the chosen default sampling model from `FW-M8B-001`, make field-of-view and out-of-bounds behavior explicit, and ensure the implementation can consume both fixture scenes and the canonical Milestone 8A stimulus representations without special-case code in each caller. Favor vectorized or cached evaluation paths so repeated frame generation does not require obviously wasteful per-detector Python loops.

Acceptance Criteria:
- A canonical API can evaluate a world-facing visual source into deterministic per-ommatidium samples using the supported eye or lattice spec.
- The sampling implementation records the realized projection or kernel settings, including any field-of-view clipping, background fill, acceptance-angle semantics, and per-eye handling required to reproduce the result.
- The same source stimulus or scene plus the same retinal config always produces the same sampled detector values and metadata.
- The implementation is structured for efficient repeated frame generation rather than ad hoc one-off projection calls.
- Regression coverage validates deterministic sampling behavior on small fixture scenes or analytic stimulus cases, including at least one boundary or out-of-field case.

Verification:
- `make test`
- A focused fixture-driven test that projects a small synthetic visual field or canonical stimulus into detector samples and asserts deterministic outputs plus boundary behavior

Notes:
Assume `FW-M8B-001` and `FW-M8B-002` have landed. Keep the math inspectable and deterministic; later simulator work will only be credible if reviewers can audit how world-space brightness becomes detector-level input. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
