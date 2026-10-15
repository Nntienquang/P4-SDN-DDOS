"""
dataset.py — Nạp dataset UniFlash-DDoS và chia train/test KHÔNG rò rỉ.

Cột bắt buộc: timestamp, run_id, scenario, label (+ các feature trong
FEATURE_NAMES), tùy chọn transition (1 = window chuyển pha, nên loại khi train).

Chia theo run_id (GroupShuffleSplit): các window cùng một lần chạy rất giống
nhau, nếu chia ngẫu nhiên theo dòng model sẽ học "dấu vết run" -> accuracy ảo.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "controller"))
from features import FEATURE_NAMES  # noqa: E402

LABEL_MAP = {"normal": 0, "flash": 0, "ddos": 1, "syn": 1, "udp": 1}


def load(path, drop_transition=True):
    df = pd.read_csv(path)
    if drop_transition and "transition" in df.columns:
        df = df[df["transition"] != 1].copy()
    missing = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing:
        raise ValueError("Thiếu cột feature: %s" % missing)
    df["y"] = df["label"].map(LABEL_MAP)
    if df["y"].isna().any():
        bad = df.loc[df["y"].isna(), "label"].unique()
        raise ValueError("Nhãn lạ không map được: %s" % bad)
    return df


def split_by_run(df, test_frac=0.3, seed=42):
    """Chia theo run_id. Trả về (train_df, test_df)."""
    from sklearn.model_selection import GroupShuffleSplit
    gss = GroupShuffleSplit(n_splits=1, test_size=test_frac, random_state=seed)
    idx_tr, idx_te = next(gss.split(df, df["y"], groups=df["run_id"]))
    return df.iloc[idx_tr].copy(), df.iloc[idx_te].copy()


def XY(df):
    return df[FEATURE_NAMES].values, df["y"].values
