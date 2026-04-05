# Error Handling And Operability Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where failures are hard to diagnose, guardrails are
weak, error handling is inconsistent, or operator workflows are more fragile
than they need to be.

## Focus

- Missing or ambiguous error messages
- Failure modes that continue silently or degrade in confusing ways
- Weak precondition checks around config, files, environment, or runtime state
- CLI and automation paths that are difficult to debug from the emitted output
- Places where the code hides the true cause of failure or leaves operators with
  unclear next steps

## Exclude

- Pure feature requests
- Minor wording nits in otherwise clear messages
- Issues that are mainly about tests or architecture
- Expected hard failures that are already explicit and actionable

## Review Process

1. Inspect the repo's main operator and automation entrypoints.
2. Look for failure paths that would be painful in real use.
3. Prefer tickets that materially improve debuggability, guardrails, or safe
   automation.
4. Emit only issues where operability is the primary concern.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `OPS-001`.
- Cite the code path and the current failure behavior.
- Explain why the present behavior would confuse or slow down an operator.
- Recommend a concrete guardrail, validation step, or error-shaping change.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. Do not use code fences.

Use this structure:

# Error Handling And Operability Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: error_handling_and_operability review
- Area: <module / subsystem>

### Problem
<what failure-path or operability issue exists>

### Evidence
<specific files, lines, and observed behavior>

### Requested Change
<the guardrail or error-handling improvement>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests, CLI checks, or repro steps>
