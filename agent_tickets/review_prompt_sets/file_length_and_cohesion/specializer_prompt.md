# File Length And Cohesion Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: file length and cohesion.
- Tune the prompt so it distinguishes between acceptable script entrypoints,
  intentionally dense contract files, and genuinely overgrown modules.
- Make the reviewer aware of the repo's real library, CLI, test, and docs
  boundaries.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only when needed to make the rewritten prompt sharper.

## Rewrite Requirements

- Name the repo's real module families and which ones are most likely to suffer
  from cohesion problems.
- Include repo-appropriate validation commands if the docs expose them.
- Call out directories that should generally be skipped during this review if
  they are generated, vendored, or external.
- Keep the output contract as ticket markdown with one ticket per issue.
- Do not perform the review.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make the final prompt ready for direct execution.
