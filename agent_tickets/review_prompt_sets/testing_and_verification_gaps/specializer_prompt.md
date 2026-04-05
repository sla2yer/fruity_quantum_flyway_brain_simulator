# Testing And Verification Gaps Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: testing and verification gaps.
- Tune the prompt around the repo's actual validation commands, fixture
  strategy, contract files, and core workflows.
- Make the rewritten prompt aware of any documented safe validation loop or
  smoke path if the repo provides one.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only when needed to sharpen the rewritten prompt.

## Rewrite Requirements

- Name the repo's real verification commands and test entrypoints when they are
  documented.
- Point the eventual reviewer toward the most important contracts and workflows.
- Mention directories that should generally be ignored.
- Keep the output contract as ticket markdown with one issue per ticket.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make the result ready to run directly.
