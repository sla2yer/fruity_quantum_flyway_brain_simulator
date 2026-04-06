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
