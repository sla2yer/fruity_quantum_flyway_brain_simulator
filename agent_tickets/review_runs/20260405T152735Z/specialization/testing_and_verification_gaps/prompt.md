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

## Prompt Set Context
- Prompt set slug: testing_and_verification_gaps
- Prompt set title: Testing And Verification Gaps Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
# Testing And Verification Gaps Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where important behavior lacks adequate regression
coverage, contract validation, failure-path checks, or operator-facing
verification guidance.

## Focus

- Critical paths with weak or missing automated coverage
- Failure modes that are handled in code but not exercised in tests
- Validation commands or smoke checks that do not cover the behavior the repo
  most depends on
- Tests that are too indirect to protect a risky contract
- Areas where the docs promise behavior that the verification story does not
  truly cover

## Exclude

- Requests for tests on low-risk trivia
- Broad "add more tests" tickets with no concrete target
- Issues that are mainly about performance or architecture
- Existing coverage gaps that are already clearly intentional and documented

## Review Process

1. Map the repo's core workflows and contracts.
2. Compare those workflows against the test and validation surface.
3. Prioritize gaps that would plausibly allow a meaningful regression through.
4. Emit only actionable tickets with a concrete missing protection.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `TESTGAP-001`.
- Cite the code path, the missing coverage, and the likely regression it would
  fail to catch.
- Recommend the narrowest useful verification addition.
- Include exact tests, smoke commands, or fixture checks when you can infer
  them.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Testing And Verification Gaps Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: testing_and_verification_gaps review
- Area: <module / subsystem>

### Problem
<what important behavior is under-protected>

### Evidence
<specific files, lines, tests, and validation gaps>

### Requested Change
<the missing tests, fixtures, or verification surface>

### Acceptance Criteria
<observable completion criteria>

### Verification
<the commands or checks that should pass once the gap is closed>

Return only the repo-specific specialized prompt markdown.
