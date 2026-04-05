# Error Handling And Operability Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: error handling and operability.
- Tailor the prompt around the repo's real commands, config surfaces, artifacts,
  and operator workflows.
- Make the eventual reviewer pay attention to the repo's documented safe
  validation loop and any auth, environment, or filesystem prerequisites.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only when they clearly improve the rewritten prompt.

## Rewrite Requirements

- Name the key operator-facing commands and likely failure points.
- Include repo-specific validation commands when the docs make them clear.
- Note directories that are usually out of scope.
- Keep the output contract as ticket markdown with one issue per ticket.
- Do not perform the review.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make it directly runnable.
