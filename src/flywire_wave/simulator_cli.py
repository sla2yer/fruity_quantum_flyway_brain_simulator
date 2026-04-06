from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .simulator_execution import execute_manifest_simulation
from .simulator_result_contract import BASELINE_MODEL_MODE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a manifest into runnable simulator arms, execute the supported "
            "model mode locally, and write deterministic result bundles."
        )
    )
    parser.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    parser.add_argument("--manifest", required=True, help="Path to the experiment manifest YAML.")
    parser.add_argument("--schema", required=True, help="Path to the manifest schema JSON.")
    parser.add_argument(
        "--design-lock",
        required=True,
        help="Path to the authoritative design-lock YAML.",
    )
    parser.add_argument(
        "--model-mode",
        default=BASELINE_MODEL_MODE,
        help="Simulator model mode to execute. Supported: baseline, surface_wave.",
    )
    parser.add_argument("--arm-id", help="Optional manifest arm_id filter.")
    parser.add_argument(
        "--use-manifest-seed-sweep",
        action="store_true",
        help="Expand the manifest seed sweep into one deterministic run per seed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    summary = execute_manifest_simulation(
        manifest_path=Path(args.manifest),
        config_path=Path(args.config),
        schema_path=Path(args.schema),
        design_lock_path=Path(args.design_lock),
        model_mode=args.model_mode,
        arm_id=args.arm_id,
        use_manifest_seed_sweep=args.use_manifest_seed_sweep,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


__all__ = ["build_parser", "main"]
