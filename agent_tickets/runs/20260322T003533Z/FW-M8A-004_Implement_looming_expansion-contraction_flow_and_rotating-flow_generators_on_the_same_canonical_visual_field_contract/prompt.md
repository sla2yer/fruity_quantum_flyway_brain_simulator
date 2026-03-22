Work ticket FW-M8A-004: Implement looming, expansion-contraction flow, and rotating-flow generators on the same canonical visual field contract.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 8A also calls for looming stimuli plus expansion, contraction, and rotating flow, but those families are more sensitive to coordinate choices than simple translated patterns. If they are bolted on later without the same field contract, later retinal sampling and scene tooling will have to guess how centers of motion, angular velocity, radial speed, clipping, and polarity should behave. That would undermine the point of having a canonical stimulus library.

Requested Change:
Implement the canonical generator families for looming, expansion or contraction flow, and rotating flow using the same normalized field and timing conventions as the simpler generators. The implementation should support explicit motion centers, radial or angular velocity parameters, polarity, apertures or masks, looming size-growth semantics, and the metadata needed to distinguish inward versus outward or clockwise versus counterclockwise motion. Keep the resulting outputs deterministic, inspectable, and ready for later retinal sampling without hidden coordinate transforms.

Acceptance Criteria:
- Looming, expansion or contraction flow, and rotating flow are each instantiable through the canonical registry and produce deterministic replayable outputs using the shared coordinate contract.
- Each generated stimulus records the parameters required to explain the motion field, including motion center, sign or direction, velocity units, growth schedule where applicable, and clipping or aperture behavior.
- The implemented families respect the documented spatial origin, axis orientation, and temporal conventions established earlier rather than inventing family-specific coordinate systems.
- Regression coverage includes fixture cases that validate symmetry or directional sanity checks, center-of-motion behavior, and deterministic serialization or frame output.
- The implementation stays library-owned and avoids duplicating motion-field logic across CLI wrappers or one-off notebooks.

Verification:
- `make test`
- A focused fixture test suite that instantiates the radial and rotational motion families and asserts motion metadata plus deterministic sample outputs

Notes:
Assume `FW-M8A-001` through `FW-M8A-003` are already in place. Favor explicit metadata and easily auditable rendering rules over compressed or opaque representations. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
