#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify FlyWire/CAVE access for FAFB public.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    cfg = load_config(args.config)
    datastack = cfg["dataset"]["datastack_name"]
    version = cfg["dataset"]["materialization_version"]
    token = os.getenv("FLYWIRE_TOKEN", "").strip()

    try:
        from caveclient import CAVEclient
    except Exception as exc:
        raise RuntimeError("caveclient is not installed. Run: pip install -r requirements.txt") from exc

    client = CAVEclient(datastack_name=datastack, auth_token=token or None)
    tables = client.materialize.get_tables()
    versions = client.materialize.get_versions()

    print(f"Datastack: {datastack}")
    print(f"Materialization versions visible: {versions}")
    print(f"Requested version: {version}")
    print(f"Tables: {tables}")

    if int(version) not in [int(v) for v in versions]:
        raise RuntimeError(f"Requested materialization version {version} is not visible in this environment.")

    try:
        from fafbseg import flywire

        if token:
            flywire.set_chunkedgraph_secret(token)
        flywire.set_default_dataset(cfg["dataset"].get("flywire_dataset", "public"))
        print("fafbseg token setup: OK")
    except Exception as exc:
        print(f"Warning: fafbseg verification skipped/failed: {exc}")

    print("Access looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
