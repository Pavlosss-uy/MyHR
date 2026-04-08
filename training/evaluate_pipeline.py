"""
Phase 4.6 - End-to-End Evaluation Pipeline
Loads all trained checkpoints, evaluates each on a held-out test split,
and produces:
  training/results/model_evaluation_report.json
  training/results/score_distributions.png
  training/results/difficulty_comparison.png
  training/results/ranking_ndcg.png
"""

import os
import sys
import json
import random
import math

import torch
import torch.nn.functional as F
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend (safe on Windows/server)
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, pearsonr
from torch.utils.data import DataLoader, Subset

# --- Path setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.registry import ModelRegistry
from models.multi_head_evaluator import MultiHeadEvaluator
from models.performance_predictor import PerformancePredictor
from models.candidate_ranker import NeuralCandidateRanker

RESULTS_DIR = os.path.join(project_root, "training", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def seed_everything(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def dcg_at_k(scores, k):
    """Discounted Cumulative Gain at k."""
    scores = scores[:k]
    return sum(s / math.log2(i + 2) for i, s in enumerate(scores))


def ndcg_at_k(ranked_scores, ideal_scores, k):
    ideal = sorted(ideal_scores, reverse=True)
    dcg   = dcg_at_k(ranked_scores, k)
    idcg  = dcg_at_k(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def regression_metrics(true_vals, pred_vals):
    true_arr = np.array(true_vals)
    pred_arr = np.array(pred_vals)
    mae  = float(np.mean(np.abs(true_arr - pred_arr)))
    rmse = float(np.sqrt(np.mean((true_arr - pred_arr) ** 2)))
    spr, _ = spearmanr(true_arr, pred_arr)
    prs, _ = pearsonr(true_arr, pred_arr)
    return {"mae": mae, "rmse": rmse, "spearman": float(spr), "pearson": float(prs)}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Skill Matcher Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_skill_matcher(registry):
    print("\n[1/5] Evaluating Skill Matcher ...")
    model = registry.load_skill_matcher()

    with open(os.path.join(project_root, "data", "skill_pairs.json"), encoding="utf-8") as f:
        pairs = json.load(f)

    # 20% held-out (last 100 of 500)
    random.shuffle(pairs)
    test_pairs = pairs[:100]

    match_sims, mismatch_sims = [], []
    correct = 0

    for pair in test_pairs:
        cv  = pair["cv_skills"]
        jd  = pair["jd_requirements"]
        lbl = int(pair["is_match"])

        # positive similarity
        pos_sim = model.calculate_match_score(cv, jd)

        # create a negative by shuffling jd with a random other pair
        neg_pair = random.choice(test_pairs)
        neg_jd   = neg_pair["jd_requirements"]
        neg_sim  = model.calculate_match_score(cv, neg_jd)

        if lbl == 1:
            match_sims.append(pos_sim)
        else:
            mismatch_sims.append(pos_sim)

        # pairwise: correct if match > mismatch
        if pos_sim > neg_sim:
            correct += 1

    pairwise_acc = correct / len(test_pairs)
    mean_match    = float(np.mean(match_sims))    if match_sims    else 0.0
    mean_mismatch = float(np.mean(mismatch_sims)) if mismatch_sims else 0.0

    print(f"  Pairwise accuracy : {pairwise_acc:.3f}")
    print(f"  Mean match sim    : {mean_match:.3f}")
    print(f"  Mean mismatch sim : {mean_mismatch:.3f}")

    return {
        "pairwise_accuracy": round(pairwise_acc, 4),
        "match_mean":        round(mean_match, 4),
        "mismatch_mean":     round(mean_mismatch, 4),
        "n_test":            len(test_pairs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Multi-Head Evaluator Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_evaluator(registry):
    print("\n[2/5] Evaluating Multi-Head Evaluator ...")
    model = registry.load_evaluator()
    device = registry.device

    with open(os.path.join(project_root, "data", "eval_training_data.json"), encoding="utf-8") as f:
        data = json.load(f)

    samples = data["samples"]
    random.shuffle(samples)
    test_samples = samples[:34]  # ~20% of 171

    true_rel, true_cla, true_dep = [], [], []
    pred_rel, pred_cla, pred_dep = [], [], []
    tier_scores = {"excellent": [], "good": [], "mediocre": [], "poor": []}

    model.eval()
    with torch.no_grad():
        for s in test_samples:
            feats = torch.tensor(s["features"], dtype=torch.float32).unsqueeze(0).to(device)
            r, c, d = model(feats)

            pred_rel.append(r.item())
            pred_cla.append(c.item())
            pred_dep.append(d.item())

            true_rel.append(float(s["relevance"]))
            true_cla.append(float(s["clarity"]))
            true_dep.append(float(s["technical_depth"]))

            tier = s.get("quality_tier", "good")
            overall = (r.item() + c.item() + d.item()) / 3.0
            tier_scores[tier].append(overall)

    spr_rel, _ = spearmanr(true_rel, pred_rel)
    spr_cla, _ = spearmanr(true_cla, pred_cla)
    spr_dep, _ = spearmanr(true_dep, pred_dep)

    print(f"  Spearman relevance      : {spr_rel:.3f}")
    print(f"  Spearman clarity        : {spr_cla:.3f}")
    print(f"  Spearman technical_depth: {spr_dep:.3f}")

    # Collect all tier scores across ALL 171 samples for the distribution plot
    all_tier_scores = {"excellent": [], "good": [], "mediocre": [], "poor": []}
    with torch.no_grad():
        for s in samples:
            feats = torch.tensor(s["features"], dtype=torch.float32).unsqueeze(0).to(device)
            r, c, d = model(feats)
            overall = (r.item() + c.item() + d.item()) / 3.0
            tier = s.get("quality_tier", "good")
            all_tier_scores[tier].append(overall)

    return {
        "spearman_relevance": round(float(spr_rel), 4),
        "spearman_clarity":   round(float(spr_cla), 4),
        "spearman_depth":     round(float(spr_dep), 4),
        "n_test":             len(test_samples),
    }, all_tier_scores


# ─────────────────────────────────────────────────────────────────────────────
# 3. Candidate Ranker Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_ranker(registry):
    print("\n[3/5] Evaluating Candidate Ranker ...")
    model = registry.load_candidate_ranker()
    device = registry.device

    with open(os.path.join(project_root, "data", "ranking_pairs.json"), encoding="utf-8") as f:
        triplets = json.load(f)

    random.shuffle(triplets)
    test_triplets = triplets[:502]  # 20%

    correct = 0
    ndcg_scores = []

    model.eval()
    with torch.no_grad():
        for t in test_triplets:
            anc = torch.tensor(t["anchor"],   dtype=torch.float32).unsqueeze(0).to(device)
            pos = torch.tensor(t["positive"], dtype=torch.float32).unsqueeze(0).to(device)
            neg = torch.tensor(t["negative"], dtype=torch.float32).unsqueeze(0).to(device)

            anc_emb = model(anc)
            pos_emb = model(pos)
            neg_emb = model(neg)

            sim_pos = F.cosine_similarity(anc_emb, pos_emb).item()
            sim_neg = F.cosine_similarity(anc_emb, neg_emb).item()

            if sim_pos > sim_neg:
                correct += 1

            # NDCG@2: rank [pos, neg] by similarity
            ranked = sorted([sim_pos, sim_neg], reverse=True)
            ideal  = [1.0, 0.0]   # binary relevance
            ranked_bin = [1.0 if s == sim_pos else 0.0 for s in ranked]
            ndcg_scores.append(ndcg_at_k(ranked_bin, ideal, k=2))

    pairwise_acc = correct / len(test_triplets)
    mean_ndcg    = float(np.mean(ndcg_scores))

    print(f"  Pairwise accuracy : {pairwise_acc:.3f}")
    print(f"  NDCG@2            : {mean_ndcg:.3f}")

    return {
        "ndcg_at_2":         round(mean_ndcg, 4),
        "pairwise_accuracy": round(pairwise_acc, 4),
        "n_test":            len(test_triplets),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Performance Predictor Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_predictor(registry):
    print("\n[4/5] Evaluating Performance Predictor ...")
    model = registry.load_performance_predictor()
    device = registry.device

    with open(os.path.join(project_root, "data", "performance_data.json"), encoding="utf-8") as f:
        data = json.load(f)

    samples = data["samples"]
    random.shuffle(samples)
    test_samples = samples[:5000]  # held-out test set

    true_vals, pred_vals = [], []

    model.eval()
    with torch.no_grad():
        batch_size = 256
        for i in range(0, len(test_samples), batch_size):
            batch = test_samples[i:i + batch_size]
            feats  = torch.tensor([s["features"] for s in batch], dtype=torch.float32).to(device)
            labels = [s["label"] for s in batch]
            preds  = model(feats).squeeze(-1).cpu().tolist()
            true_vals.extend(labels)
            pred_vals.extend(preds if isinstance(preds, list) else [preds])

    metrics = regression_metrics(true_vals, pred_vals)
    print(f"  MAE      : {metrics['mae']:.4f}")
    print(f"  RMSE     : {metrics['rmse']:.4f}")
    print(f"  Spearman : {metrics['spearman']:.4f}")
    print(f"  Pearson  : {metrics['pearson']:.4f}")

    return {
        "mae":      round(metrics["mae"], 4),
        "rmse":     round(metrics["rmse"], 4),
        "spearman": round(metrics["spearman"], 4),
        "pearson":  round(metrics["pearson"], 4),
        "n_test":   len(test_samples),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Difficulty Engine Evaluation (read from comparison JSON)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_difficulty():
    print("\n[5/5] Loading Difficulty Engine comparison ...")
    cmp_path = os.path.join(RESULTS_DIR, "difficulty_comparison.json")
    if not os.path.exists(cmp_path):
        print("  WARNING: difficulty_comparison.json not found, skipping.")
        return {}

    with open(cmp_path, encoding="utf-8") as f:
        cmp = json.load(f)

    result = {}
    for method, stats in cmp.items():
        pct = stats.get("pct_in_target_zone", 0)
        result[method] = round(float(pct), 1)
        print(f"  {method:20s}: {pct:.1f}% in zone")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Plot 1 — Evaluator Score Distributions by Tier
# ─────────────────────────────────────────────────────────────────────────────

def plot_score_distributions(tier_scores):
    tiers  = ["poor", "mediocre", "good", "excellent"]
    colors = ["#e74c3c", "#e67e22", "#3498db", "#2ecc71"]

    fig, ax = plt.subplots(figsize=(9, 5))

    for tier, color in zip(tiers, colors):
        scores = tier_scores.get(tier, [])
        if scores:
            ax.hist(scores, bins=12, alpha=0.7, label=tier.capitalize(),
                    color=color, edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Overall Score (0-100)", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Evaluator Score Distributions by Quality Tier", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xlim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(RESULTS_DIR, "score_distributions.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [SAVED] {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Plot 2 — Difficulty Method Comparison Bar Chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_difficulty_comparison(difficulty_metrics):
    if not difficulty_metrics:
        return

    labels = list(difficulty_metrics.keys())
    values = [difficulty_metrics[k] for k in labels]

    display_labels = {
        "heuristic":     "Heuristic",
        "reinforce":     "REINFORCE 6-D",
        "reinforce_6d":  "REINFORCE 6-D",
        "ppo":           "PPO",
    }
    bar_labels = [display_labels.get(k, k) for k in labels]
    colors = ["#95a5a6", "#3498db", "#2ecc71", "#e67e22"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(bar_labels, values, color=colors[:len(values)], edgecolor="white",
                  linewidth=0.8, width=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylabel("% Scores in Target Zone (50-80)", fontsize=11)
    ax.set_title("Difficulty Engine: Method Comparison", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.axhline(65.0, color="#e74c3c", linestyle="--", linewidth=1.2, label="Target (65%)")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(RESULTS_DIR, "difficulty_comparison.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [SAVED] {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Plot 3 — Ranker NDCG@k Curve
# ─────────────────────────────────────────────────────────────────────────────

def plot_ranking_ndcg(registry):
    print("  Computing NDCG@k curve ...")
    model = registry.load_candidate_ranker()
    device = registry.device

    with open(os.path.join(project_root, "data", "ranking_pairs.json"), encoding="utf-8") as f:
        triplets = json.load(f)

    random.shuffle(triplets)
    test_triplets = triplets[:502]

    # Gather similarities for all triplets
    sim_pairs = []
    model.eval()
    with torch.no_grad():
        for t in test_triplets:
            anc = torch.tensor(t["anchor"],   dtype=torch.float32).unsqueeze(0).to(device)
            pos = torch.tensor(t["positive"], dtype=torch.float32).unsqueeze(0).to(device)
            neg = torch.tensor(t["negative"], dtype=torch.float32).unsqueeze(0).to(device)
            anc_e = model(anc)
            pos_e = model(pos)
            neg_e = model(neg)
            sim_pairs.append((
                F.cosine_similarity(anc_e, pos_e).item(),
                F.cosine_similarity(anc_e, neg_e).item(),
            ))

    ks = [1, 2, 3, 5]
    ndcg_at = []
    for k in ks:
        scores = []
        for sim_pos, sim_neg in sim_pairs:
            ranked_bin = [1.0, 0.0] if sim_pos >= sim_neg else [0.0, 1.0]
            ideal      = [1.0, 0.0]
            scores.append(ndcg_at_k(ranked_bin, ideal, k=k))
        ndcg_at.append(float(np.mean(scores)))

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(ks, ndcg_at, marker="o", color="#3498db", linewidth=2, markersize=7)
    for k, v in zip(ks, ndcg_at):
        ax.annotate(f"{v:.3f}", (k, v), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9)

    ax.set_xlabel("k", fontsize=11)
    ax.set_ylabel("NDCG@k", fontsize=11)
    ax.set_title("Candidate Ranker: NDCG@k Curve", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.1)
    ax.set_xticks(ks)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = os.path.join(RESULTS_DIR, "ranking_ndcg.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [SAVED] {path}")

    return {k: round(v, 4) for k, v in zip(ks, ndcg_at)}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    seed_everything(42)
    print("=" * 60)
    print("  MyHR - End-to-End Model Evaluation Pipeline")
    print("=" * 60)

    registry = ModelRegistry()

    # ── Evaluations ──────────────────────────────────────────────
    skill_metrics           = evaluate_skill_matcher(registry)
    evaluator_metrics, tier_scores = evaluate_evaluator(registry)
    ranker_metrics          = evaluate_ranker(registry)
    predictor_metrics       = evaluate_predictor(registry)
    difficulty_pct          = evaluate_difficulty()

    # ── Plots ─────────────────────────────────────────────────────
    print("\n[Plots] Generating visualisations ...")
    plot_score_distributions(tier_scores)
    plot_difficulty_comparison(difficulty_pct)
    ndcg_curve = plot_ranking_ndcg(registry)

    # ── Unified Report ────────────────────────────────────────────
    report = {
        "skill_matcher": skill_metrics,
        "evaluator":     evaluator_metrics,
        "ranker":        {**ranker_metrics, "ndcg_curve": ndcg_curve},
        "predictor":     predictor_metrics,
        "difficulty":    difficulty_pct,
    }

    report_path = os.path.join(RESULTS_DIR, "model_evaluation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[SAVED] {report_path}")
    print("\n" + "=" * 60)
    print("  EVALUATION COMPLETE")
    print("=" * 60)
    print("\nSummary:")
    print(f"  Skill Matcher   pairwise acc : {skill_metrics['pairwise_accuracy']:.3f}")
    print(f"  Evaluator       Spearman avg : {(evaluator_metrics['spearman_relevance'] + evaluator_metrics['spearman_clarity'] + evaluator_metrics['spearman_depth']) / 3:.3f}")
    print(f"  Ranker          NDCG@2       : {ranker_metrics['ndcg_at_2']:.3f}")
    print(f"  Predictor       Spearman     : {predictor_metrics['spearman']:.3f}")
    if difficulty_pct:
        best_method = max(difficulty_pct, key=difficulty_pct.get)
        print(f"  Difficulty      best method  : {best_method} ({difficulty_pct[best_method]:.1f}% in zone)")
    print()


if __name__ == "__main__":
    main()
