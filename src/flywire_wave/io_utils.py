from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_root_ids(root_ids: Iterable[int], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rid in root_ids:
            f.write(f"{int(rid)}\n")
    return out


def read_root_ids(path: str | Path) -> list[int]:
    ids: list[int] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids.append(int(line))
    return ids


def write_json(data: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return out
