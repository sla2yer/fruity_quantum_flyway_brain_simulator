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
