#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.surface_wave_inspection import execute_surface_wave_inspection_workflow


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic local surface-wave parameter sweep and publish "
            "offline inspection reports."
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
        "--arm-id",
        action="append",
        dest="arm_ids",
        help="Optional surface-wave arm_id filter. Repeat to inspect multiple arms.",
    )
    parser.add_argument(
        "--use-manifest-seed-sweep",
        action="store_true",
        help="Expand the manifest seed sweep before running the surface-wave audit.",
    )
    parser.add_argument(
        "--sweep-spec",
        help="Optional YAML/JSON sweep spec describing explicit parameter sets, grids, or seeds.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for the generated inspection report.",
    )
    args = parser.parse_args(argv)

    summary = execute_surface_wave_inspection_workflow(
        manifest_path=args.manifest,
        config_path=args.config,
        schema_path=args.schema,
        design_lock_path=args.design_lock,
        arm_ids=args.arm_ids,
        use_manifest_seed_sweep=bool(args.use_manifest_seed_sweep),
        sweep_spec_path=args.sweep_spec,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
