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
        # min_samples_leaf>1 để bớt học thuộc nhiễu của từng run
        "RandomForest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", min_samples_leaf=2,
            random_state=0, n_jobs=1),
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
    ap.add_argument("--folds", type=int, default=5,
                    help="GroupKFold theo run_id (mỗi run chỉ nằm ở 1 fold test)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    from sklearn.model_selection import GroupKFold

    df = ds.load(args.data).reset_index(drop=True)
    n_runs = df["run_id"].nunique()
    k = max(2, min(args.folds, n_runs))
    print("Dataset: %d window, %d run, %d fold GroupKFold" % (len(df), n_runs, k))
    print("Phân bố nhãn:", df["label"].value_counts().to_dict())

    # Dự đoán out-of-fold (OOF) cho MỌI phương pháp: mỗi window được dự đoán
    # bởi model KHÔNG thấy run của nó lúc train -> đánh giá trung thực.
    methods = ["StaticThreshold", "EWMA"] + list(get_models().keys())
    oof = {m: np.zeros(len(df), dtype=int) for m in methods}
    fold_rows = []
    gkf = GroupKFold(n_splits=k)
    for fi, (itr, ite) in enumerate(gkf.split(df, df["y"], groups=df["run_id"])):
        train, test = df.iloc[itr], df.iloc[ite]
        Xtr, ytr = ds.XY(train)
        Xte, yte = ds.XY(test)
        labels_te = test["label"].tolist()
        normal_pr = train.loc[train["label"] == "normal", "packet_rate"].values
        st = StaticThreshold.fit_from_normal(normal_pr, pct=99, k=1.2)
        preds = {"StaticThreshold": np.array(st.predict_series(test["packet_rate"].values)),
                 "EWMA": np.array(_ewma_per_run(test))}
        for name, model in get_models().items():
            model.fit(Xtr, ytr)
            preds[name] = model.predict(Xte).astype(int)
        for name, p in preds.items():
            oof[name][ite] = p
            m = eval_pred(yte, p, labels_te)
            fold_rows.append({"fold": fi, "method": name, **{
                c: m[c] for c in ["precision", "recall", "f1", "fpr", "flash_fpr"]}})

    folds = pd.DataFrame(fold_rows)
    folds.to_csv(os.path.join(args.out, "cv_folds.csv"), index=False)

    # Bảng chính: chỉ số trên toàn bộ dự đoán OOF + std giữa các fold
    labels_all = df["label"].tolist()
    rows = []
    for name in methods:
        m = eval_pred(df["y"].values, oof[name], labels_all)
        sd = folds[folds["method"] == name][["recall", "f1", "flash_fpr"]].std()
        s5 = df["scenario"].str.contains("S5")
        s5_flash = (s5 & (df["label"] == "flash")).values
        rows.append({"method": name,
                     "precision": m["precision"], "recall": m["recall"],
                     "f1": m["f1"], "fpr": m["fpr"], "flash_fpr": m["flash_fpr"],
                     "flash_fpr_S5": (oof[name][s5_flash].mean()
                                      if s5_flash.any() else None),
                     "recall_sd": sd["recall"], "f1_sd": sd["f1"],
                     "flash_fpr_sd": sd["flash_fpr"]})
    table = pd.DataFrame(rows).round(4)
    csv_path = os.path.join(args.out, "model_compare.csv")
    table.to_csv(csv_path, index=False)

    # Ma trận nhầm lẫn của RF theo nhãn chi tiết (normal/flash/ddos)
    cm = pd.crosstab(df["label"], oof["RandomForest"], rownames=["nhãn thật"],
                     colnames=["dự đoán (1=DDoS)"])
    cm.to_csv(os.path.join(args.out, "rf_confusion_by_label.csv"))

    # Model triển khai: train trên TOÀN BỘ dataset (CV ở trên chỉ để ước lượng)
    import pickle
    models_dir = os.path.join(ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    name2file = {"LogisticRegression": "lr.pkl", "RandomForest": "rf.pkl",
                 "XGBoost": "xgb.pkl"}
    X_all, y_all = ds.XY(df)
    importances = {}
    for name, model in get_models().items():
        model.fit(X_all, y_all)
        imp = _importance(model)
        if imp is not None:
            importances[name] = dict(zip(FEATURE_NAMES, [float(x) for x in imp]))
        with open(os.path.join(models_dir, name2file[name]), "wb") as fh:
            pickle.dump(model, fh)
    with open(os.path.join(args.out, "feature_importance.json"), "w") as f:
        json.dump(importances, f, indent=2)
    with open(os.path.join(models_dir, "model_card.json"), "w") as f:
        json.dump({"data": args.data, "n_windows": int(len(df)), "n_runs": int(n_runs),
                   "features": FEATURE_NAMES, "label_map": ds.LABEL_MAP,
                   "cv": "GroupKFold k=%d theo run_id" % k}, f, indent=2)
    print("[info] đã lưu model (train trên toàn bộ dataset) -> models/*.pkl")

    # Báo cáo markdown
    md = ["# Tuần 7 — So sánh phương pháp phát hiện (GroupKFold theo run)\n",
          "- Dataset: `%s` — %d window, %d run, nhãn: %s" % (
              args.data, len(df), n_runs, df["label"].value_counts().to_dict()),
          "- Đánh giá: dự đoán out-of-fold, %d fold, mỗi run chỉ ở 1 fold test "
          "(không rò rỉ giữa các window cùng run). ± = độ lệch chuẩn giữa fold.\n" % k,
          "| Phương pháp | Precision | Recall | F1 | FPR | **Flash-FPR** | Flash-FPR (S5) |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in table.to_dict("records"):
        md.append("| %s | %.3f | %.3f ± %.3f | %.3f ± %.3f | %.3f | **%.3f** ± %.3f | %s |" % (
            r["method"], r["precision"], r["recall"], r["recall_sd"] or 0, r["f1"],
            r["f1_sd"] or 0, r["fpr"], r["flash_fpr"] or 0, r["flash_fpr_sd"] or 0,
            "—" if pd.isna(r["flash_fpr_S5"]) else "%.3f" % r["flash_fpr_S5"]))
    md.append("\nMa trận nhầm lẫn RandomForest theo nhãn chi tiết:\n")
    md.append("```\n%s\n```" % cm.to_string())
    if "RandomForest" in importances:
        top = sorted(importances["RandomForest"].items(), key=lambda kv: -kv[1])
        md.append("\nFeature quan trọng nhất (RF): " +
                  ", ".join("%s=%.2f" % kv for kv in top[:4]))
    with open(os.path.join(args.out, "model_report.md"), "w") as f:
        f.write("\n".join(md) + "\n")

    print("\n=== So sánh phương pháp (out-of-fold, chia theo run) ===")
    print(table.to_string(index=False))
    print("\n", cm)
    print("\nĐã lưu:", csv_path, "và model_report.md")
    return table


def _ewma_per_run(test_df):
    """Chạy EWMA riêng cho từng run theo đúng thứ tự thời gian."""
    preds = pd.Series(0, index=test_df.index, dtype=int)
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
