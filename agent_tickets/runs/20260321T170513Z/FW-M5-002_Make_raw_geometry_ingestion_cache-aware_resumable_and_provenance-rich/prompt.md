Work ticket FW-M5-002: Make raw geometry ingestion cache-aware, resumable, and provenance-rich.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 5 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`scripts/02_fetch_meshes.py` always behaves like a one-shot downloader. It does not clearly separate cache hits from fresh downloads, it does not record structured per-neuron fetch provenance, and optional skeleton failures collapse to `None` without leaving behind enough information for a later rebuild or audit. That makes large subset fetches brittle and expensive to rerun.

Requested Change:
Upgrade raw geometry ingestion so it can skip valid cached assets, refetch stale or corrupt ones, and record a structured fetch status per root ID. Treat mesh fetches as required, skeleton fetches as optional-but-audited, and capture enough provenance to explain what happened during a run without reading console logs. The implementation should support resumable ingestion and make repeated executions cheap by default.

Acceptance Criteria:
- Re-running the fetch step against already downloaded valid assets reports cache hits and avoids unnecessary re-downloads by default.
- The fetch layer can explicitly refetch assets when requested through config or CLI controls.
- Per-root raw-asset provenance records whether mesh and skeleton fetches were fetched, reused from cache, skipped, or failed, along with enough context to diagnose the reason.
- Zero-byte, malformed, or otherwise invalid cached files are detected and do not silently count as healthy cache hits.
- Regression coverage exercises cache-hit, forced-refetch, and optional-skeleton-failure scenarios using local stubs rather than live FlyWire access.

Verification:
- `make test`
- A targeted unit test suite for `scripts/02_fetch_meshes.py` or the underlying library functions that covers cache reuse and corrupted-cache recovery

Notes:
Assume `FW-M5-001` is already in place so raw-asset provenance has a stable home in the manifest or bundle layout. Be careful not to turn skeleton failures into hard failures unless the config explicitly says skeletons are required.
