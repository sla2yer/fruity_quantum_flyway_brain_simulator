# FW-M13-001 Rationale

## Design Choices

This ticket adds one library-owned contract module instead of scattering the
Milestone 13 vocabulary across scripts or docs. The module owns:

- the four layer IDs
- the first validator-family IDs
- the first validator IDs
- the evidence-scope vocabulary
- one shared result-status vocabulary
- the machine-to-reviewer handoff boundary
- a deterministic validation-output artifact layout

The design intentionally composes with Milestones 6, 10, 11, and 12. Validation
starts from their contract-owned artifacts instead of inventing private
notebook-only discovery rules.

## Why Criteria Profiles Are References Only

Grant owns the scientific criteria values and the plausibility judgment. This
ticket therefore freezes criteria-profile references, not the future numeric
threshold contents. That keeps the Milestone 13 vocabulary stable without
pretending to settle the scientific review work early.

The explicit boundary is:

- machine code may classify deterministic findings from declared local artifacts
- Grant decides whether those findings support a scientific claim

That distinction is encoded in the contract and repeated in the design note.

## Testing Strategy

The regression coverage focuses on the contract surface this ticket introduces:

- deterministic normalization and JSON serialization of validation-contract
  metadata
- stable discovery of layers, validator families, and validator IDs
- normalization of representative fixture metadata with reordered catalogs and
  humanized IDs
- deterministic validation-bundle metadata plus artifact-path discovery

This keeps the test surface narrow and stable while still proving that later
Milestone 13 work can rely on one canonical vocabulary.

## Simplifications

The ticket deliberately does not implement a full validation execution runner or
the final scientific threshold tables. It also freezes only the first validator
family per layer, because the immediate repo risk was vocabulary drift rather
than missing numerical kernels.

The offline report is Markdown-only for now. That is enough to reserve the
artifact slot and prove deterministic discovery without committing the repo to a
larger reporting stack yet.

## Future Expansion Points

Later tickets can extend this contract by adding:

- criteria-profile loaders backed by config or manifest references
- concrete validator execution code and result writers
- richer reviewer artifacts or UI packaging
- additional validator families per layer
- cross-run comparison helpers for validation bundles

Those additions should reuse the locked IDs and artifact slots here. If they
need different semantics, the contract version should change rather than
mutating `validation_ladder.v1`.
