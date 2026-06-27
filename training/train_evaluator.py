"""
Multi-Head Evaluator Training Script
======================================
Trains the MultiHeadEvaluator model on LLM-labeled data.

Pipeline:
1. Load labeled data from data/eval_training_data.json
2. Train/val split (80/20)
3. Multi-task weighted loss training
4. Evaluate with Spearman rank correlation per head
5. Save best model to models/checkpoints/evaluator_v1.pt

Usage:
    python training/train_evaluator.py
    
Prerequisites:
    python training/generate_eval_data.py  (generates training data first)
"""

import hashlib
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import numpy as np
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import TensorDataset, DataLoader, WeightedRandomSampler
from scipy.stats import spearmanr
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from models.multi_head_evaluator import MultiHeadEvaluator
from training.metrics import make_writer
from utils.seeding import set_all_seeds
from utils.trainer_logger import ExperimentLogger


# ??? Configuration ???????????????????????????????????????????????????????????

DATA_FILE = os.path.join(PROJECT_ROOT, "data", "eval_training_data.json")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "checkpoints", "evaluator_v1.pt")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "embed_cache")

# Training hyperparameters
EPOCHS = 100
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 0.01
T_MAX = 50  # CosineAnnealing period
EARLY_STOP_PATIENCE = 10
# 70/15/15 split — held-out test set is excluded from training and early-stop selection
TRAIN_SPLIT = 0.70
VAL_SPLIT   = 0.15

# Loss weights (must sum to 1.0)
LOSS_WEIGHTS = {
    "relevance": 0.35,
    "clarity": 0.30,
    "depth": 0.35,
}

# Random seed for reproducibility
SEED = 42


# ??? Embedding Cache ?????????????????????????????????????????????????????????

def _cached_encode(embedder, texts: list, tag: str) -> np.ndarray:
    """Encode texts with SentenceTransformer, using a file cache keyed by content hash."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5("\n".join(texts).encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{tag}_{h}.npy")
    if os.path.exists(cache_path):
        print(f"   [CACHE HIT] {tag} — loading from {os.path.basename(cache_path)}")
        return np.load(cache_path)
    embs = embedder.encode(
        texts, convert_to_numpy=True, batch_size=32, show_progress_bar=True
    ).astype(np.float32)
    np.save(cache_path, embs)
    return embs


# ??? Data Loading ????????????????????????????????????????????????????????????

def load_data(data_path: str) -> tuple:
    """
    Load labeled training data.
    
    Returns:
        features: np.array (N, 768)
        labels: dict of np.arrays, each (N,) ? 'relevance', 'clarity', 'depth'
    """
    print(f"? Loading data from {data_path}...")

    with open(data_path, "r") as f:
        dataset = json.load(f)

    samples = dataset["samples"]
    metadata = dataset["metadata"]

    print(f"   Total samples: {metadata['total_samples']}")
    print(f"   Feature dim: {metadata['feature_dim']}")
    print(f"   Quality distribution: {metadata['quality_distribution']}")

    # --- CRITICAL FIX: align training features with INFERENCE ---
    # The stored s["features"] were built with all-MiniLM-L6-v2 as concat(Q, A)
    # (see generate_eval_data.py), but the live evaluator is fed
    # all-mpnet-base-v2(answer) only (agent.py / feature_extractor.py). Same 768
    # dims, but a totally different vector space + content → the deployed model
    # scored noise. We re-encode the ANSWER with the exact inference embedder so
    # training == inference.
    from sentence_transformers import SentenceTransformer
    print("   Re-encoding answers with all-mpnet-base-v2 (matches inference)...")
    _embedder = SentenceTransformer("all-mpnet-base-v2")
    answers = [s.get("answer", "") for s in samples]
    features = _cached_encode(_embedder, answers, "evaluator_answers")

    labels = {
        "relevance": np.array([s["relevance"] for s in samples], dtype=np.float32),
        "clarity": np.array([s["clarity"] for s in samples], dtype=np.float32),
        "depth": np.array([s["technical_depth"] for s in samples], dtype=np.float32),
    }
    quality_tiers = [s.get("quality_tier", "excellent") for s in samples]

    print(f"   Features shape: {features.shape}")
    print(f"   Label ranges: relevance=[{labels['relevance'].min():.0f}, {labels['relevance'].max():.0f}], "
          f"clarity=[{labels['clarity'].min():.0f}, {labels['clarity'].max():.0f}], "
          f"depth=[{labels['depth'].min():.0f}, {labels['depth'].max():.0f}]")

    from collections import Counter
    tier_counts = Counter(quality_tiers)
    print(f"   Quality distribution: {dict(tier_counts)}")

    return features, labels, quality_tiers


def prepare_dataloaders(features, labels, quality_tiers, train_split=TRAIN_SPLIT, val_split=VAL_SPLIT, seed=SEED):
    """Split data into train/val/test (70/15/15) and create DataLoaders.

    Uses WeightedRandomSampler on the training split so each quality tier
    is sampled at equal frequency regardless of raw class counts.  This
    directly addresses the 325 excellent / 10 poor imbalance in existing data.
    The test split is returned separately and excluded from all training decisions.
    """
    np.random.seed(seed)
    n = len(features)
    indices = np.random.permutation(n)
    train_end = int(n * train_split)
    val_end   = int(n * (train_split + val_split))

    train_idx = indices[:train_end]
    val_idx   = indices[train_end:val_end]
    test_idx  = indices[val_end:]

    print(f"\nTrain/Val/Test split: {len(train_idx)}/{len(val_idx)}/{len(test_idx)}")

    # --- Build WeightedRandomSampler for training split ---
    from collections import Counter
    train_tiers = [quality_tiers[i] for i in train_idx]
    tier_counts = Counter(train_tiers)
    tier_weight = {tier: 1.0 / count for tier, count in tier_counts.items()}
    sample_weights = torch.tensor(
        [tier_weight[t] for t in train_tiers], dtype=torch.float32
    )
    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_idx),
        replacement=True,
    )
    print(f"   WeightedRandomSampler tier weights: "
          + ", ".join(f"{t}={w:.4f}" for t, w in sorted(tier_weight.items())))

    def make_tensor_ds(idx):
        X     = torch.tensor(features[idx])
        y_rel = torch.tensor(labels["relevance"][idx])
        y_cla = torch.tensor(labels["clarity"][idx])
        y_dep = torch.tensor(labels["depth"][idx])
        return TensorDataset(X, y_rel, y_cla, y_dep)

    train_ds = make_tensor_ds(train_idx)
    val_ds   = make_tensor_ds(val_idx)
    test_ds  = make_tensor_ds(test_idx)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, sampler=sampler)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False)

    return train_loader, val_loader, test_loader, train_idx, val_idx, test_idx


# ??? Training ????????????????????????????????????????????????????????????????

def _unpack_preds(preds):
    """Model returns either a dict or a (rel, cla, dep) tuple."""
    if isinstance(preds, dict):
        return preds["relevance"], preds["clarity"], preds["depth"]
    return preds[0], preds[1], preds[2]


def compute_loss(preds, y_rel, y_cla, y_dep) -> torch.Tensor:
    """Multi-task weighted loss."""
    rel, cla, dep = _unpack_preds(preds)
    loss = (
        LOSS_WEIGHTS["relevance"] * F.mse_loss(rel.view(-1), y_rel)
        + LOSS_WEIGHTS["clarity"] * F.mse_loss(cla.view(-1), y_cla)
        + LOSS_WEIGHTS["depth"] * F.mse_loss(dep.view(-1), y_dep)
    )
    return loss


def evaluate(model, data_loader) -> dict:
    """
    Evaluate model on a dataset.
    
    Returns:
        dict with loss, per-head MSE and Spearman correlation.
    """
    model.eval()
    all_preds = {"relevance": [], "clarity": [], "depth": []}
    all_labels = {"relevance": [], "clarity": [], "depth": []}
    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for X, y_rel, y_cla, y_dep in data_loader:
            preds = model(X)
            loss = compute_loss(preds, y_rel, y_cla, y_dep)
            total_loss += loss.item()
            n_batches += 1

            rel, cla, dep = _unpack_preds(preds)
            for key, pred_t, y in zip(
                ["relevance", "clarity", "depth"],
                [rel, cla, dep],
                [y_rel, y_cla, y_dep]
            ):
                all_preds[key].extend(pred_t.view(-1).tolist())
                all_labels[key].extend(y.tolist())

    results = {"loss": total_loss / max(n_batches, 1)}

    for key in ["relevance", "clarity", "depth"]:
        preds_arr = np.array(all_preds[key])
        labels_arr = np.array(all_labels[key])

        results[f"{key}_mse"] = float(np.mean((preds_arr - labels_arr) ** 2))

        # Spearman rank correlation
        if len(set(labels_arr)) > 1:  # Need variance for correlation
            rho, p_value = spearmanr(preds_arr, labels_arr)
            results[f"{key}_spearman"] = float(rho)
            results[f"{key}_spearman_p"] = float(p_value)
        else:
            results[f"{key}_spearman"] = 0.0
            results[f"{key}_spearman_p"] = 1.0

    return results


def train(model, train_loader, val_loader):
    """Full training loop with early stopping."""
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=T_MAX)
    writer = make_writer("multi_head_evaluator")
    logger = ExperimentLogger("multi_head_evaluator", params={"lr": LEARNING_RATE, "epochs": EPOCHS, "batch": BATCH_SIZE})

    best_val_loss = float("inf")
    best_epoch = 0
    patience_counter = 0
    best_state = None

    print(f"\n? Training Multi-Head Evaluator")
    print(f"   Epochs: {EPOCHS} | Batch: {BATCH_SIZE} | LR: {LEARNING_RATE}")
    print(f"   Loss weights: {LOSS_WEIGHTS}")
    print(f"   Early stopping patience: {EARLY_STOP_PATIENCE}")
    print("=" * 80)

    for epoch in range(1, EPOCHS + 1):
        # ?? Train ??
        model.train()
        train_loss = 0.0
        n_batches = 0

        for X, y_rel, y_cla, y_dep in train_loader:
            optimizer.zero_grad()
            preds = model(X)
            loss = compute_loss(preds, y_rel, y_cla, y_dep)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            n_batches += 1

        train_loss /= max(n_batches, 1)
        scheduler.step()

        # ?? Validate ??
        val_results = evaluate(model, val_loader)
        val_loss = val_results["loss"]

        # ?? TensorBoard + MLflow ??
        writer.add_scalar("Loss/train", train_loss, epoch)
        writer.add_scalar("Loss/val", val_loss, epoch)
        writer.add_scalar("LR", optimizer.param_groups[0]["lr"], epoch)
        logger.log_metric("loss/train", train_loss, step=epoch)
        logger.log_metric("loss/val",   val_loss,   step=epoch)
        for key in ["relevance", "clarity", "depth"]:
            writer.add_scalar(f"Metric/{key}_spearman", val_results[f"{key}_spearman"], epoch)
            writer.add_scalar(f"Metric/{key}_mse",      val_results[f"{key}_mse"],      epoch)
            logger.log_metric(f"{key}_spearman", val_results[f"{key}_spearman"], step=epoch)

        # ?? Logging ??
        if epoch % 5 == 0 or epoch == 1:
            spearman_str = " | ".join(
                f"{k[:3]}={val_results[f'{k}_spearman']:.3f}"
                for k in ["relevance", "clarity", "depth"]
            )
            print(
                f"  Epoch {epoch:3d}/{EPOCHS} | "
                f"Train Loss: {train_loss:.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Spearman: {spearman_str}"
            )

        # ?? Early Stopping ??
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= EARLY_STOP_PATIENCE:
                print(f"\n  ??  Early stopping at epoch {epoch} (best: {best_epoch})")
                break

    # Restore best model and close writer
    if best_state is not None:
        model.load_state_dict(best_state)
    writer.close()
    logger.finish()

    print(f"\n  ? Best model from epoch {best_epoch} (val_loss={best_val_loss:.4f})")
    return model, best_epoch


# ??? Main ????????????????????????????????????????????????????????????????????

def main():
    print("=" * 60)
    print("  ? Multi-Head Evaluator Training")
    print("=" * 60)

    # Check for training data
    if not Path(DATA_FILE).exists():
        print(f"\n? Training data not found at {DATA_FILE}")
        print("   Run this first: python training/generate_eval_data.py")
        sys.exit(1)

    set_all_seeds(SEED)

    # Load data
    features, labels, quality_tiers = load_data(DATA_FILE)

    # Determine input dimension from data
    input_dim = features.shape[1]
    print(f"\n   Input dimension: {input_dim}")

    # Create model
    model = MultiHeadEvaluator(input_dim=input_dim)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"   Total parameters: {total_params:,}")
    print(f"   Trainable parameters: {trainable_params:,}")

    # Prepare data
    train_loader, val_loader, test_loader, train_idx, val_idx, test_idx = prepare_dataloaders(features, labels, quality_tiers)

    print(f"   Train: {len(train_idx)} | Val: {len(val_idx)} | Test: {len(test_idx)}")

    # Train
    model, best_epoch = train(model, train_loader, val_loader)

    # Final evaluation on validation set
    print("\n" + "=" * 60)
    print("  Final Evaluation on Validation Set")
    print("=" * 60)

    val_results = evaluate(model, val_loader)

    print(f"\n  Validation Loss: {val_results['loss']:.4f}")
    print(f"\n  Per-Head Metrics:")
    print(f"  {'Head':<15} {'MSE':>8} {'Spearman':>12} {'p-value':>10} {'Target':>8}")
    print(f"  {'-'*55}")

    target_met = True
    for key in ["relevance", "clarity", "depth"]:
        mse = val_results[f"{key}_mse"]
        rho = val_results[f"{key}_spearman"]
        p = val_results[f"{key}_spearman_p"]
        status = "OK" if rho > 0.65 else "LOW"
        if rho <= 0.65:
            target_met = False
        print(f"  {key:<15} {mse:>8.2f} {rho:>12.4f} {p:>10.4f} {status} > 0.65")

    if target_met:
        print(f"\n  All heads exceed Spearman target of 0.65!")
    else:
        print(f"\n  Some heads below Spearman target. Consider more data or longer training.")

    # Held-out TEST SET evaluation
    print("\n" + "=" * 60)
    print("  TEST SET Evaluation (held-out, never seen during training)")
    print("=" * 60)

    test_results = evaluate(model, test_loader)

    print(f"\n  Test Loss: {test_results['loss']:.4f}")
    for key in ["relevance", "clarity", "depth"]:
        rho = test_results[f"{key}_spearman"]
        mse = test_results[f"{key}_mse"]
        print(f"  {key:<15} MSE={mse:.4f}  Spearman={rho:.4f}")
    print(f"\nTEST SET — rel={test_results['relevance_spearman']:.4f}  "
          f"cla={test_results['clarity_spearman']:.4f}  dep={test_results['depth_spearman']:.4f}")

    # MC Dropout uncertainty test (only if model supports it)
    if hasattr(model, "predict_with_uncertainty"):
        print("\n  MC Dropout Uncertainty Test (10 forward passes):")
        test_features = torch.tensor(features[:5], dtype=torch.float32)
        means, stds = model.predict_with_uncertainty(test_features, n_forward=10)
        for key in ["relevance", "clarity", "depth"]:
            print(f"    {key}: mean={means[key][:3].tolist()}, std={stds[key][:3].tolist()}")

    # Save checkpoint — wrapped with metadata so the registry can verify the
    # embedder identity matches inference (guards against the MiniLM/mpnet mix-up).
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "input_dim": input_dim,
        "embedder": "all-mpnet-base-v2",
        "embed_mode": "answer_only",
    }, CHECKPOINT_PATH)
    print(f"\n  ? Model saved to {CHECKPOINT_PATH}")

    print(f"\n? Training complete! Next step:")
    print(f"   python training/train_cross_encoder.py")


if __name__ == "__main__":
    main()
