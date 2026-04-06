# Package Structure And Module Placement Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: package structure and module placement.
- Tailor the prompt around the repo's real package layout, especially whether
  `src/` is flatter than the actual subsystem boundaries.
- Make the reviewer reason explicitly about when a family of modules should
  become subpackages instead of remaining siblings in one directory.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if they materially sharpen the rewritten prompt.

## Rewrite Requirements

- Name the repo's real subsystem families and candidate subpackage boundaries.
- Make the prompt distinguish between good file-level splits and true
  directory/package ownership changes.
- Call out generated, vendored, or external directories that should not drive
  package-structure tickets.
- Include repo-safe validation commands when documentation makes them clear.
- Keep the output contract as ticket markdown with one issue per ticket.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make the result ready to send directly to an agent.
