# Subset Preset Rationale

This document records the scientific reasoning behind the Milestone 4 named subset presets so the selection tool stays reproducible, reviewable, and easy to revise later.

## Design rules

- Keep the Milestone 2 locked claim in view: the first active circuit should stay centered on the horizontal ON/OFF local-motion channel around `T4a` and `T5a`.
- Prefer explicit cell-type rules over ad hoc root-id lists so presets can be regenerated from a fresh registry snapshot.
- Add context in small, inspectable layers:
  first the locked core,
  then direct one-hop context,
  then a denser local halo for boundary checks and ablation work.
- Exclude known out-of-scope branches by default, especially `R7/R8` and the broader color / polarization pathways.
- Treat relation-expansion caps as guardrails, not guarantees of a fixed neuron count. The actual root-id count still depends on the available registry and connectivity snapshot.

## Presets

### `motion_minimal`

Purpose:
establish the smallest reproducible subset that still matches the Milestone 2 active graph.

Included classes:
`T4a`, `T5a`, `Mi1`, `Tm3`, `Mi4`, `Mi9`, `Tm1`, `Tm2`, `Tm4`, `Tm9`

Reasoning:
- `T4a` and `T5a` are the surface-simulated anchors named in the locked circuit boundary.
- The listed `Mi*` and `Tm*` partners are the direct reduced ON/OFF inputs already called out in the milestone doc and registry role defaults.
- This preset is the right starting point for the first morphology-sensitive comparison because it minimizes extra context that could blur causal interpretation.

Best uses:
- first end-to-end simulator bring-up
- mesh fetch sanity checks
- baseline vs surface-model comparisons with the smallest fair circuit

### `motion_medium`

Purpose:
keep the same core active graph, but expose direct one-hop upstream and downstream context so you can inspect subset boundaries instead of treating them as invisible.

Added logic:
- one-hop upstream expansion from `T4a/T5a`
- one-hop downstream expansion from `T4a/T5a`
- region filters biased toward medulla, lobula, and lobula-plate neighborhoods

Reasoning:
- Milestone 2 explicitly marks direct partners and downstream promotion candidates as part of the candidate graph even when they are not active.
- Adding only one hop keeps the subset interpretable while surfacing the most immediate omissions and potential promotion targets.
- This is the right preset for report generation because the boundary partner lists become informative without immediately exploding into a much larger optic-lobe sample.

Best uses:
- checking whether the locked core drops important direct partners
- reviewing readout candidates before promoting them into later milestones
- generating richer preview graphs and boundary reports for discussion

### `motion_dense`

Purpose:
probe how sensitive the subset is to local halo/context choices without committing to a whole-field expansion.

Added logic:
- inherit everything from `motion_medium`
- add a broader upstream halo from the current selection, still constrained to local motion neuropils

Reasoning:
- The Milestone 2 doc asks for the selected footprint plus a one-ring halo so each active detector keeps a local neighborhood.
- This preset approximates that idea at the metadata/connectivity layer before mesh-scale geometry is fetched.
- It is intentionally denser so it can support boundary stress tests, geometry shuffles, and later promotion decisions without changing the overall scientific framing.

Best uses:
- ablation planning
- checking whether qualitative conclusions survive modest subset broadening
- deciding which context-only partners deserve promotion in Milestones 5 through 7

## Suggested ablations

- `motion_minimal` vs `motion_medium`: isolates the effect of adding only direct context.
- `motion_medium` vs `motion_dense`: asks whether conclusions depend on a small halo expansion.
- `motion_minimal` with one input class removed, for example `Mi1` or `Tm3`: tests branch sensitivity while keeping the rest of the selection fixed.
- `motion_medium` with downstream expansion disabled: checks whether readout-candidate inclusion changes interpretation of the same active core.

## Operational notes

- If `visual_neuron_columns.csv` is available, add `column_ids` or `column_*_range` filters to pin the preset to a specific retinotopic patch.
- Neuropil matching reuses the vendored FlyWire Codex neuropil lookup so free-form region labels can resolve to canonical FlyWire region IDs.
- Relationship expansion reuses the vendored Codex reachability helper so the subset tool and the reference snapshot agree on graph-traversal semantics.
