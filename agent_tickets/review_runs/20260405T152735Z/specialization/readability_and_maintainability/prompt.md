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

## Prompt Set Context
- Prompt set slug: readability_and_maintainability
- Prompt set title: Readability And Maintainability Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
# Readability And Maintainability Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where the code is harder to understand and maintain
than it needs to be because of confusing naming, tangled control flow, hidden
invariants, or poor local clarity.

## Focus

- Functions with dense branching or hard-to-follow state changes
- Names that obscure intent or domain meaning
- Hidden assumptions, magic values, or invariants that are not communicated in
  code structure
- Repeated patterns that are difficult to reason about because the local story
  is unclear
- Areas where maintainers are likely to make mistakes because understanding
  costs are too high

## Exclude

- Pure formatting or stylistic preferences
- Large-scale refactors whose main payoff is file splitting or architecture
- Documentation-only issues
- Problems better categorized as testing, performance, or operability

## Review Process

1. Look at the repo's most central logic first.
2. Favor issues that would materially slow down future changes or reviews.
3. Require concrete evidence that the current code obscures intent.
4. Prefer a small set of high-value tickets over broad cleanup lists.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `MAINT-001`.
- Cite files and line references.
- Explain why the current code is hard to reason about, not just that it is
  "unclear."
- Recommend a maintainability improvement with a clear payoff.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Readability And Maintainability Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: readability_and_maintainability review
- Area: <module / subsystem>

### Problem
<what makes the code hard to understand or maintain>

### Evidence
<specific files, lines, and why the maintainability cost is real>

### Requested Change
<the clarity or maintainability improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or checks that should still pass after the cleanup>

Return only the repo-specific specialized prompt markdown.
