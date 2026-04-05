# Overengineering And Abstraction Load Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: overengineering and abstraction load.
- Tailor the prompt so the reviewer can separate necessary domain complexity
  from optional engineering ceremony.
- Make the prompt sensitive to the repo's actual stage of maturity, surfaced
  workflows, and real extension points.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if that materially improves the rewritten prompt.

## Rewrite Requirements

- Name the repo areas where unnecessary indirection would be most costly.
- Include repo-specific validation commands if they are clearly documented.
- Mention any directories that should typically be ignored.
- Keep the ticket format intact and one-issue-per-ticket.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make it ready to send directly to an agent.
