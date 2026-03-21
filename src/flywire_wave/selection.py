from __future__ import annotations

from pathlib import Path
from typing import Iterable

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

PROJECT_ROLE_CANDIDATES = [
    "project_role",
    "role_in_project",
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


def load_selection_table(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find selection table at {csv_path}.")
    return pd.read_csv(csv_path)


def select_visual_subset(
    df: pd.DataFrame,
    *,
    super_class: str | None = "visual_projection",
    super_classes: Iterable[str] | None = None,
    project_roles: Iterable[str] | None = None,
    limit: int = 12,
    sort_by: str = "root_id",
) -> pd.DataFrame:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)

    out = df.copy()
    if super_classes is None:
        super_classes = [super_class] if super_class else []

    normalized_super_classes = [str(value).strip().lower() for value in super_classes if str(value).strip()]
    if normalized_super_classes:
        super_col = _find_first_existing(df, SUPER_CLASS_CANDIDATES)
        out[super_col] = out[super_col].astype(str)
        out = out[out[super_col].str.lower().isin(normalized_super_classes)].copy()

    normalized_project_roles = [str(value).strip().lower() for value in project_roles or [] if str(value).strip()]
    if normalized_project_roles:
        role_col = _find_first_existing(df, PROJECT_ROLE_CANDIDATES)
        out[role_col] = out[role_col].astype(str)
        out = out[out[role_col].str.lower().isin(normalized_project_roles)].copy()

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
