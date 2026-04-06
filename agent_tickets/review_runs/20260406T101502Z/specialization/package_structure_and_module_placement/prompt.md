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

## Prompt Set Context
- Prompt set slug: package_structure_and_module_placement
- Prompt set title: Package Structure And Module Placement Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
# Package Structure And Module Placement Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where package layout, directory structure, module
placement, or ownership boundaries are making the codebase harder to navigate,
extend, or maintain safely.

## Focus

- Flat package layouts that have outgrown a single directory
- Modules living in the wrong package or alongside unrelated peers
- Missing subpackage boundaries for major subsystem families
- CLI, contract, planning, execution, packaging, and UI code living together
  without a strong directory boundary
- Test utilities or fixtures trapped in the wrong modules instead of shared
  support locations
- Folder structures that obscure ownership, dependency direction, or review
  surface boundaries

## Exclude

- Pure renames with no architectural payoff
- Mechanical moves that only reshuffle imports without improving ownership
- File-splitting tickets whose main issue is local cohesion rather than package
  structure
- Generated, vendored, or external code

## Review Process

1. Identify the repo's major subsystem families and how they are currently laid
   out on disk.
2. Look for places where directory/package structure is lagging behind actual
   ownership boundaries.
3. Prefer tickets where package or directory changes would improve navigation,
   dependency clarity, and future refactoring safety.
4. Only emit a ticket when folder/module placement is the primary reason the
   change should happen.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `PKGSTR-001`.
- Cite concrete files and explain the package-boundary problem, not just that
  things feel "flat."
- Recommend a target ownership boundary or subpackage layout.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Package Structure And Module Placement Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: package_structure_and_module_placement review
- Area: <package / subsystem>

### Problem
<what package-structure or module-placement issue exists>

### Evidence
<specific files, directories, and why the current layout hurts>

### Requested Change
<the target package, directory, or ownership change>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or checks that should still pass after the restructure>

Return only the repo-specific specialized prompt markdown.
