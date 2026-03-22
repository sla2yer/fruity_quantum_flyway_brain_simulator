# Offline Coupling Inspection Workflow

Milestone 7 is not finished when coupling bundles merely serialize. Before the
simulator starts consuming those bundles, reviewers need one offline workflow
that can answer:

- which synapse rows belong to one connectome edge
- where the edge reads from the presynaptic state space
- where it lands on the postsynaptic state space
- how many synapses were aggregated into each coupling component
- which sign and delay semantics were assigned
- whether mapping coverage and bundle integrity are trustworthy enough for
  follow-on simulator work

`scripts/08_coupling_inspection.py` is that workflow.

## Inputs

The report reads only local Milestone 7 artifacts:

- `config.paths.processed_coupling_dir/synapse_registry.csv`
- `config.paths.processed_coupling_dir/edges/<pre_root_id>__to__<post_root_id>_coupling.npz`
- `config.paths.processed_coupling_dir/roots/<pre_root_id>_outgoing_anchor_map.npz`
- `config.paths.processed_coupling_dir/roots/<post_root_id>_incoming_anchor_map.npz`
- the local geometry bundle paths needed by the realized anchor types:
  - patch graphs for surface-patch anchors
  - optional surface graphs for a lighter background overlay
  - raw skeletons for skeleton-node anchors

No FlyWire token or network access is required.

If a required local artifact is missing, the report does not crash with a raw
traceback. It writes a deterministic blocked detail JSON for that edge and
surfaces the missing prerequisite paths explicitly.

## Run It

Inspect one explicit edge:

```bash
python scripts/08_coupling_inspection.py --config config/local.yaml --edge 202:101
```

Inspect a small hand-picked set:

```bash
python scripts/08_coupling_inspection.py \
  --config config/local.yaml \
  --edge 202:101 \
  --edge 101:303
```

Read the edge set from a file:

```bash
python scripts/08_coupling_inspection.py --config config/local.yaml --edges-file edge_review.txt
```

Equivalent Make target:

```bash
make coupling-inspect CONFIG=config/local.yaml COUPLING_INSPECT_ARGS="--edge 202:101"
```

Release-style Milestone 7 integration pass:

```bash
make milestone7-readiness
```

That command runs the focused fixture suite plus the shipped offline command
sequence over [`config/milestone_7_verification.yaml`](../config/milestone_7_verification.yaml)
and publishes `milestone_7_readiness.md` / `milestone_7_readiness.json` in the
same deterministic coupling-inspection report directory.

Accepted edge-list formats are:

- `202:101`
- `202,101`
- `202->101`

## Output Layout

The output directory is deterministic for the exact sorted edge set:

```text
config.paths.coupling_inspection_dir/edges-<sorted-edge-slug>/
```

Example:

```text
data/processed/coupling_inspection/edges-202-to-101/index.html
data/processed/coupling_inspection/edges-202-to-101/report.md
data/processed/coupling_inspection/edges-202-to-101/summary.json
data/processed/coupling_inspection/edges-202-to-101/edges.txt
data/processed/coupling_inspection/edges-202-to-101/202__to__101_details.json
data/processed/coupling_inspection/edges-202-to-101/202__to__101_source_readout.svg
data/processed/coupling_inspection/edges-202-to-101/202__to__101_target_landing.svg
```

That path stability is deliberate so the report can be referenced from run
logs, ticket notes, or later Milestone 7 readiness checks.

## What It Shows

For each inspected edge, the report includes:

- an edge summary with topology, kernel, sign, delay, neuropil, and usable vs
  blocked synapse counts
- a presynaptic readout panel that overlays synapse query points, anchor
  residual lines, and aggregate source-cloud emphasis on the local geometry
- a postsynaptic landing panel with the same treatment on the receiving side
- presynaptic and postsynaptic mapping summaries:
  - mapping-status counts
  - quality-status counts
  - anchor-type counts
  - fallback usage
- aggregation summaries:
  - component count
  - component sign counts
  - delay-bin counts
  - per-component synapse counts
- blocked-synapse rows and reasons when applicable

## QA Checks

Each edge emits compact `pass`, `warn`, or `fail` flags, backed by a more
detailed metric table in the edge detail JSON.

Current checks cover:

- presynaptic mapping coverage
- postsynaptic mapping coverage
- quality-warning fraction on each side
- fallback fraction on each side
- exact row agreement across the edge bundle, the local synapse registry slice,
  and the root-local anchor maps
- component-membership completeness for usable synapses
- source and target cloud-normalization residuals
- signed and absolute weight conservation from per-synapse membership to
  aggregate component totals
- non-negative, finite per-synapse delays

The overall edge status is:

- `pass`: no warnings or failures
- `warn`: review is needed, but the edge is still structurally coherent
- `fail`: an integrity or mapping problem needs fixing before the bundle is used
- `blocked`: one or more required local artifacts were missing, so the edge was
  not reviewable

## Reviewer Checklist

Reviewers should look for:

- presynaptic query points and anchors staying on the expected source
  representation instead of scattering across unrelated structure
- postsynaptic landing anchors matching the intended receiving geometry rather
  than collapsing onto one implausible patch or node
- blocked synapses being explicit and explainable rather than silently absent
- fallback usage staying limited and scientifically justified
- quality warnings concentrating on known edge cases rather than dominating the
  whole edge
- component rows that make sense:
  - sign splits preserved
  - delay bins plausible
  - aggregated synapse counts matching what the visuals suggest

When the report warns or fails:

- if mapping coverage drops or blocked rows grow, inspect the source snapshot
  and the anchor fallback path first
- if artifact-consistency checks fail, treat the edge bundle as untrustworthy
  until the registry, anchor maps, and coupling archive agree exactly again
- if cloud-normalization or weight-conservation checks fail, stop downstream
  simulator work on that edge and rebuild or debug the coupling assembly
- if delay checks fail, do not assume the simulator can repair the bundle; fix
  the Milestone 7 artifact first

## Threshold Overrides

Optional overrides live under `meshing.coupling_inspection_thresholds` in the
config:

```yaml
meshing:
  coupling_inspection_thresholds:
    pre_mapped_fraction:
      warn: 0.95
      fail: 0.80
      comparison: min
      blocking: true
```

Use tighter thresholds when the report is acting as a release gate. Relax them
only when the review goal is exploratory and the tradeoff is documented
explicitly.
