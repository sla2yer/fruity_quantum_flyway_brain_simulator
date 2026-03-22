Work ticket FW-M7-002: Build a canonical local synapse registry from per-synapse source snapshots and selected roots.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 7 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`build_registry` currently produces neuron and connectivity registries, but the connectivity table is edge-aggregated and does not retain the per-synapse locations Milestone 7 needs. There is no canonical local artifact for synapse rows, no config or provenance plumbing for synapse-level source snapshots, and no stable way to materialize a reproducible subset-scoped synapse table without depending on live FlyWire access at simulator runtime.

Requested Change:
Extend the registry layer so the repo can ingest synapse-level source snapshots into a canonical local synapse registry and keep it aligned with the selected subset. Normalize column names and dtypes, capture source provenance, and preserve the fields needed for later anchor mapping and coupling assembly, such as presynaptic and postsynaptic root IDs, synapse identifiers when available, synapse coordinates or anchorable geometry fields, neuropil context, and any neurotransmitter or sign-related source fields. The implementation should make subset-scoped synapse extraction reproducible and auditable without breaking existing neuron or connectivity registry workflows.

Acceptance Criteria:
- Config and provenance plumbing expose an explicit synapse source path plus a canonical local synapse-registry artifact owned by library code.
- The synapse loader validates a documented minimum column set and fails clearly when required localization fields are missing or malformed.
- The repo can materialize a synapse registry restricted to the active selected-root subset or another requested root set without re-querying FlyWire live.
- Existing aggregated connectivity outputs continue to work, and any new relationship between the edge-level connectivity registry and the synapse-level registry is documented and test-covered.
- Regression coverage exercises healthy fixture ingestion, malformed-source rejection, and deterministic subset extraction using local test data only.

Verification:
- `make test`
- A focused unit or integration-style test that builds a fixture synapse registry and asserts normalized fields, provenance, and subset filtering behavior

Notes:
Favor a format and loader shape that are friendly to local fixture tests and offline inspection. The key deliverable is not only having more rows; it is having a reproducible, audited local synapse table that later mapping work can trust.
