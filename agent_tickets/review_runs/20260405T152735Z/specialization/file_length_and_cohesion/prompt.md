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

## Prompt Set Context
- Prompt set slug: file_length_and_cohesion
- Prompt set title: File Length And Cohesion Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
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

Return only the repo-specific specialized prompt markdown.
