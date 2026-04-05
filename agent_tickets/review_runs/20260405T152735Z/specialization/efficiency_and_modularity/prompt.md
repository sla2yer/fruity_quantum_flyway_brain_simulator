# Efficiency And Modularity Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Use the local docs and code layout to name the real subsystems, workflows,
  commands, and constraints that should guide the review.
- Preserve the original review lens: efficiency and modularity.
- Tune the prompt so the reviewer looks first at the repo's likely hot paths,
  heavy data-processing paths, orchestration seams, and core library modules.
- Keep the output contract as ticket markdown with one ticket per issue.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if they clearly sharpen the rewritten prompt.

## Rewrite Requirements

- Make the review scope specific to this repo's architecture and workflow.
- Name the commands the reviewer should use for validation when the repo makes
  that clear.
- Call out any directories that should usually be ignored, such as generated
  outputs, vendored code, or submodules, if the repo contains them.
- Keep the prompt actionable and concise enough to run directly.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary, analysis, or surrounding code fences.
- Keep the final prompt ready to send directly to an agent.

## Prompt Set Context
- Prompt set slug: efficiency_and_modularity
- Prompt set title: Efficiency And Modularity Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
# Efficiency And Modularity Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code, open pull requests, or propose implementation patches.

## Objective

Find senior-level issues where runtime efficiency, data-movement cost, or weak
modular structure is materially hurting the codebase.

## Focus

- Repeated full scans, redundant parsing, avoidable recomputation, or excessive
  copying in meaningful execution paths
- Modules or functions that mix too many responsibilities and therefore block
  reuse, testing, or optimization
- Duplicate logic that should be centralized because the duplication is already
  causing drift or overhead
- APIs or call patterns that make the efficient path hard to use correctly

## Exclude

- Pure micro-optimizations with no plausible operational payoff
- Style-only feedback
- Abstractions whose main issue is overengineering rather than efficiency or
  modularity
- Tickets that are primarily about testing, naming, or documentation

## Review Process

1. Identify the parts of the repo most likely to be performance-sensitive or
   structurally central.
2. Trace the current implementation far enough to confirm the issue is real.
3. Prefer fewer, higher-signal tickets over broad wish lists.
4. Only emit a ticket when the efficiency or modularity concern is the primary
   reason the change should happen.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `EFFMOD-001`.
- Write for senior engineers who need enough context to act without rediscovering
  the problem from scratch.
- Cite concrete evidence with file paths and 1-based line references when
  possible, for example `src/package/module.py:42`.
- Explain why the current shape is costly, not just that it could be cleaner.
- Recommend changes that simplify or speed up the system without adding needless
  complexity.
- If there are no credible issues, return a short markdown document that says no
  tickets are recommended.

## Output Format

Return only markdown. Do not wrap the answer in code fences.

Use this structure:

# Efficiency And Modularity Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: efficiency_and_modularity review
- Area: <module / subsystem>

### Problem
<what is wrong and why it matters>

### Evidence
<specific files, lines, and observations>

### Requested Change
<the change a senior dev should make>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, benchmarks, smoke checks, or command-level validation>

Return only the repo-specific specialized prompt markdown.
