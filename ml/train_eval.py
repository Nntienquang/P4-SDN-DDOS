"""
train_eval.py — Train LR / RF / XGBoost và so với baseline threshold/EWMA.

Chạy:
  python3 ml/train_eval.py --data data/uniflash_v01.csv --out experiments/week7

In bảng so sánh Precision/Recall/F1/FPR/Flash-FPR và lưu confusion matrix,
feature importance. XGBoost là tùy chọn (bỏ qua nếu chưa cài).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "controller"))
sys.path.insert(0, os.path.join(ROOT, "baseline"))
sys.path.insert(0, os.path.join(ROOT, "metrics"))
sys.path.insert(0, HERE)

from features import FEATURE_NAMES            # noqa: E402
from detectors import StaticThreshold, EWMA   # noqa: E402
from service_metrics import security_metrics, flash_false_positive_rate  # noqa: E402
import dataset as ds                           # noqa: E402


def get_models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    models = {
        "LogisticRegression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced")),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=0),
    }
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = XGBClassifier(
            n_estimators=200, max_depth=5, eval_metric="logloss",
            use_label_encoder=False, random_state=0)
    except Exception:
        print("[info] Bỏ qua XGBoost (chưa cài). Cài: pip install xgboost")
    return models


def eval_pred(y_true, y_pred, labels_str):
    m = security_metrics(list(y_true), list(y_pred))
    m["flash_fpr"] = flash_false_positive_rate(list(labels_str), list(y_pred))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="experiments/week7")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    df = ds.load(args.data)
    train, test = ds.split_by_run(df, test_frac=0.3, seed=args.seed)
    Xtr, ytr = ds.XY(train)
    Xte, yte = ds.XY(test)
    labels_te = test["label"].tolist()
    print("Train: %d window (%d run), Test: %d window (%d run)" % (
        len(train), train["run_id"].nunique(),
        len(test), test["run_id"].nunique()))

    rows = []

    # --- Baseline threshold/EWMA trên packet_rate ---
    pr_col = FEATURE_NAMES.index("packet_rate")
    normal_pr = train.loc[train["y"] == 0, "packet_rate"].values
    st = StaticThreshold.fit_from_normal(normal_pr, pct=99, k=1.0)
    st_pred = st.predict_series(Xte[:, pr_col])
    rows.append(("StaticThreshold", eval_pred(yte, st_pred, labels_te)))

    ewma = EWMA(alpha=0.2, k=3.0, warmup=10)
    # EWMA cần chạy theo thời gian của từng run để đúng ngữ nghĩa
    ew_pred = _ewma_per_run(test)
    rows.append(("EWMA", eval_pred(yte, ew_pred, labels_te)))

    # --- Models ---
    import pickle
    models_dir = os.path.join(ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    name2file = {"LogisticRegression": "lr.pkl", "RandomForest": "rf.pkl",
                 "XGBoost": "xgb.pkl"}
    importances = {}
    for name, model in get_models().items():
        model.fit(Xtr, ytr)
        pred = model.predict(Xte)
        rows.append((name, eval_pred(yte, pred, labels_te)))
        imp = _importance(model)
        if imp is not None:
            importances[name] = dict(zip(FEATURE_NAMES, [float(x) for x in imp]))
        # lưu model để detector/run_matrix dùng (tuần 8-10)
        with open(os.path.join(models_dir, name2file[name]), "wb") as fh:
            pickle.dump(model, fh)
    print("[info] đã lưu model -> models/*.pkl")

    # --- Bảng kết quả ---
    table = pd.DataFrame(
        [{"method": n, **{k: m[k] for k in
          ["precision", "recall", "f1", "fpr", "flash_fpr"]}} for n, m in rows])
    table = table.round(4)
    csv_path = os.path.join(args.out, "model_compare.csv")
    table.to_csv(csv_path, index=False)
    with open(os.path.join(args.out, "feature_importance.json"), "w") as f:
        json.dump(importances, f, indent=2)

    print("\n=== So sánh phương pháp (test theo run) ===")
    print(table.to_string(index=False))
    print("\nĐã lưu:", csv_path)
    return table


def _ewma_per_run(test_df):
    """Chạy EWMA riêng cho từng run theo đúng thứ tự thời gian."""
    preds = pd.Series(index=test_df.index, dtype=int)
    for _, grp in test_df.sort_values("timestamp").groupby("run_id"):
        ew = EWMA(alpha=0.2, k=3.0, warmup=5)
        for idx, val in grp["packet_rate"].items():
            preds[idx] = ew.predict(val)
    return preds.loc[test_df.index].tolist()


def _importance(model):
    if hasattr(model, "feature_importances_"):
        return model.feature_importances_
    if hasattr(model, "named_steps"):
        for step in model.named_steps.values():
            if hasattr(step, "coef_"):
                return np.abs(step.coef_[0])
    return None


if __name__ == "__main__":
    main()
