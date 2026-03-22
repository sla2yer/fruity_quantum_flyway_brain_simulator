#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.coupling_inspection import parse_edge_spec, read_edge_specs
from flywire_wave.io_utils import ensure_dir, read_root_ids
from flywire_wave.milestone7_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    build_milestone7_readiness_paths,
    discover_milestone7_edge_specs,
    generate_milestone7_readiness_report,
)
from flywire_wave.readiness_contract import FOLLOW_ON_READINESS_KEY, READY_FOR_FOLLOW_ON_WORK_KEY
from flywire_wave.registry import load_synapse_registry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 7 integration verification pass and publish a readiness report."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file that defines the local verification bundle.",
    )
    parser.add_argument(
        "--edge",
        action="append",
        dest="edges",
        default=[],
        help="Optional edge spec in 'pre:post', 'pre,post', or 'pre->post' form. Repeatable.",
    )
    parser.add_argument(
        "--edges-file",
        help="Optional newline-delimited edge list. When omitted, edges are discovered from the scoped synapse registry.",
    )
    parser.add_argument(
        "--fixture-test-target",
        action="append",
        dest="fixture_test_targets",
        default=[],
        help="Optional unittest target to add to the focused verification suite. Repeatable.",
    )
    parser.add_argument(
        "--skip-fixture-tests",
        action="store_true",
        help="Skip the focused fixture verification suite.",
    )
    parser.add_argument(
        "--skip-registry",
        action="store_true",
        help="Skip scripts/build_registry.py and reuse existing registry outputs.",
    )
    parser.add_argument(
        "--skip-selection",
        action="store_true",
        help="Skip scripts/01_select_subset.py and reuse the selected-root alias plus scoped synapse registry.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip scripts/03_build_wave_assets.py and reuse existing coupling bundles.",
    )
    parser.add_argument(
        "--skip-coupling-inspection",
        action="store_true",
        help="Skip scripts/08_coupling_inspection.py and reuse an existing report bundle.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    coupling_inspection_dir = Path(paths["coupling_inspection_dir"])
    pending_command_log_dir = ensure_dir(coupling_inspection_dir / "_milestone_7_readiness_pending" / "commands")

    fixture_targets = list(DEFAULT_FIXTURE_TEST_TARGETS)
    fixture_targets.extend(args.fixture_test_targets)
    fixture_verification = (
        _skipped_command_result("fixture_verification", "skipped by --skip-fixture-tests")
        if args.skip_fixture_tests
        else _run_command(
            name="fixture_verification",
            command=[sys.executable, "-m", "unittest", *fixture_targets],
            log_dir=pending_command_log_dir,
        )
    )

    registry_command = (
        _skipped_command_result("build_registry", "skipped by --skip-registry")
        if args.skip_registry
        else _run_command(
            name="build_registry",
            command=[sys.executable, str(ROOT / "scripts" / "build_registry.py"), "--config", str(args.config)],
            log_dir=pending_command_log_dir,
        )
    )

    selection_command = (
        _skipped_command_result("select_subset", "skipped by --skip-selection")
        if args.skip_selection
        else _run_command(
            name="select_subset",
            command=[sys.executable, str(ROOT / "scripts" / "01_select_subset.py"), "--config", str(args.config)],
            log_dir=pending_command_log_dir,
        )
    )

    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs resolved for the Milestone 7 readiness pass.")

    edge_specs = _resolve_edge_specs(args=args, cfg=cfg)
    if not edge_specs:
        synapse_registry_path = Path(paths["processed_coupling_dir"]) / "synapse_registry.csv"
        if synapse_registry_path.exists():
            synapse_registry = load_synapse_registry(synapse_registry_path)
            edge_specs = sorted(
                {
                    (int(pre_root_id), int(post_root_id))
                    for pre_root_id, post_root_id in zip(
                        synapse_registry["pre_root_id"].tolist(),
                        synapse_registry["post_root_id"].tolist(),
                    )
                }
            )
    if not edge_specs:
        edge_specs = discover_milestone7_edge_specs(paths["manifest_json"])
    if not edge_specs:
        raise RuntimeError("No Milestone 7 edges were available for the readiness pass.")

    readiness_paths = build_milestone7_readiness_paths(paths["coupling_inspection_dir"], edge_specs)
    command_log_dir = ensure_dir(readiness_paths["report_dir"] / "commands")
    _relocate_command_logs(
        command_results=[fixture_verification, registry_command, selection_command],
        destination_dir=command_log_dir,
    )

    build_command = (
        _skipped_command_result("build_wave_assets", "skipped by --skip-build")
        if args.skip_build
        else _run_command(
            name="build_wave_assets",
            command=[sys.executable, str(ROOT / "scripts" / "03_build_wave_assets.py"), "--config", str(args.config)],
            log_dir=command_log_dir,
        )
    )

    if args.skip_coupling_inspection:
        coupling_inspection_command = _skipped_command_result(
            "coupling_inspection",
            "skipped by --skip-coupling-inspection",
        )
    else:
        coupling_inspection_command = _run_coupling_inspection_command(
            config_path=args.config,
            edge_specs=edge_specs,
            log_dir=command_log_dir,
        )

    summary = generate_milestone7_readiness_report(
        config_path=args.config,
        manifest_path=paths["manifest_json"],
        connectivity_registry_path=paths["connectivity_registry_csv"],
        synapse_registry_path=Path(paths["processed_coupling_dir"]) / "synapse_registry.csv",
        synapse_registry_provenance_path=Path(paths["processed_coupling_dir"]) / "synapse_registry_provenance.json",
        coupling_inspection_dir=paths["coupling_inspection_dir"],
        root_ids=root_ids,
        edge_specs=edge_specs,
        fixture_verification=fixture_verification,
        registry_command=registry_command,
        selection_command=selection_command,
        build_command=build_command,
        coupling_inspection_command=coupling_inspection_command,
    )
    print(
        json.dumps(
            {
                "report_version": summary["report_version"],
                "readiness_status": summary[FOLLOW_ON_READINESS_KEY]["status"],
                READY_FOR_FOLLOW_ON_WORK_KEY: summary[FOLLOW_ON_READINESS_KEY][READY_FOR_FOLLOW_ON_WORK_KEY],
                "markdown_path": summary["markdown_path"],
                "json_path": summary["json_path"],
                "coupling_inspection_summary_path": summary["coupling_inspection_summary_path"],
            },
            indent=2,
        )
    )
    return 1 if summary[FOLLOW_ON_READINESS_KEY]["status"] == "hold" else 0


def _resolve_edge_specs(*, args: argparse.Namespace, cfg: dict[str, object]) -> list[tuple[int, int]]:
    edge_specs = [parse_edge_spec(value) for value in args.edges]
    if args.edges_file:
        edge_specs.extend(read_edge_specs(args.edges_file))
    return sorted({(int(pre_root_id), int(post_root_id)) for pre_root_id, post_root_id in edge_specs})


def _run_coupling_inspection_command(
    *,
    config_path: str,
    edge_specs: list[tuple[int, int]],
    log_dir: Path,
) -> dict[str, object]:
    command: list[str] = [
        sys.executable,
        str(ROOT / "scripts" / "08_coupling_inspection.py"),
        "--config",
        str(config_path),
    ]
    for pre_root_id, post_root_id in edge_specs:
        command.extend(["--edge", f"{pre_root_id}:{post_root_id}"])
    return _run_command(
        name="coupling_inspection",
        command=command,
        log_dir=log_dir,
    )


def _run_command(*, name: str, command: list[str], log_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    payload: dict[str, object] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
        "stdout_log_path": str(stdout_path.resolve()),
        "stderr_log_path": str(stderr_path.resolve()),
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, object] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    candidate = stripped[start:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _relocate_command_logs(*, command_results: list[dict[str, object]], destination_dir: Path) -> None:
    ensure_dir(destination_dir)
    for result in command_results:
        for field_name in ["stdout_log_path", "stderr_log_path"]:
            source_path_value = str(result.get(field_name, "") or "")
            if not source_path_value:
                continue
            source_path = Path(source_path_value)
            if not source_path.exists():
                continue
            destination_path = destination_dir / source_path.name
            if source_path.resolve() == destination_path.resolve():
                continue
            shutil.move(str(source_path), str(destination_path))
            result[field_name] = str(destination_path.resolve())


def _skipped_command_result(name: str, reason: str) -> dict[str, object]:
    return {
        "name": name,
        "status": "skipped",
        "command": "",
        "returncode": None,
        "reason": reason,
        "stdout_log_path": "",
        "stderr_log_path": "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
