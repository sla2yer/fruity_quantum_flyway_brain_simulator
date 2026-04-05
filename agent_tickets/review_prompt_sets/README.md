# Review Prompt Sets

Each review lens lives in its own directory and is discovered automatically by
`scripts/run_review_prompt_tickets.py`.

Every prompt set must include:

- `generic_prompt.md`: the reusable, repo-agnostic review prompt
- `specializer_prompt.md`: the prompt used to rewrite the generic prompt into a
  repo-specific version before the review runs

The runner executes two phases:

1. Specialize every generic prompt for the current repository.
2. Run the specialized prompts to generate ticket packs.

The generated artifacts land under `agent_tickets/review_runs/` by default.
