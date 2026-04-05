from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flywire_wave.agent_tickets import _stream_ticket_process, _ticket_runner_popen_kwargs


PROMPT_SET_REQUIRED_FILENAMES = ("generic_prompt.md", "specializer_prompt.md")
PROMPT_RUN_ARTIFACT_FILENAMES = ("prompt.md", "stdout.jsonl", "stderr.log", "last_message.md")
SPECIALIZED_PROMPT_FILENAME = "specialized_prompt.md"
TICKETS_FILENAME = "tickets.md"
SUMMARY_FILENAME = "summary.json"
COMBINED_TICKETS_FILENAME = "combined_tickets.md"


@dataclass(frozen=True)
class ReviewPromptSet:
    slug: str
    title: str
    directory: Path
    generic_prompt_path: Path
    specializer_prompt_path: Path


@dataclass(frozen=True)
class SpecializedReviewPrompt:
    slug: str
    title: str
    specialized_prompt_path: Path
    previous_tickets_path: Path | None = None


PromptJobRunner = Callable[..., dict[str, Any]]


def _slug_to_title(slug: str) -> str:
    return slug.replace("_", " ").strip().title()


def _read_markdown_title(path: Path, *, fallback: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def load_review_prompt_sets(prompt_root: str | Path) -> list[ReviewPromptSet]:
    prompt_root = Path(prompt_root)
    if not prompt_root.exists():
        raise FileNotFoundError(f"Prompt root does not exist: {prompt_root}")

    prompt_sets: list[ReviewPromptSet] = []
    for entry in sorted(prompt_root.iterdir()):
        if not entry.is_dir():
            continue
        generic_prompt_path = entry / "generic_prompt.md"
        specializer_prompt_path = entry / "specializer_prompt.md"

        if not generic_prompt_path.exists() and not specializer_prompt_path.exists():
            continue
        missing = [
            filename
            for filename in PROMPT_SET_REQUIRED_FILENAMES
            if not (entry / filename).exists()
        ]
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise RuntimeError(f"Prompt set {entry.name} is missing required file(s): {missing_text}")

        title = _read_markdown_title(generic_prompt_path, fallback=_slug_to_title(entry.name))
        prompt_sets.append(
            ReviewPromptSet(
                slug=entry.name,
                title=title,
                directory=entry,
                generic_prompt_path=generic_prompt_path,
                specializer_prompt_path=specializer_prompt_path,
            )
        )

    return prompt_sets


def filter_review_prompt_sets(
    prompt_sets: Sequence[ReviewPromptSet],
    *,
    include_slugs: set[str] | None = None,
) -> list[ReviewPromptSet]:
    selected = list(prompt_sets)
    if include_slugs is None:
        return selected

    normalized = {slug.strip() for slug in include_slugs if slug.strip()}
    selected = [prompt_set for prompt_set in selected if prompt_set.slug in normalized]
    found = {prompt_set.slug for prompt_set in selected}
    missing = sorted(normalized - found)
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"Unknown prompt set(s): {missing_text}")
    return selected


def load_specialized_review_prompts(review_run_dir: str | Path) -> list[SpecializedReviewPrompt]:
    review_run_dir = Path(review_run_dir)
    specialization_dir = review_run_dir / "specialization"
    if not specialization_dir.exists():
        raise FileNotFoundError(f"Specialization directory does not exist: {specialization_dir}")

    titles_by_slug: dict[str, str] = {}
    summary_path = review_run_dir / SUMMARY_FILENAME
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}
        for result in summary.get("specialization_results", []):
            slug = str(result.get("prompt_set", "")).strip()
            title = str(result.get("title", "")).strip()
            if slug and title:
                titles_by_slug[slug] = title

    prompts: list[SpecializedReviewPrompt] = []
    for entry in sorted(specialization_dir.iterdir()):
        if not entry.is_dir():
            continue
        specialized_prompt_path = entry / SPECIALIZED_PROMPT_FILENAME
        if not specialized_prompt_path.exists():
            continue

        slug = entry.name
        title = titles_by_slug.get(slug, _slug_to_title(slug))
        previous_tickets_path = review_run_dir / "reviews" / slug / TICKETS_FILENAME
        prompts.append(
            SpecializedReviewPrompt(
                slug=slug,
                title=title,
                specialized_prompt_path=specialized_prompt_path,
                previous_tickets_path=previous_tickets_path if previous_tickets_path.exists() else None,
            )
        )

    return prompts


def build_specialization_prompt(prompt_set: ReviewPromptSet, *, repo_root: str | Path) -> str:
    specializer_prompt = prompt_set.specializer_prompt_path.read_text(encoding="utf-8").strip()
    generic_prompt = prompt_set.generic_prompt_path.read_text(encoding="utf-8").strip()
    repo_root = Path(repo_root).resolve()

    parts = [
        specializer_prompt,
        "",
        "## Prompt Set Context",
        f"- Prompt set slug: {prompt_set.slug}",
        f"- Prompt set title: {prompt_set.title}",
        f"- Repository root: {repo_root}",
        "",
        "## Generic Prompt To Rewrite",
        generic_prompt,
        "",
        "Return only the repo-specific specialized prompt markdown.",
    ]
    return "\n".join(parts).strip() + "\n"


def build_review_execution_prompt(
    prompt_set: ReviewPromptSet,
    *,
    repo_root: str | Path,
    specialized_prompt_text: str,
) -> str:
    repo_root = Path(repo_root).resolve()
    parts = [
        f"Repository root: {repo_root}",
        f"Prompt set slug: {prompt_set.slug}",
        "",
        "Run the repo-specific review prompt below against this repository.",
        "Stay in review mode and return only the final ticket markdown requested by the prompt.",
        "",
        specialized_prompt_text.strip(),
    ]
    return "\n".join(parts).strip() + "\n"


def build_review_refresh_prompt(
    prompt: SpecializedReviewPrompt,
    *,
    repo_root: str | Path,
) -> str:
    repo_root = Path(repo_root).resolve()
    specialized_prompt_text = prompt.specialized_prompt_path.read_text(encoding="utf-8").strip()
    previous_tickets_text = ""
    if prompt.previous_tickets_path is not None and prompt.previous_tickets_path.exists():
        previous_tickets_text = prompt.previous_tickets_path.read_text(encoding="utf-8").strip()

    parts = [
        f"Repository root: {repo_root}",
        f"Prompt set slug: {prompt.slug}",
        "",
        "Refresh the ticket pack for this review lens against the repository's current state.",
        "Use the repo-specific specialized prompt below as the review contract.",
        "If a previously reported issue is still valid, keep its existing ticket ID whenever practical.",
        "Remove tickets that no longer apply, update surviving tickets to match the current code, and add new IDs only for newly discovered issues.",
    ]
    if previous_tickets_text:
        parts.extend(
            [
                "",
                "## Previous Ticket Pack",
                previous_tickets_text,
            ]
        )
    parts.extend(
        [
            "",
            "## Repo-Specific Review Prompt",
            specialized_prompt_text,
            "",
            "Return only the current ticket markdown.",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def _sync_prompt_artifacts(staging_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in PROMPT_RUN_ARTIFACT_FILENAMES:
        source_path = staging_dir / filename
        target_path = target_dir / filename
        if source_path.exists():
            target_path.write_bytes(source_path.read_bytes())
            continue
        if target_path.exists():
            target_path.unlink()


def run_prompt_job(
    job_name: str,
    *,
    prompt_text: str,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    model: str | None = None,
    extra_args: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
    heartbeat_seconds: float = 20.0,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    output_dir = Path(output_dir)
    prompt_path = output_dir / "prompt.md"
    stdout_path = output_dir / "stdout.jsonl"
    stderr_path = output_dir / "stderr.log"
    last_message_path = output_dir / "last_message.md"

    with tempfile.TemporaryDirectory(prefix=f"flywire_wave_{job_name}_") as staging_dir_str:
        staging_dir = Path(staging_dir_str)
        staging_prompt_path = staging_dir / "prompt.md"
        staging_stdout_path = staging_dir / "stdout.jsonl"
        staging_stderr_path = staging_dir / "stderr.log"
        staging_last_message_path = staging_dir / "last_message.md"

        staging_prompt_path.write_text(prompt_text, encoding="utf-8")

        cmd = [
            runner,
            "exec",
            "--json",
            "--cd",
            str(repo_root),
            "--sandbox",
            sandbox,
            "--output-last-message",
            str(staging_last_message_path),
        ]
        if model:
            cmd.extend(["--model", model])
        if extra_args:
            cmd.extend(extra_args)

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_ticket_runner_popen_kwargs(),
        )
        assert process.stdin is not None
        process.stdin.write(prompt_text)
        process.stdin.close()

        return_code = _stream_ticket_process(
            process,
            raw_output_path=staging_stdout_path,
            progress_callback=progress_callback,
            heartbeat_seconds=heartbeat_seconds,
            heartbeat_label=job_name,
        )

        if not staging_stderr_path.exists():
            staging_stderr_path.write_text("", encoding="utf-8")
        if not staging_last_message_path.exists():
            staging_last_message_path.write_text("", encoding="utf-8")

        _sync_prompt_artifacts(staging_dir, output_dir)

    return {
        "job_name": job_name,
        "command": cmd,
        "returncode": int(return_code),
        "output_dir": str(output_dir),
        "prompt_path": str(prompt_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "last_message_path": str(last_message_path),
    }


def _write_stage_output_copy(source_path: Path, target_path: Path) -> Path:
    text = source_path.read_text(encoding="utf-8")
    normalized = text.rstrip()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(normalized + ("\n" if normalized else ""), encoding="utf-8")
    return target_path


def _worker_count(prompt_set_count: int, requested_max_workers: int | None) -> int:
    if prompt_set_count <= 0:
        return 1
    if requested_max_workers is None:
        return min(4, prompt_set_count)
    return max(1, min(requested_max_workers, prompt_set_count))


def _make_failure_result(
    *,
    stage: str,
    prompt_set: ReviewPromptSet,
    output_dir: Path,
    error_text: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "prompt_set": prompt_set.slug,
        "title": prompt_set.title,
        "returncode": -1,
        "output_dir": str(output_dir),
        "error": error_text,
    }


def _run_parallel_stage(
    prompt_sets: Sequence[ReviewPromptSet],
    *,
    stage: str,
    max_workers: int,
    worker: Callable[[ReviewPromptSet], dict[str, Any]],
    progress_callback: Callable[[str], None] | None,
) -> list[dict[str, Any]]:
    results_by_slug: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(worker, prompt_set): prompt_set for prompt_set in prompt_sets}
        for future in as_completed(future_map):
            prompt_set = future_map[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - defensive fallback
                result = _make_failure_result(
                    stage=stage,
                    prompt_set=prompt_set,
                    output_dir=Path("."),
                    error_text=str(exc),
                )
                if progress_callback is not None:
                    progress_callback(f"[{stage}:{prompt_set.slug}] failed with exception: {exc}")
            results_by_slug[prompt_set.slug] = result
    return [results_by_slug[prompt_set.slug] for prompt_set in prompt_sets if prompt_set.slug in results_by_slug]


def write_combined_ticket_report(
    review_results: Sequence[dict[str, Any]],
    output_dir: str | Path,
) -> Path | None:
    successful_results = [result for result in review_results if result.get("returncode") == 0]
    if not successful_results:
        return None

    output_path = Path(output_dir) / COMBINED_TICKETS_FILENAME
    parts = ["# Combined Review Tickets", ""]
    for result in successful_results:
        tickets_path_text = result.get("tickets_path")
        if not tickets_path_text:
            continue
        tickets_path = Path(tickets_path_text)
        if not tickets_path.exists():
            continue
        parts.extend(
            [
                f"## {result['prompt_set']}",
                "",
                tickets_path.read_text(encoding="utf-8").rstrip(),
                "",
            ]
        )
    output_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return output_path


def write_review_run_summary(summary: dict[str, Any], output_dir: str | Path) -> Path:
    output_path = Path(output_dir) / SUMMARY_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return output_path


def execute_specialized_review_refresh(
    prompts: Sequence[SpecializedReviewPrompt],
    *,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    model: str | None = None,
    extra_args: list[str] | None = None,
    max_workers: int | None = None,
    heartbeat_seconds: float = 20.0,
    progress_callback: Callable[[str], None] | None = None,
    job_runner: PromptJobRunner | None = None,
) -> dict[str, Any]:
    selected_prompts = list(prompts)
    if not selected_prompts:
        raise RuntimeError("No specialized review prompts selected.")

    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    job_runner = job_runner or run_prompt_job
    worker_count = _worker_count(len(selected_prompts), max_workers)

    def run_review(prompt: SpecializedReviewPrompt) -> dict[str, Any]:
        stage_output_dir = output_dir / "reviews" / prompt.slug
        if progress_callback is not None:
            progress_callback(f"[refresh:{prompt.slug}] starting")

        result = job_runner(
            f"refresh_{prompt.slug}",
            prompt_text=build_review_refresh_prompt(prompt, repo_root=repo_root),
            repo_root=repo_root,
            runner=runner,
            output_dir=stage_output_dir,
            sandbox=sandbox,
            model=model,
            extra_args=extra_args,
            progress_callback=(
                None
                if progress_callback is None
                else lambda message, slug=prompt.slug: progress_callback(f"[refresh:{slug}] {message}")
            ),
            heartbeat_seconds=heartbeat_seconds,
        )
        result.update(
            {
                "stage": "refresh",
                "prompt_set": prompt.slug,
                "title": prompt.title,
                "specialized_prompt_path": str(prompt.specialized_prompt_path),
                "previous_tickets_path": (
                    str(prompt.previous_tickets_path) if prompt.previous_tickets_path is not None else None
                ),
            }
        )
        if result["returncode"] == 0:
            tickets_path = _write_stage_output_copy(
                Path(result["last_message_path"]),
                stage_output_dir / TICKETS_FILENAME,
            )
            result["tickets_path"] = str(tickets_path)
        if progress_callback is not None:
            status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
            progress_callback(f"[refresh:{prompt.slug}] finished: {status_text}")
        return result

    review_results = _run_parallel_stage(
        selected_prompts,
        stage="refresh",
        max_workers=worker_count,
        worker=run_review,
        progress_callback=progress_callback,
    )
    combined_tickets_path = write_combined_ticket_report(review_results, output_dir)
    summary: dict[str, Any] = {
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "runner": runner,
        "sandbox": sandbox,
        "model": model,
        "extra_args": list(extra_args or []),
        "max_workers": worker_count,
        "prompt_set_slugs": [prompt.slug for prompt in selected_prompts],
        "review_results": review_results,
        "combined_tickets_path": str(combined_tickets_path) if combined_tickets_path else None,
    }
    summary["successful_review_count"] = sum(
        1 for result in review_results if result.get("returncode") == 0
    )
    summary["success"] = (
        len(review_results) == len(selected_prompts)
        and all(result.get("returncode") == 0 for result in review_results)
    )

    summary_path = output_dir / SUMMARY_FILENAME
    summary["summary_path"] = str(summary_path)
    write_review_run_summary(summary, output_dir)
    return summary


def execute_review_prompt_workflow(
    prompt_sets: Sequence[ReviewPromptSet],
    *,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    specializer_model: str | None = None,
    review_model: str | None = None,
    extra_args: list[str] | None = None,
    max_workers: int | None = None,
    continue_on_error: bool = False,
    heartbeat_seconds: float = 20.0,
    progress_callback: Callable[[str], None] | None = None,
    job_runner: PromptJobRunner | None = None,
) -> dict[str, Any]:
    selected_prompt_sets = list(prompt_sets)
    if not selected_prompt_sets:
        raise RuntimeError("No prompt sets selected.")

    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    job_runner = job_runner or run_prompt_job
    worker_count = _worker_count(len(selected_prompt_sets), max_workers)

    def run_specialization(prompt_set: ReviewPromptSet) -> dict[str, Any]:
        stage_output_dir = output_dir / "specialization" / prompt_set.slug
        if progress_callback is not None:
            progress_callback(f"[specialization:{prompt_set.slug}] starting")

        result = job_runner(
            f"specialization_{prompt_set.slug}",
            prompt_text=build_specialization_prompt(prompt_set, repo_root=repo_root),
            repo_root=repo_root,
            runner=runner,
            output_dir=stage_output_dir,
            sandbox=sandbox,
            model=specializer_model,
            extra_args=extra_args,
            progress_callback=(
                None
                if progress_callback is None
                else lambda message, slug=prompt_set.slug: progress_callback(
                    f"[specialization:{slug}] {message}"
                )
            ),
            heartbeat_seconds=heartbeat_seconds,
        )
        result.update(
            {
                "stage": "specialization",
                "prompt_set": prompt_set.slug,
                "title": prompt_set.title,
                "generic_prompt_path": str(prompt_set.generic_prompt_path),
                "specializer_prompt_path": str(prompt_set.specializer_prompt_path),
            }
        )
        if result["returncode"] == 0:
            specialized_prompt_path = _write_stage_output_copy(
                Path(result["last_message_path"]),
                stage_output_dir / SPECIALIZED_PROMPT_FILENAME,
            )
            result["specialized_prompt_path"] = str(specialized_prompt_path)
        if progress_callback is not None:
            status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
            progress_callback(f"[specialization:{prompt_set.slug}] finished: {status_text}")
        return result

    specialization_results = _run_parallel_stage(
        selected_prompt_sets,
        stage="specialization",
        max_workers=worker_count,
        worker=run_specialization,
        progress_callback=progress_callback,
    )

    successful_specializations = [
        result for result in specialization_results if result.get("returncode") == 0
    ]
    specialization_failures = [
        result for result in specialization_results if result.get("returncode") != 0
    ]

    review_results: list[dict[str, Any]] = []
    if successful_specializations and (continue_on_error or not specialization_failures):
        specialization_by_slug = {
            result["prompt_set"]: result for result in successful_specializations
        }

        def run_review(prompt_set: ReviewPromptSet) -> dict[str, Any]:
            specialization_result = specialization_by_slug[prompt_set.slug]
            stage_output_dir = output_dir / "reviews" / prompt_set.slug
            specialized_prompt_path = Path(specialization_result["specialized_prompt_path"])
            specialized_prompt_text = specialized_prompt_path.read_text(encoding="utf-8")

            if progress_callback is not None:
                progress_callback(f"[review:{prompt_set.slug}] starting")

            result = job_runner(
                f"review_{prompt_set.slug}",
                prompt_text=build_review_execution_prompt(
                    prompt_set,
                    repo_root=repo_root,
                    specialized_prompt_text=specialized_prompt_text,
                ),
                repo_root=repo_root,
                runner=runner,
                output_dir=stage_output_dir,
                sandbox=sandbox,
                model=review_model,
                extra_args=extra_args,
                progress_callback=(
                    None
                    if progress_callback is None
                    else lambda message, slug=prompt_set.slug: progress_callback(f"[review:{slug}] {message}")
                ),
                heartbeat_seconds=heartbeat_seconds,
            )
            result.update(
                {
                    "stage": "review",
                    "prompt_set": prompt_set.slug,
                    "title": prompt_set.title,
                    "specialized_prompt_path": str(specialized_prompt_path),
                }
            )
            if result["returncode"] == 0:
                tickets_path = _write_stage_output_copy(
                    Path(result["last_message_path"]),
                    stage_output_dir / TICKETS_FILENAME,
                )
                result["tickets_path"] = str(tickets_path)
            if progress_callback is not None:
                status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
                progress_callback(f"[review:{prompt_set.slug}] finished: {status_text}")
            return result

        review_prompt_sets = [
            prompt_set
            for prompt_set in selected_prompt_sets
            if prompt_set.slug in specialization_by_slug
        ]
        review_results = _run_parallel_stage(
            review_prompt_sets,
            stage="review",
            max_workers=_worker_count(len(review_prompt_sets), max_workers),
            worker=run_review,
            progress_callback=progress_callback,
        )

    combined_tickets_path = write_combined_ticket_report(review_results, output_dir)
    summary: dict[str, Any] = {
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "runner": runner,
        "sandbox": sandbox,
        "specializer_model": specializer_model,
        "review_model": review_model,
        "extra_args": list(extra_args or []),
        "max_workers": worker_count,
        "prompt_set_slugs": [prompt_set.slug for prompt_set in selected_prompt_sets],
        "specialization_results": specialization_results,
        "review_results": review_results,
        "combined_tickets_path": str(combined_tickets_path) if combined_tickets_path else None,
    }
    summary["successful_specialization_count"] = sum(
        1 for result in specialization_results if result.get("returncode") == 0
    )
    summary["successful_review_count"] = sum(
        1 for result in review_results if result.get("returncode") == 0
    )
    summary["success"] = (
        len(specialization_failures) == 0
        and len(review_results) == len(successful_specializations)
        and all(result.get("returncode") == 0 for result in review_results)
    )

    summary_path = output_dir / SUMMARY_FILENAME
    summary["summary_path"] = str(summary_path)
    write_review_run_summary(summary, output_dir)
    return summary
