#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import select_cli_runner
from flywire_wave.review_prompt_tickets import (
    collect_failed_prompt_job_summaries,
    execute_review_prompt_workflow,
    filter_review_prompt_sets,
    load_review_prompt_sets,
)


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Specialize repo-review prompts in parallel, then run the specialized "
            "prompts in parallel to generate ticket packs."
        )
    )
    parser.add_argument(
        "--prompt-root",
        default="agent_tickets/review_prompt_sets",
        help="Directory that contains the review prompt-set folders.",
    )
    parser.add_argument(
        "--prompt-set",
        action="append",
        dest="prompt_sets",
        help="Run only the specified prompt-set slug. Repeatable.",
    )
    parser.add_argument(
        "--runner",
        help="Override the CLI executable. Defaults to CODEL_CLI_BIN, then codel-cli, then codex.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(ROOT),
        help="Repository root to pass to the CLI.",
    )
    parser.add_argument(
        "--output-dir",
        default=f"agent_tickets/review_runs/{_now_utc_stamp()}",
        help="Directory for specialization prompts, review prompts, logs, and summaries.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode passed to the CLI runner.",
    )
    parser.add_argument(
        "--specializer-model",
        help="Optional model override for the prompt-specialization phase.",
    )
    parser.add_argument(
        "--review-model",
        help="Optional model override for the review-ticket generation phase.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Maximum parallel prompt jobs per phase. Defaults to min(4, prompt set count).",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        dest="extra_args",
        default=[],
        help="Additional raw argument passed through to the CLI runner for both phases. Repeatable.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue into the review phase for prompt sets whose specialization succeeded.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=20.0,
        help="How often to print a keep-alive message if a child runner stays quiet.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan without launching the CLI runner.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    prompt_root = _resolve_repo_path(args.prompt_root)
    repo_root = _resolve_repo_path(args.repo_root)
    output_dir = _resolve_repo_path(args.output_dir)
    prompt_sets = filter_review_prompt_sets(
        load_review_prompt_sets(prompt_root),
        include_slugs=set(args.prompt_sets) if args.prompt_sets else None,
    )
    if not prompt_sets:
        raise RuntimeError("No prompt sets matched the requested filters.")

    if args.dry_run:
        plan = {
            "repo_root": str(repo_root),
            "prompt_root": str(prompt_root),
            "output_dir": str(output_dir),
            "runner": args.runner or os.getenv("CODEL_CLI_BIN") or "auto",
            "sandbox": args.sandbox,
            "specializer_model": args.specializer_model,
            "review_model": args.review_model,
            "max_workers": args.max_workers,
            "extra_args": args.extra_args,
            "prompt_sets": [
                {
                    "slug": prompt_set.slug,
                    "title": prompt_set.title,
                    "generic_prompt_path": str(prompt_set.generic_prompt_path),
                    "specializer_prompt_path": str(prompt_set.specializer_prompt_path),
                }
                for prompt_set in prompt_sets
            ],
        }
        print(json.dumps(plan, indent=2))
        return 0

    runner = select_cli_runner(args.runner)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"Running {len(prompt_sets)} prompt set(s) through specialization and review using {runner}.",
        flush=True,
    )

    progress_lock = Lock()

    def progress_callback(message: str) -> None:
        with progress_lock:
            print(message, flush=True)

    summary = execute_review_prompt_workflow(
        prompt_sets,
        repo_root=repo_root,
        runner=runner,
        output_dir=output_dir,
        sandbox=args.sandbox,
        specializer_model=args.specializer_model,
        review_model=args.review_model,
        extra_args=args.extra_args,
        max_workers=args.max_workers,
        continue_on_error=args.continue_on_error,
        heartbeat_seconds=args.heartbeat_seconds,
        progress_callback=progress_callback,
    )

    print(f"Summary written to {summary['summary_path']}", flush=True)
    if summary["combined_tickets_path"]:
        print(f"Combined tickets written to {summary['combined_tickets_path']}", flush=True)
    failed_results = collect_failed_prompt_job_summaries(summary)
    if failed_results:
        print("Failed prompt jobs:", flush=True)
        for failure in failed_results:
            artifact_text = ", ".join(failure["diagnostic_paths"])
            if not artifact_text:
                artifact_text = "(no prompt-job diagnostics were written)"
            print(
                (
                    f"- prompt_set={failure['prompt_set']} "
                    f"stage={failure['stage']} "
                    f"returncode={failure['returncode']} "
                    f"artifacts={artifact_text}"
                ),
                flush=True,
            )

    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
