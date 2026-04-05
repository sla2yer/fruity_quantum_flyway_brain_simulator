# API Boundaries And Coupling Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where module boundaries, public APIs, data contracts,
or dependency relationships are making the system harder to extend or reason
about safely.

## Focus

- Leaky module boundaries or public APIs that expose internal details
- Modules that know too much about each other
- Data contracts that are inconsistent, weakly normalized, or hard to validate
- CLI, library, and test surfaces that disagree about the same behavior
- APIs with confusing flags, optional fields, return shapes, or lifecycle rules

## Exclude

- Pure file-size complaints
- Feedback that is mostly about performance
- Style nits and naming-only issues
- Abstractions whose main problem is unnecessary ceremony rather than coupling

## Review Process

1. Identify the repo's primary public seams: library APIs, scripts, schemas,
   manifests, configs, bundles, or other contracts.
2. Look for places where the current boundary increases change risk or hidden
   coupling.
3. Prefer tickets that tighten ownership or clarify contracts.
4. Only emit issues where boundary design is the main reason to act.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `APICPL-001`.
- Cite concrete files and lines.
- Explain how the current boundary leaks, couples, or confuses behavior.
- Recommend a contract or ownership change that would make the system easier to
  evolve.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# API Boundaries And Coupling Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: api_boundaries_and_coupling review
- Area: <module / subsystem>

### Problem
<what boundary or coupling issue exists>

### Evidence
<specific files, lines, and why this creates risk>

### Requested Change
<the contract or ownership improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, contract checks, or command-level validation>
