Work ticket FW-M6-003: Construct coarse patch operators and fine-to-coarse transfer operators that stay consistent with the fine surface.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 6 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 5's patch graph is a useful coarse partition, but it is still only a topological summary. There is no formally defined restriction or prolongation operator, no coarse mass treatment, and no guarantee that the coarse patch dynamics are meaningfully derived from the fine surface discretization rather than just sharing a vaguely similar graph shape. Without transfer operators and consistency checks, the repo cannot compare coarse and fine evolution honestly.

Requested Change:
Build the coarse operator layer as a real multiresolution discretization derived from the fine surface operator. Introduce fine-to-coarse and coarse-to-fine transfer operators, define the coarse operator assembly rule, serialize the mass or area terms needed for the coarse state, and emit comparison metrics that quantify how well coarse application matches fine application after transfer. The implementation should make it easy for later simulator code to project states between resolutions without reconstructing the math from raw patch-membership arrays.

Acceptance Criteria:
- The processed operator bundle includes first-class transfer-operator artifacts or arrays in addition to the coarse patch operator itself.
- The coarse operator is derived through a documented scheme tied to the fine discretization, rather than being assembled through an unrelated ad hoc graph rule.
- Transfer operators preserve constant fields and mass or area totals within documented tolerances for fixture meshes.
- The build step emits coarse-versus-fine comparison metrics such as transfer residuals, Rayleigh-quotient drift, or another documented quality measure appropriate to the chosen discretization.
- Regression coverage validates deterministic transfer construction, patch coverage assumptions, and coarse-versus-fine consistency on local fixture assets.

Verification:
- `make test`
- A focused fixture test that builds fine and coarse operators together, applies transfer in both directions, and asserts the documented consistency tolerances

Notes:
Assume `FW-M6-001` and `FW-M6-002` have landed. The core requirement is not just having a patch graph; it is having a coarse model that downstream code can trust as a principled reduction of the fine one.
