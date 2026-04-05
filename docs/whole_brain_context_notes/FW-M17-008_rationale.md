# FW-M17-008 Rationale

## Design choices

This ticket adds one explicit Milestone 17 readiness layer instead of treating
the earlier whole-brain tickets as sufficient proof on their own.

The core decisions were:

- add one public whole-brain-context CLI,
  `scripts/36_whole_brain_context_session.py`, so reviewers can package and
  inspect the Milestone 17 surface without importing library code
- keep the readiness pass showcase-driven because that is the richest existing
  upstream surface and it exercises both the compact Milestone 16 handoff and
  the broader Milestone 17 package
- audit two packaged context modes:
  the default richer review path and a downstream-module-focused path
- verify dashboard bridge rendering through the shipped dashboard command while
  still checking the honest `summary_only` fallback path directly in library
  code
- record residual product and scientific risks as explicit follow-on tickets
  instead of leaving them implicit in the report prose

The intent is straightforward: Milestone 17 should end with one reviewable
place where contract semantics, packaging, dashboard integration, and showcase
handoff all line up.

## Testing strategy

The verification strategy combines public-command execution with focused
regression tests.

The readiness pass itself now:

- materializes the repo-owned packaged showcase fixture
- builds a showcase session from the shipped CLI
- builds a richer whole-brain review package from the new whole-brain-context
  CLI and reruns it to prove deterministic outputs
- inspects the packaged preset library, reduction-profile spread, overlay and
  metadata-facet catalogs, pathway explanation payloads, and serialized view
  state
- builds a dashboard session that links the packaged Milestone 17 context and
  checks both the bridge metadata and honest oversized fallback behavior
- builds a downstream-module-focused context package and verifies explicit
  simplification labels plus dashboard/showcase handoff lineage

Regression coverage was extended with:

- `tests/test_milestone17_readiness.py` for the end-to-end report surface
- a focused showcase-session test for the `analysis_summary` to
  `whole_brain_context_handoff` link

The full repo verification still ends with `make test`.

## Simplifications

The readiness pass is intentionally an integration audit, not a browser test
suite or a scientific curation pass.

Current simplifications:

- the dashboard verification still inspects packaged bootstrap/state artifacts
  and library fallback behavior instead of driving the whole-brain controls in
  a browser engine
- the richer whole-brain review fixture remains a compact local metadata graph
  rather than a denser curated female-brain context pack
- the readiness report checks that pathway explanations and downstream modules
  stay truthful and traceable, but it does not claim those curated pathways are
  scientifically final

Those limits are deliberate. The milestone needed one deterministic confidence
point first.

## Future expansion

Likely follow-on work can extend this layer by:

- adding a browser-level smoke for context representation switching, overlay or
  facet interactions, and the showcase handoff
- promoting the current compact review fixture into a denser scientifically
  curated broader-brain context pack
- exposing more reviewer-facing context inspection affordances once the UI path
  matters as much as the packaging contract
