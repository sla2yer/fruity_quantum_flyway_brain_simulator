Work ticket FW-M6-004: Add configurable boundary-condition and anisotropy plumbing to operator assembly.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: Milestone 6 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The roadmap explicitly calls for boundary masks and optional anisotropy tensors, but the current pipeline has no stable way to describe or assemble either. If Milestone 6 ships only a hardcoded isotropic operator with implicit boundary behavior, Milestones 10 and 13 will have to reopen the asset contract and retroactively guess how directional propagation or boundary semantics were supposed to work.

Requested Change:
Extend the operator config and assembly API so boundary-condition handling and optional anisotropy are explicit, versioned, and inspectable. Default behavior should remain simple and isotropic, but the bundle contract must reserve a clean path for directional conductivity or wave-speed modifiers expressed in local tangent coordinates. Serialize whichever coefficients or tensors are needed to reproduce the assembled operator, and document the supported modes and guardrails in repo docs.

Acceptance Criteria:
- Config and manifest plumbing expose explicit boundary-condition and anisotropy settings with stable defaults that preserve existing isotropic behavior.
- Operator metadata records the active boundary mode, anisotropy model, and any per-vertex, per-edge, or per-patch coefficients used during assembly.
- Identity anisotropy reproduces the isotropic operator exactly or within a documented numerical tolerance enforced by tests.
- At least one nontrivial anisotropic fixture case is covered by regression tests, along with boundary-handling behavior that demonstrates the implemented semantics are real rather than metadata-only.
- Documentation explains the supported anisotropy and boundary modes, their intended use, and the guardrails that keep them from becoming an arbitrary tuning escape hatch.

Verification:
- `make test`
- A targeted test module that compares isotropic and anisotropic assemblies on a fixture mesh and asserts the documented boundary-mode behavior

Notes:
Keep the first anisotropy model intentionally narrow. A diagonal tensor in the local tangent basis is enough if it creates a stable extension point without forcing a premature full constitutive-model framework.
