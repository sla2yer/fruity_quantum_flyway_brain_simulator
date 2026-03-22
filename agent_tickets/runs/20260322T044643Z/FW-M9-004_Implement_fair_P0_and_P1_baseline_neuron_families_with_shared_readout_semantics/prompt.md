Work ticket FW-M9-004: Implement fair P0 and P1 baseline neuron families with shared readout semantics.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The Milestone 1 design lock explicitly names `P0` and `P1`, but the repo still has no actual implementation of either baseline family. There is no library-owned equation set, parameter schema, update rule, normalization convention, or shared readout mapping for the canonical point baseline versus the stronger reduced baseline. Without concrete `P0` and `P1` implementations, later comparisons to `surface_wave` will either be scientifically vague or will drift into script-local one-off baselines that nobody can audit fairly.

Requested Change:
Implement the baseline neuron-family layer that instantiates the canonical `P0` and `P1` models described by the design lock. `P0` should realize the passive leaky linear non-spiking single-compartment baseline, while `P1` should realize the stronger reduced baseline with explicit synaptic integration current or explicit delay structure chosen in `FW-M9-001`. Expose the realized state variables and readout mapping explicitly so downstream metrics compare fair, shared observables rather than apples to oranges.

Acceptance Criteria:
- There is one canonical API that resolves normalized model specs into executable `P0` and `P1` neuron-family implementations.
- `P0` and `P1` use documented, test-covered update equations and parameter semantics rather than hidden heuristics or hardcoded constants in runner code.
- The implementation exposes shared readout extraction so baseline runs can report the same observable family that later `surface_wave` runs will be compared against.
- Invalid, ambiguous, or scientifically disallowed parameterizations fail clearly instead of silently mutating into a different model family.
- Regression coverage validates representative steady-state, impulse-response, and parameter-normalization behavior for both baseline families using local fixtures only.

Verification:
- `make test`
- A focused unit test that instantiates fixture `P0` and `P1` models, steps them under simple drives, and asserts deterministic responses plus shared readout behavior

Notes:
Assume `FW-M9-001` through `FW-M9-003` are already in place. Keep the baseline fair and explicit: the point of this ticket is not maximal biological richness, but a credible comparison family that later reviewers can audit quickly. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
