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
