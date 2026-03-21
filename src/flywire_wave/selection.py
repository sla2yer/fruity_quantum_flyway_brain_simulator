from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_ID_CANDIDATES = [
    "root_id",
    "pt_root_id",
    "id",
    "rootid",
]

SUPER_CLASS_CANDIDATES = [
    "super_class",
    "superclass",
    "class_super",
]


def _find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str:
    lower_to_original = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_to_original:
            return lower_to_original[candidate.lower()]
    raise KeyError(f"None of the candidate columns exist: {candidates}")


def load_classification_table(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Could not find classification CSV at {csv_path}. "
            "Download it from the Codex FAFB portal and place it there."
        )
    return pd.read_csv(csv_path)


def select_visual_subset(
    df: pd.DataFrame,
    *,
    super_class: str = "visual",
    limit: int = 12,
    sort_by: str = "root_id",
) -> pd.DataFrame:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    super_col = _find_first_existing(df, SUPER_CLASS_CANDIDATES)

    out = df.copy()
    out[super_col] = out[super_col].astype(str)
    out = out[out[super_col].str.lower() == super_class.lower()].copy()
    out[root_col] = pd.to_numeric(out[root_col], errors="coerce")
    out = out.dropna(subset=[root_col]).copy()
    out[root_col] = out[root_col].astype("int64")
    out = out.drop_duplicates(subset=[root_col])

    sort_col = root_col if sort_by == "root_id" else sort_by
    if sort_col in out.columns:
        out = out.sort_values(sort_col)

    return out.head(limit).reset_index(drop=True)


def extract_root_ids(df: pd.DataFrame) -> list[int]:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    return [int(x) for x in df[root_col].tolist()]
