from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import zipfile


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


def write_json(data: Any, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return out


def write_jsonl(records: Iterable[Mapping[str, Any]], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    dict(record),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
            )
            handle.write("\n")
    return out


def write_csv_rows(
    *,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
    out_path: str | Path,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})
    return out


def write_deterministic_npz(
    arrays: Mapping[str, np.ndarray | Sequence[Any]],
    out_path: str | Path,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for array_name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(
                buffer,
                np.asarray(arrays[array_name]),
                allow_pickle=False,
            )
            info = zipfile.ZipInfo(f"{array_name}.npy")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue())
    return out
