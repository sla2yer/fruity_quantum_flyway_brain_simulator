# File Length And Cohesion Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where files, modules, classes, or functions have grown
too large or too mixed in responsibility, making the code harder to navigate,
test, and change safely.

## Focus

- Oversized files that bundle unrelated concerns
- Functions or classes that own too many jobs
- Script files that quietly contain reusable library logic without a clear seam
- Modules where navigation cost is high because responsibilities are scattered
  or interleaved
- Split opportunities that would materially improve cohesion, ownership, or
  reviewability

## Exclude

- Mechanical file splitting with no clear design payoff
- Complaints based on line count alone
- Thin wrapper files that are small but awkward for different reasons
- Issues better explained as abstraction debt, API design, or testing gaps

## Review Process

1. Look for the highest-change or most central files first.
2. Evaluate whether size is causing real cohesion or maintenance problems.
3. Prefer tickets where a clearer file or module boundary would reduce future
   change risk.
4. Skip speculative refactors that would mostly reshuffle code without improving
   comprehension.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `FILECOH-001`.
- Make the case for why the current size or shape is a problem in practice.
- Cite concrete files and line references.
- Describe a better ownership boundary rather than only saying to "split the
  file."
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# File Length And Cohesion Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: file_length_and_cohesion review
- Area: <module / subsystem>

### Problem
<what has become too large or too mixed>

### Evidence
<specific files, lines, and why the current shape hurts>

### Requested Change
<target split, boundary, or ownership change>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or review checks that should still pass after the refactor>
