Work ticket APICPL-003: Geometry manifest `_coupling_contract` is sampled from the lowest sorted root's `coupling_bundle` instead of manifest inputs.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: api_boundaries_and_coupling review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The manifest-level coupling header is no longer sensitive to dict insertion order, because roots are sorted numerically before sampling. But it is still synthesized from exactly one per-root `coupling_bundle`: the lowest root ID that has one. That makes the global contract depend on sampled per-root metadata instead of explicit manifest-owned inputs. Because the header builder reconstructs `processed_coupling_dir` from that sampled bundle's `local_synapse_registry.path`, stale or mixed per-root coupling metadata can silently override the caller-provided coupling directory and rewrite the manifest-wide registry path/status that simulation planning treats as authoritative.

Requested Change:
Make `_coupling_contract` a manifest-owned record derived from explicit manifest inputs. The manifest writer should not infer the global `local_synapse_registry` location/status from a sampled root bundle, and an explicit `processed_coupling_dir` must not be overridden by per-root metadata. If per-root `coupling_bundle.assets.local_synapse_registry` entries disagree with the manifest-wide coupling location or readiness status, fail manifest construction with a clear error instead of serializing the lowest root's bundle into the header.

Acceptance Criteria:
- `_coupling_contract.local_synapse_registry.path` is derived from explicit manifest input when `processed_coupling_dir` is supplied, even if per-root `coupling_bundle_metadata` is present.
- Adding or removing a lower-root record with stale `coupling_bundle.assets.local_synapse_registry` metadata does not rewrite the manifest-wide coupling header.
- Conflicting per-root `local_synapse_registry` path or status values cause geometry manifest writing to fail clearly.
- Regression coverage includes a multi-root manifest with conflicting bundle metadata and a case where sampled bundle metadata disagrees with the explicit `processed_coupling_dir`.

Verification:
`python3 -m unittest tests.test_geometry_contract -v`; `python3 -m unittest tests.test_coupling_contract -v`; `python3 -m unittest tests.test_simulation_planning -v`
