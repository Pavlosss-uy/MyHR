"""
Shared evaluation metrics utilities for all MyHR training scripts.
"""

import numpy as np
from datetime import datetime
from torch.utils.tensorboard import SummaryWriter
from sklearn.metrics import (
    classification_report, confusion_matrix,
    f1_score, accuracy_score
)
from scipy.stats import spearmanr, pearsonr


# ---------------------------------------------------------------------------
# Classification metrics (emotion model)
# ---------------------------------------------------------------------------

def classification_metrics(y_true, y_pred, label_names=None):
    """
    Compute per-class and aggregate classification metrics.

    Returns a dict with:
        weighted_f1, macro_f1, accuracy,
        per_class_f1 (dict label→f1),
        confusion_matrix (2-D list)
    """
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    macro_f1    = f1_score(y_true, y_pred, average="macro",    zero_division=0)
    acc         = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=range(len(label_names)) if label_names else None).tolist()

    per_class_f1 = {}
    if label_names:
        f1s = f1_score(y_true, y_pred, average=None, zero_division=0, labels=range(len(label_names)))
        for name, score in zip(label_names, f1s):
            per_class_f1[name] = float(score)

    report_str = classification_report(
        y_true, y_pred,
        labels=range(len(label_names)) if label_names else None,
        target_names=label_names,
        zero_division=0
    )

    return {
        "weighted_f1":    float(weighted_f1),
        "macro_f1":       float(macro_f1),
        "accuracy":       float(acc),
        "per_class_f1":   per_class_f1,
        "confusion_matrix": cm,
        "report_str":     report_str,
    }


# ---------------------------------------------------------------------------
# Regression metrics (scorer, predictor, evaluator)
# ---------------------------------------------------------------------------

def regression_metrics(y_true, y_pred):
    """
    Compute regression quality metrics.

    Returns a dict with: mae, rmse, pearson_r, spearman_rho
    """
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)

    mae  = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    if len(y_true) >= 2 and np.std(y_true) > 1e-9 and np.std(y_pred) > 1e-9:
        pearson_r,  _ = pearsonr(y_true, y_pred)
        spearman_rho, _ = spearmanr(y_true, y_pred)
    else:
        pearson_r = spearman_rho = 0.0

    return {
        "mae":          mae,
        "rmse":         rmse,
        "pearson_r":    float(pearson_r),
        "spearman_rho": float(spearman_rho),
    }


# ---------------------------------------------------------------------------
# Ranking metrics (candidate ranker)
# ---------------------------------------------------------------------------

def _dcg_at_k(relevances, k):
    relevances = np.array(relevances[:k], dtype=float)
    if len(relevances) == 0:
        return 0.0
    gains = relevances / np.log2(np.arange(2, len(relevances) + 2))
    return float(gains.sum())


def ranking_metrics(similarity_scores_list, binary_labels_list, k=5):
    """
    Compute ranking quality metrics over a list of (scores, labels) pairs.

    Each element of similarity_scores_list is a 1-D array of predicted
    similarity scores; the matching element of binary_labels_list is a
    1-D array of ground-truth binary relevance (1 = hired / relevant,
    0 = rejected / irrelevant).

    Returns a dict with: ndcg_at_k, pairwise_accuracy
    """
    ndcg_scores = []
    pairwise_correct = 0
    pairwise_total   = 0

    for scores, labels in zip(similarity_scores_list, binary_labels_list):
        scores = np.array(scores, dtype=float)
        labels = np.array(labels, dtype=float)

        # NDCG@k
        sorted_labels = labels[np.argsort(-scores)]
        ideal_labels  = np.sort(labels)[::-1]
        dcg   = _dcg_at_k(sorted_labels, k)
        idcg  = _dcg_at_k(ideal_labels,  k)
        ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)

        # Pairwise accuracy: for every (i, j) pair where label[i] > label[j],
        # check that score[i] > score[j]
        for i in range(len(labels)):
            for j in range(len(labels)):
                if labels[i] > labels[j]:
                    pairwise_total += 1
                    if scores[i] > scores[j]:
                        pairwise_correct += 1

    ndcg   = float(np.mean(ndcg_scores)) if ndcg_scores else 0.0
    pairwise_acc = (pairwise_correct / pairwise_total
                    if pairwise_total > 0 else 0.0)

    return {
        "ndcg_at_k":       ndcg,
        "pairwise_accuracy": float(pairwise_acc),
    }


# ---------------------------------------------------------------------------
# RL metrics (difficulty engine)
# ---------------------------------------------------------------------------

def rl_metrics(rewards_per_episode, scores_per_episode,
               target_low=50.0, target_high=80.0):
    """
    Compute RL training quality metrics.

    Args:
        rewards_per_episode: list of per-step reward lists
        scores_per_episode:  list of per-step score lists
        target_low/high:     bounds of the "good zone" for candidate scores

    Returns a dict with: avg_reward, score_variance, pct_in_target_zone
    """
    all_rewards = [r for ep in rewards_per_episode for r in ep]
    all_scores  = [s for ep in scores_per_episode  for s in ep]

    avg_reward = float(np.mean(all_rewards)) if all_rewards else 0.0
    score_var  = float(np.var(all_scores))   if all_scores  else 0.0
    pct_zone   = (float(np.mean([target_low <= s <= target_high
                                 for s in all_scores])) * 100
                  if all_scores else 0.0)

    return {
        "avg_reward":         avg_reward,
        "score_variance":     score_var,
        "pct_in_target_zone": pct_zone,
    }


# ---------------------------------------------------------------------------
# TensorBoard writer factory
# ---------------------------------------------------------------------------

def make_writer(model_name: str) -> SummaryWriter:
    """Return a SummaryWriter that logs to training/runs/<model_name>_<timestamp>."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = f"training/runs/{model_name}_{timestamp}"
    return SummaryWriter(log_dir=log_dir)
