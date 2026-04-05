# Readability And Maintainability Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: readability and maintainability.
- Tailor the prompt around the repo's real domain language, module families,
  operator workflows, and contract surfaces.
- Help the eventual reviewer focus on high-value clarity problems rather than
  style-only commentary.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if that materially sharpens the rewritten prompt.

## Rewrite Requirements

- Name the repo areas where local clarity matters most.
- Include repo-specific validation commands when documentation exposes them.
- Mention directories that are generally out of scope.
- Keep the output contract as ticket markdown with one issue per ticket.
- Do not perform the review.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make the result ready for direct use.
