# API Boundaries And Coupling Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: API boundaries and coupling.
- Tailor the prompt around the repo's real public seams, such as configs, CLI
  wrappers, schemas, manifests, bundle metadata, or library entrypoints.
- Help the eventual reviewer distinguish between internal helpers and true
  contracts that other code relies on.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if that clearly improves the rewritten prompt.

## Rewrite Requirements

- Name the repo's important contract surfaces and likely coupling hotspots.
- Include repo-specific validation commands when the docs make them clear.
- Note directories that are usually out of scope for this review.
- Keep the ticket format unchanged and one issue per ticket.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make the result directly runnable.
