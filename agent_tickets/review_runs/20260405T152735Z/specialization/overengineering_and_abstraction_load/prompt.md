# Overengineering And Abstraction Load Prompt Specializer

Rewrite the supplied generic review prompt into a repo-specific version for the
current repository.

## What To Do

- Read the repository context before rewriting the prompt.
- Preserve the original review lens: overengineering and abstraction load.
- Tailor the prompt so the reviewer can separate necessary domain complexity
  from optional engineering ceremony.
- Make the prompt sensitive to the repo's actual stage of maturity, surfaced
  workflows, and real extension points.

## Minimum Repo Context To Inspect

- `AGENTS.md`
- `README.md`
- `Makefile`
- `src/`
- `scripts/`
- `tests/`

Inspect additional files only if that materially improves the rewritten prompt.

## Rewrite Requirements

- Name the repo areas where unnecessary indirection would be most costly.
- Include repo-specific validation commands if they are clearly documented.
- Mention any directories that should typically be ignored.
- Keep the ticket format intact and one-issue-per-ticket.
- Do not perform the review itself.

## Output Rules

- Return only the specialized prompt markdown.
- Do not include commentary or code fences.
- Make it ready to send directly to an agent.

## Prompt Set Context
- Prompt set slug: overengineering_and_abstraction_load
- Prompt set title: Overengineering And Abstraction Load Review Prompt
- Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

## Generic Prompt To Rewrite
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

Return only the repo-specific specialized prompt markdown.
