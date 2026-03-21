Work ticket FW-M6-001: Freeze a versioned operator bundle contract and discretization design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 6 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 5 produces geometry bundles that are useful preprocessing artifacts, but they are not yet a stable numerical-operator contract. The repo has no canonical definition for which operator family is being used, which auxiliary matrices and geometry fields must be serialized, how boundary handling is represented, or how downstream code should discover coarse-versus-fine transfer structures. Without a versioned contract and an explicit design note, later simulator work will bind itself to ad hoc archive keys and undocumented mathematical assumptions.

Requested Change:
Define a first-class operator bundle contract for Milestone 6 and document the numerical design choices behind it. The implementation should centralize artifact naming and metadata in library code, extend the processed manifest so downstream consumers can discover operator assets without hardcoded filenames, and add a markdown design note that compares the viable discretization families before committing to the default. The design note should be decisive: pick the default fine-surface discretization, explain when fallback behavior is allowed, state which quantities should be conserved or damped, and record the stability-relevant assumptions the later wave engine will inherit.

Acceptance Criteria:
- Operator bundle path and metadata construction are centralized in library code rather than being reimplemented inside scripts.
- The processed manifest records an explicit operator-contract version plus per-root metadata for discretization family, normalization or mass treatment, boundary-condition mode, geodesic-neighborhood settings, and transfer-operator availability.
- A dedicated markdown design note compares graph-based and mesh-based operator families, explains the chosen default, names the fallback cases, and documents the stability-relevant properties later milestones must preserve.
- Existing geometry-bundle consumers either continue to work unchanged or a documented compatibility shim keeps current Milestone 5 workflows intact while the repo migrates.
- Regression coverage verifies deterministic contract serialization, manifest fields, and operator-bundle discovery for fixture assets.

Verification:
- `make test`
- A focused unit test that parses fixture operator metadata and asserts deterministic manifest serialization

Notes:
This ticket should land first. Keep the contract boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the operator choice.
