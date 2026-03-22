from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.mixed_fidelity_inspection import (
    execute_mixed_fidelity_inspection_workflow,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an offline mixed-fidelity surrogate inspection against higher-fidelity "
            "reference variants built from local artifacts only."
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
        required=True,
        help="surface_wave arm_id to inspect.",
    )
    parser.add_argument(
        "--reference-root",
        action="append",
        default=[],
        help=(
            "Optional explicit root reference in '<root_id>:<reference_morphology_class>' "
            "form. Repeat to inspect multiple roots. When omitted, the workflow uses the "
            "resolved policy recommendations and then falls back to the next higher class."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for the generated inspection report.",
    )
    args = parser.parse_args(argv)

    summary = execute_mixed_fidelity_inspection_workflow(
        manifest_path=args.manifest,
        config_path=args.config,
        schema_path=args.schema,
        design_lock_path=args.design_lock,
        arm_id=args.arm_id,
        reference_root_specs=args.reference_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
