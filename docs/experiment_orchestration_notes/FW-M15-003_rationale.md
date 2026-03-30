# FW-M15-003 Rationale

## Design Choices

This ticket adds one library-owned runner module,
`flywire_wave.experiment_suite_execution`, instead of pushing Milestone 15
resume logic into shell scripts or into the existing Milestone 9 through 14
stage libraries.

The runner treats the normalized suite plan from `FW-M15-002` as the only
source of suite intent, then derives a second deterministic surface from it:

- a dependency-aware execution schedule
- materialized per-work-item manifest and config snapshots
- one persisted execution-state ledger keyed by `suite_spec_hash` and
  `work_item_id`

The schedule is intentionally explicit rather than inheriting the contract
sorting for `work_items`. Contract order is stable, but it is not an execution
topology. The runner therefore freezes a separate execution ordering:

- global stage sequence first
- then root-cell ordering
- then base-versus-ablation lineage
- then seed ordering for simulation cells

That gives dry runs, retries, and resumes one stable answer to "what runs
next?" without depending on directory scans or ad hoc shell loops.

I also kept planned suite metadata separate from realized stage outputs. The
planner already emits suite-owned placeholder artifact targets, but Milestone
15 packaging and indexing are still a later ticket. Pretending those planned
paths are already the authoritative bundle locations would blur the line
between planning and packaging. The runner therefore:

- persists the normalized suite plan and suite metadata
- writes the base upstream simulation plan to the suite root
- records actual produced bundle paths in the execution-state provenance

That makes status and resume semantics explicit now without pre-empting
`FW-M15-005`.

## Testing Strategy

The regression coverage focuses on orchestration semantics instead of re-running
the full Milestone 9 through 14 science stack in unit tests.

The new fixture test:

- resolves a real normalized suite plan through the Milestone 15 planner
- builds the deterministic execution schedule from that plan
- exercises dry-run output and verifies that it does not mutate persisted state
- injects fixture stage executors so one simulation work item fails once
- verifies that downstream work is marked `blocked` explicitly
- reruns the same suite and confirms that succeeded work items are skipped,
  failed work is retried, and previously blocked downstream stages resume

That test shape is deliberate. The ticket is about deterministic orchestration,
status persistence, and resume behavior. Using fixture executors keeps the test
fast while still proving that the real runner logic does not depend on manual
operator memory.

## Simplifications

The first version stays conservative in a few places:

- It reuses existing stage APIs by materializing per-work-item manifest and
  config snapshots instead of adding new in-memory execution hooks to every
  earlier milestone module.
- Validation packaging is recorded in orchestration provenance, but the suite
  contract still exposes only one `validation_bundle` role. The runner keeps
  that ambiguity explicit in the state ledger rather than silently redefining
  the contract.
- Declared ablation families are only realized through the override patches
  already present on normalized suite cells. The full deterministic ablation
  transform layer still belongs to `FW-M15-004`.
- Resume semantics trust the persisted execution-state file rather than trying
  to infer prior success from arbitrary files on disk.

These are intentional constraints for a first local runner. The priority here
is boring, reviewable orchestration behavior.

## Future Expansion Points

The clearest next steps are:

- `FW-M15-004`: replace planning-only ablation patches with explicit transform
  realizations and provenance
- `FW-M15-005`: promote the execution-state artifact inventory into a canonical
  suite packaging and indexing layer
- `FW-M15-006` and `FW-M15-007`: consume that packaged suite inventory for
  rollups, tables, plots, and review outputs
- add optional parallel or distributed scheduling later without changing the
  stable work-item IDs, dependency rules, or persisted status semantics added
  here
