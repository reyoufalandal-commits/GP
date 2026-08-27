#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _plot_decision_counts(run_summary: dict, out: Path) -> None:
    counts = run_summary.get("decision_counts", {})
    if not counts:
        return
    labels = list(counts.keys())
    vals = [counts[k] for k in labels]
    plt.figure(figsize=(8, 4))
    sns.barplot(x=labels, y=vals, palette="viridis")
    plt.title("Runtime Lab Decision Counts")
    plt.ylabel("Rows")
    plt.xlabel("Decision Label")
    plt.xticks(rotation=12)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _plot_macro_f1(scorecard: dict, out: Path) -> None:
    tc = scorecard.get("train_compare", {})
    if not tc:
        return
    base = tc.get("base_macro_f1", 0.0)
    boost = tc.get("boost_macro_f1", 0.0)
    plt.figure(figsize=(6, 4))
    sns.barplot(x=["Base", "Rare-Boost"], y=[base, boost], palette="mako")
    plt.ylim(0, 1.0)
    plt.title("Macro F1: Before vs After")
    plt.ylabel("Macro F1")
    for i, v in enumerate([base, boost]):
        plt.text(i, v + 0.02, f"{v:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _plot_rare_classes_f1(metrics_rare_boost: dict, out: Path) -> None:
    rep = metrics_rare_boost.get("classification_report", {})
    targets = ["PortScan", "Web Attack � Brute Force", "FTP-Patator", "DoS slowloris"]
    rows = []
    for t in targets:
        if t in rep:
            rows.append((t, float(rep[t].get("f1-score", 0.0))))
    if not rows:
        return
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    plt.figure(figsize=(8, 4))
    sns.barplot(x=names, y=vals, palette="crest")
    plt.ylim(0, 1.0)
    plt.title("Rare / Weak Class F1 (Boosted Model)")
    plt.ylabel("F1")
    plt.xticks(rotation=15)
    for i, v in enumerate(vals):
        plt.text(i, v + 0.02, f"{v:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _plot_confusion_heatmap(metrics_rare_boost: dict, out: Path) -> None:
    cm = metrics_rare_boost.get("confusion_matrix")
    rep = metrics_rare_boost.get("classification_report", {})
    if cm is None:
        return
    labels = [k for k in rep.keys() if k not in ("accuracy", "macro avg", "weighted avg")]
    if len(labels) != len(cm):
        labels = [f"C{i}" for i in range(len(cm))]
    arr = np.array(cm, dtype=float)
    plt.figure(figsize=(8, 6))
    sns.heatmap(arr, cmap="Blues", cbar=True)
    plt.title("Confusion Matrix (Rare-Boost)")
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.xticks(np.arange(len(labels)) + 0.5, labels, rotation=45, ha="right", fontsize=8)
    plt.yticks(np.arange(len(labels)) + 0.5, labels, rotation=0, fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _plot_holdout_unknown_recall(scorecard: dict, out: Path) -> None:
    results = scorecard.get("holdout_multi", {}).get("results", [])
    if not results:
        return
    names = [r.get("holdout", "holdout") for r in results]
    vals = [float(r.get("recommendation", {}).get("unknown_recall", 0.0)) for r in results]
    plt.figure(figsize=(8, 4))
    sns.barplot(x=names, y=vals, palette="flare")
    plt.ylim(0, 1.05)
    plt.title("Holdout Unknown Recall (CIC)")
    plt.ylabel("Unknown Recall")
    plt.xticks(rotation=15)
    for i, v in enumerate(vals):
        plt.text(i, v + 0.02, f"{v:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _plot_unsw_unknown(scorecard: dict, out: Path) -> None:
    u = scorecard.get("unsw_unknown_eval", {})
    uc = scorecard.get("unsw_novelty_calibrator_eval", {})
    if not u:
        return
    labels = ["Default", "AdaptiveGates", "Calibrator"]
    vals = [
        float(u.get("unknown_recall_attack_uncertain", 0.0)),
        float(u.get("adaptive_unknown_recall_attack_uncertain", 0.0)),
        float(uc.get("calibrator_unknown_recall", 0.0)),
    ]
    plt.figure(figsize=(7, 4))
    sns.barplot(x=labels, y=vals, palette="rocket")
    plt.ylim(0, 1.0)
    plt.title("UNSW Unknown Recall Comparison")
    plt.ylabel("Unknown Recall")
    for i, v in enumerate(vals):
        plt.text(i, v + 0.02, f"{v:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _save_model_card(
    *,
    out_path: Path,
    model_name: str,
    role: str,
    inputs: str,
    output: str,
    key_metric_name: str,
    key_metric_value: str,
) -> None:
    fig = plt.figure(figsize=(10, 4.8))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_title(f"{model_name}", fontsize=18, fontweight="bold", pad=14)
    body = (
        f"Role: {role}\n\n"
        f"Inputs: {inputs}\n\n"
        f"Output: {output}\n\n"
        f"Key metric: {key_metric_name} = {key_metric_value}"
    )
    ax.text(
        0.02,
        0.90,
        body,
        fontsize=12,
        va="top",
        ha="left",
        bbox={"boxstyle": "round,pad=0.6", "facecolor": "#f3f6fa", "edgecolor": "#c8d2e1"},
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close(fig)


def _generate_model_cards(
    *,
    out_dir: Path,
    scorecard: dict,
    metrics_rare_boost: dict,
    metrics_anomaly_val: dict,
    runtime: dict,
) -> list[str]:
    cards_dir = out_dir / "ModelCards"
    _ensure_dir(cards_dir)

    macro_f1 = _safe_float(
        metrics_rare_boost.get("classification_report", {}).get("macro avg", {}).get("f1-score", 0.0)
    )
    attack_recall = _safe_float(metrics_anomaly_val.get("recall_attack", 0.0))
    default_unsw_recall = _safe_float(scorecard.get("unsw_unknown_eval", {}).get("unknown_recall_attack_uncertain", 0.0))
    adaptive_unsw_recall = _safe_float(
        scorecard.get("unsw_unknown_eval", {}).get("adaptive_unknown_recall_attack_uncertain", 0.0)
    )
    calibrator_unsw_recall = _safe_float(
        scorecard.get("unsw_novelty_calibrator_eval", {}).get("calibrator_unknown_recall", 0.0)
    )
    alert_uncertain = int(runtime.get("decision_counts", {}).get("AttackUncertain", 0)) if runtime else 0

    _save_model_card(
        out_path=cards_dir / "model_01_supervised_multiclass.png",
        model_name="Model 01 - Supervised Multiclass",
        role="Classifies known traffic families (Benign, DDoS, PortScan, etc.).",
        inputs="Engineered flow features from Hawk-Eye schema.",
        output="Known class prediction and class probabilities.",
        key_metric_name="Macro F1 (validation)",
        key_metric_value=f"{macro_f1:.3f}",
    )
    _save_model_card(
        out_path=cards_dir / "model_02_anomaly_detector.png",
        model_name="Model 02 - Anomaly Detector",
        role="Flags behavior that deviates from benign baseline profile.",
        inputs="Same network-flow features transformed for anomaly scoring.",
        output="Anomaly score used by novelty/triage logic.",
        key_metric_name="Attack recall (anomaly eval)",
        key_metric_value=f"{attack_recall:.3f}",
    )
    _save_model_card(
        out_path=cards_dir / "model_03_open_set_gate.png",
        model_name="Model 03 - Open-Set Gate",
        role="Measures distance from known class prototypes for OOD detection.",
        inputs="Feature embedding + prototype references from train classes.",
        output="OOD score contributing to AttackUncertain decision.",
        key_metric_name="UNSW unknown recall (default gate)",
        key_metric_value=f"{default_unsw_recall:.3f}",
    )
    _save_model_card(
        out_path=cards_dir / "model_04_unsw_adaptive_gate.png",
        model_name="Model 04 - UNSW Adaptive Gate",
        role="Applies quantile-based adaptive thresholds to improve external OOD recall.",
        inputs="Known-row quantiles of OOD/SZD/anomaly scores.",
        output="Adaptive AttackUncertain flag for external unknown traffic.",
        key_metric_name="UNSW unknown recall (adaptive)",
        key_metric_value=f"{adaptive_unsw_recall:.3f}",
    )
    _save_model_card(
        out_path=cards_dir / "model_05_novelty_calibrator.png",
        model_name="Model 05 - Novelty Calibrator",
        role="Logistic-regression calibrator over p_attack + OOD + anomaly scores.",
        inputs="Stacked novelty-related scores with alert-budget constraint.",
        output="Calibrated novelty probability and novelty flag.",
        key_metric_name="UNSW unknown recall (calibrator)",
        key_metric_value=f"{calibrator_unsw_recall:.3f}",
    )
    _save_model_card(
        out_path=cards_dir / "model_06_decision_fusion_policy.png",
        model_name="Model 06 - Decision Fusion Policy",
        role="Combines all model signals into final SOC triage label.",
        inputs="Binary attack score, class score, OOD score, anomaly score.",
        output="KnownAttack / AttackUncertain / BenignOrLowRisk.",
        key_metric_name="Runtime AttackUncertain count",
        key_metric_value=str(alert_uncertain),
    )

    return sorted([p.name for p in cards_dir.glob("*.png")])


def _classification_labels(rep: dict, cm_rows: int) -> list[str]:
    labels = [k for k in rep.keys() if k not in ("accuracy", "macro avg", "weighted avg")]
    if len(labels) != cm_rows:
        return [f"C{i}" for i in range(cm_rows)]
    return labels


def _plot_supervised_model_graphs(metrics_rare_boost: dict, out_dir: Path) -> list[str]:
    model_dir = out_dir / "ModelGraphs" / "supervised_multiclass"
    _ensure_dir(model_dir)
    generated: list[str] = []

    rep = metrics_rare_boost.get("classification_report", {})
    cm = np.array(metrics_rare_boost.get("confusion_matrix", []), dtype=float)
    if not rep:
        return generated

    labels = _classification_labels(rep, cm.shape[0] if cm.size else 0)
    rows = []
    for lab in labels:
        r = rep.get(lab, {})
        rows.append(
            {
                "class": lab,
                "precision": _safe_float(r.get("precision", 0.0)),
                "recall": _safe_float(r.get("recall", 0.0)),
                "f1": _safe_float(r.get("f1-score", 0.0)),
                "support": _safe_float(r.get("support", 0.0)),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        long_df = df.melt(id_vars=["class"], value_vars=["precision", "recall", "f1"], var_name="metric", value_name="value")
        plt.figure(figsize=(12, 5))
        sns.barplot(data=long_df, x="class", y="value", hue="metric")
        plt.ylim(0, 1.05)
        plt.title("Supervised Model - Per-Class Metrics")
        plt.xlabel("Class")
        plt.ylabel("Score")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        out = model_dir / "per_class_precision_recall_f1.png"
        plt.savefig(out, dpi=160)
        plt.close()
        generated.append(out.name)

        plt.figure(figsize=(11, 4))
        sns.barplot(data=df, x="class", y="support", color="#4c78a8")
        plt.title("Supervised Model - Class Support Distribution")
        plt.xlabel("Class")
        plt.ylabel("Support")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        out = model_dir / "class_support_distribution.png"
        plt.savefig(out, dpi=160)
        plt.close()
        generated.append(out.name)

    if cm.size:
        row_sums = cm.sum(axis=1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            cm_norm = np.divide(cm, row_sums, where=row_sums > 0)
        cm_norm = np.nan_to_num(cm_norm)
        plt.figure(figsize=(9, 7))
        sns.heatmap(cm_norm, cmap="YlGnBu", vmin=0.0, vmax=1.0)
        plt.title("Supervised Model - Normalized Confusion Matrix")
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.xticks(np.arange(len(labels)) + 0.5, labels, rotation=45, ha="right", fontsize=8)
        plt.yticks(np.arange(len(labels)) + 0.5, labels, rotation=0, fontsize=8)
        plt.tight_layout()
        out = model_dir / "confusion_matrix_normalized.png"
        plt.savefig(out, dpi=160)
        plt.close()
        generated.append(out.name)

    return generated


def _plot_anomaly_model_graphs(metrics_anomaly_val: dict, out_dir: Path) -> list[str]:
    model_dir = out_dir / "ModelGraphs" / "anomaly_detector"
    _ensure_dir(model_dir)
    generated: list[str] = []
    if not metrics_anomaly_val:
        return generated

    p = _safe_float(metrics_anomaly_val.get("precision_attack", 0.0))
    r = _safe_float(metrics_anomaly_val.get("recall_attack", 0.0))
    f1 = _safe_float(metrics_anomaly_val.get("f1_attack", 0.0))
    plt.figure(figsize=(7, 4))
    sns.barplot(x=["Precision", "Recall", "F1"], y=[p, r, f1], palette="magma")
    plt.ylim(0, 1.0)
    plt.title("Anomaly Detector - Attack Metrics")
    plt.ylabel("Score")
    for i, v in enumerate([p, r, f1]):
        plt.text(i, v + 0.02, f"{v:.3f}", ha="center")
    plt.tight_layout()
    out = model_dir / "attack_precision_recall_f1.png"
    plt.savefig(out, dpi=160)
    plt.close()
    generated.append(out.name)

    cm = metrics_anomaly_val.get("confusion_matrix", {})
    vals = [int(cm.get(k, 0)) for k in ("tp", "fp", "tn", "fn")]
    plt.figure(figsize=(7, 4))
    sns.barplot(x=["TP", "FP", "TN", "FN"], y=vals, palette="viridis")
    plt.title("Anomaly Detector - Confusion Counts")
    plt.ylabel("Rows")
    plt.tight_layout()
    out = model_dir / "confusion_counts.png"
    plt.savefig(out, dpi=160)
    plt.close()
    generated.append(out.name)
    return generated


def _plot_open_set_model_graphs(scorecard: dict, out_dir: Path) -> list[str]:
    model_dir = out_dir / "ModelGraphs" / "open_set_and_novelty"
    _ensure_dir(model_dir)
    generated: list[str] = []

    unsw = scorecard.get("unsw_unknown_eval", {})
    calib = scorecard.get("unsw_novelty_calibrator_eval", {})
    if not unsw:
        return generated

    names = ["Default", "Adaptive", "Calibrator"]
    recall_vals = [
        _safe_float(unsw.get("unknown_recall_attack_uncertain", 0.0)),
        _safe_float(unsw.get("adaptive_unknown_recall_attack_uncertain", 0.0)),
        _safe_float(calib.get("calibrator_unknown_recall", 0.0)),
    ]
    alert_vals = [
        _safe_float(unsw.get("attack_uncertain_rate", 0.0)),
        _safe_float(unsw.get("adaptive_attack_uncertain_rate", 0.0)),
        _safe_float(calib.get("calibrator_alert_rate", 0.0)),
    ]

    x = np.arange(len(names))
    width = 0.38
    plt.figure(figsize=(8, 4))
    plt.bar(x - width / 2, recall_vals, width=width, label="Unknown Recall")
    plt.bar(x + width / 2, alert_vals, width=width, label="Alert Rate")
    plt.xticks(x, names)
    plt.ylim(0, 1.0)
    plt.title("Open-Set / Novelty - Recall vs Alert Rate")
    plt.ylabel("Score")
    plt.legend()
    plt.tight_layout()
    out = model_dir / "unsw_recall_vs_alert_rate.png"
    plt.savefig(out, dpi=160)
    plt.close()
    generated.append(out.name)

    thr = unsw.get("adaptive_thresholds", {})
    if thr:
        t_names = list(thr.keys())
        t_vals = [float(v) for v in thr.values()]
        plt.figure(figsize=(8, 4))
        sns.barplot(x=t_names, y=t_vals, palette="cubehelix")
        plt.title("Adaptive Gate Thresholds (UNSW)")
        plt.ylabel("Threshold Value")
        plt.xticks(rotation=20, ha="right")
        plt.tight_layout()
        out = model_dir / "adaptive_threshold_values.png"
        plt.savefig(out, dpi=160)
        plt.close()
        generated.append(out.name)

    return generated


def _plot_decision_fusion_graphs(runtime: dict, out_dir: Path) -> list[str]:
    model_dir = out_dir / "ModelGraphs" / "decision_fusion"
    _ensure_dir(model_dir)
    generated: list[str] = []
    counts = runtime.get("decision_counts", {}) if runtime else {}
    if not counts:
        return generated
    labels = list(counts.keys())
    vals = [int(counts[k]) for k in labels]

    plt.figure(figsize=(8, 4))
    sns.barplot(x=labels, y=vals, palette="Set2")
    plt.title("Decision Fusion - Output Label Counts")
    plt.xlabel("Decision Label")
    plt.ylabel("Rows")
    plt.xticks(rotation=12)
    plt.tight_layout()
    out = model_dir / "decision_label_counts.png"
    plt.savefig(out, dpi=160)
    plt.close()
    generated.append(out.name)

    total = max(sum(vals), 1)
    pct = [100.0 * v / total for v in vals]
    plt.figure(figsize=(7, 4))
    sns.barplot(x=labels, y=pct, palette="Set3")
    plt.title("Decision Fusion - Output Label Percentages")
    plt.ylabel("Percent (%)")
    plt.xticks(rotation=12)
    for i, v in enumerate(pct):
        plt.text(i, v + 0.5, f"{v:.2f}%", ha="center")
    plt.tight_layout()
    out = model_dir / "decision_label_percentages.png"
    plt.savefig(out, dpi=160)
    plt.close()
    generated.append(out.name)
    return generated


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate result charts from Hawk-Eye reports.")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--runtime-summary", default=None, help="Optional runtime lab run_summary.json path.")
    ap.add_argument("--output-dir", default="reports/figures")
    args = ap.parse_args()

    reports = Path(args.reports_dir)
    out_dir = Path(args.output_dir)
    _ensure_dir(out_dir)

    scorecard = _read_json(reports / "final_rare_scorecard.json")
    metrics_rare_boost = _read_json(reports / "metrics_rare_boost.json")
    metrics_anomaly_val = _read_json(reports / "metrics_anomaly_val.json")
    runtime = _read_json(Path(args.runtime_summary)) if args.runtime_summary else {}

    _plot_macro_f1(scorecard, out_dir / "macro_f1_before_after.png")
    _plot_rare_classes_f1(metrics_rare_boost, out_dir / "rare_class_f1_boosted.png")
    _plot_confusion_heatmap(metrics_rare_boost, out_dir / "confusion_matrix_rare_boost.png")
    _plot_holdout_unknown_recall(scorecard, out_dir / "holdout_unknown_recall.png")
    _plot_unsw_unknown(scorecard, out_dir / "unsw_unknown_recall_comparison.png")
    if runtime:
        _plot_decision_counts(runtime, out_dir / "runtime_decision_counts.png")
    model_card_files = _generate_model_cards(
        out_dir=out_dir,
        scorecard=scorecard,
        metrics_rare_boost=metrics_rare_boost,
        metrics_anomaly_val=metrics_anomaly_val,
        runtime=runtime,
    )
    model_graphs = {
        "supervised_multiclass": _plot_supervised_model_graphs(metrics_rare_boost, out_dir),
        "anomaly_detector": _plot_anomaly_model_graphs(metrics_anomaly_val, out_dir),
        "open_set_and_novelty": _plot_open_set_model_graphs(scorecard, out_dir),
        "decision_fusion": _plot_decision_fusion_graphs(runtime, out_dir),
    }

    manifest = {
        "output_dir": str(out_dir.resolve()),
        "generated": sorted([p.name for p in out_dir.glob("*.png")]),
        "model_cards_dir": str((out_dir / "ModelCards").resolve()),
        "model_cards": model_card_files,
        "model_graphs_dir": str((out_dir / "ModelGraphs").resolve()),
        "model_graphs": model_graphs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
