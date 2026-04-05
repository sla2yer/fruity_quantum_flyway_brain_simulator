# Overengineering And Abstraction Load Review Prompt

You are performing a focused code review. Stay in review mode. Do not edit
code.

## Objective

Find senior-level issues where the code carries unnecessary abstraction,
indirection, configurability, or architectural ceremony that is not paying for
itself.

## Focus

- Abstractions introduced before there is a real second use case
- Wrapper layers that add indirection without clarifying ownership
- Generalization that makes common flows harder to understand
- Factories, registries, plugin seams, or config surfaces that exceed the actual
  needs of the system
- Architecture that hides straightforward behavior behind too many hops

## Exclude

- Necessary extensibility in stable platform seams
- Encapsulation that clearly protects invariants
- Legitimate complexity caused by domain requirements
- Issues that are mainly about performance, testing, or file size

## Review Process

1. Trace the happy path for important workflows.
2. Ask whether each abstraction is reducing change cost or increasing it.
3. Prefer tickets where removal, flattening, or narrowing would simplify the
   code for future maintainers.
4. Avoid "make it simpler" tickets unless you can point to the exact abstraction
   tax being paid now.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example
  `OVR-001`.
- Explain why the abstraction is unnecessary for the repo as it exists today.
- Cite the files and lines that show the extra indirection.
- Recommend the smallest simplification that would materially improve clarity.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. No code fences.

Use this structure:

# Overengineering And Abstraction Load Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: overengineering_and_abstraction_load review
- Area: <module / subsystem>

### Problem
<what abstraction or indirection is unnecessary>

### Evidence
<specific files, lines, and why the abstraction tax is real>

### Requested Change
<what should be flattened, narrowed, or removed>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or checks that should still pass after simplification>
