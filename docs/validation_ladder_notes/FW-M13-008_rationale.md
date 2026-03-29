# FW-M13-008 Rationale

## Purpose

Milestone 13 already had contract, planning, layer validators, packaging, and a
smoke baseline, but it still lacked one explicit integration pass that tied
those pieces together for reviewers. This ticket adds that missing layer:

- `flywire_wave.milestone13_readiness` plus
  `scripts/28_milestone13_readiness.py` run one deterministic readiness pass
  and write a concise in-repo report
- the readiness pass combines a representative-manifest validation-plan audit
  with a repeated end-to-end packaged smoke run so reviewers can see both the
  manifest-facing contract surface and the executable ladder behavior in one
  place

## Design Choices

- The readiness pass reuses the existing packaged smoke command instead of
  inventing a second hidden integration path.
  The main end-to-end execution audit runs
  `scripts/27_validation_ladder.py smoke` twice and verifies deterministic
  bundle identity, stable output paths, stable report/export bytes, and
  baseline agreement.
- Representative-manifest coverage is plan-first on purpose.
  The readiness pass materializes a small local fixture that points at the real
  Milestone 1 demo manifest, then resolves the full validation plan plus the
  four layer-specific plans. That proves the contract surface and output
  locations for a real manifest path without requiring a committed manifest-scale
  result cache in git.
- Review-level findings remain valid readiness outputs.
  The current smoke fixture intentionally produces one packaged `review` status
  at the task layer. The readiness pass treats that as evidence that the
  machine-versus-review boundary is preserved, not as an integration failure.
- Command discovery is audited explicitly.
  The pass checks `make help`, the packaged ladder CLI help, the new readiness
  CLI help, and the repo docs so reviewers can confirm the shipped commands are
  actually discoverable.

## Testing Strategy

Coverage now lands in three places.

- `tests/test_milestone13_readiness.py` runs the full readiness pass in a
  temporary output root and asserts deterministic report paths plus expected
  audit results.
- `tests/test_validation_circuit.py` now covers the default circuit-readout
  derivation path so `make circuit-validate` is a valid shipped command surface
  instead of requiring an undocumented extra flag.
- `make test` and `make validation-ladder-smoke` continue to validate the
  broader Milestone 13 layer and packaging regressions.

## Simplifications

- The representative-manifest fixture synthesizes local result-bundle metadata
  and a packaged analysis bundle rather than shipping a committed manifest-scale
  execution cache.
  That is enough to audit plan resolution and deterministic output discovery,
  but it does not replace a future manifest-owned execution cache.
- The readiness report is Markdown plus JSON.
  It focuses on high-signal audit results, command surfaces, risks, and
  follow-on tickets instead of adding another visualization stack.
- The readiness pass does not force all review-level findings to become `pass`.
  It verifies that those review outputs are deterministic, discoverable, and
  clearly separated from blocking failures.

## Future Expansion

Likely follow-on work:

- add a committed manifest-scale validation fixture with cached runnable assets
  so all four validators can execute on a representative manifest without
  synthetic metadata generation
- expand the task-layer smoke fixture so dashboard work can exercise richer
  shared-versus-wave presentation states on packaged Milestone 13 outputs
- add a first-class manifest-owned ladder orchestration command when later
  milestones need one command that resolves plans, runs all layers, and packages
  results for cached local assets
