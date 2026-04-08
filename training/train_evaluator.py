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

import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import TensorDataset, DataLoader
from scipy.stats import spearmanr
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from models.multi_head_evaluator import MultiHeadEvaluator
from training.metrics import make_writer


# ??? Configuration ???????????????????????????????????????????????????????????

DATA_FILE = os.path.join(PROJECT_ROOT, "data", "eval_training_data.json")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "checkpoints", "evaluator_v1.pt")

# Training hyperparameters
EPOCHS = 100
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 0.01
T_MAX = 50  # CosineAnnealing period
EARLY_STOP_PATIENCE = 10
VAL_SPLIT = 0.2

# Loss weights (must sum to 1.0)
LOSS_WEIGHTS = {
    "relevance": 0.35,
    "clarity": 0.30,
    "depth": 0.35,
}

# Random seed for reproducibility
SEED = 42


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

    # Extract features and labels
    features = np.array([s["features"] for s in samples], dtype=np.float32)
    labels = {
        "relevance": np.array([s["relevance"] for s in samples], dtype=np.float32),
        "clarity": np.array([s["clarity"] for s in samples], dtype=np.float32),
        "depth": np.array([s["technical_depth"] for s in samples], dtype=np.float32),
    }

    print(f"   Features shape: {features.shape}")
    print(f"   Label ranges: relevance=[{labels['relevance'].min():.0f}, {labels['relevance'].max():.0f}], "
          f"clarity=[{labels['clarity'].min():.0f}, {labels['clarity'].max():.0f}], "
          f"depth=[{labels['depth'].min():.0f}, {labels['depth'].max():.0f}]")

    return features, labels


def prepare_dataloaders(features, labels, val_split=VAL_SPLIT, seed=SEED):
    """Split data into train/val and create DataLoaders."""
    np.random.seed(seed)
    n = len(features)
    indices = np.random.permutation(n)
    val_size = int(n * val_split)

    val_idx = indices[:val_size]
    train_idx = indices[val_size:]

    print(f"\n? Train/Val split: {len(train_idx)}/{len(val_idx)}")

    def make_loader(idx, shuffle=False):
        X = torch.tensor(features[idx])
        y_rel = torch.tensor(labels["relevance"][idx])
        y_cla = torch.tensor(labels["clarity"][idx])
        y_dep = torch.tensor(labels["depth"][idx])
        ds = TensorDataset(X, y_rel, y_cla, y_dep)
        return DataLoader(ds, batch_size=BATCH_SIZE, shuffle=shuffle)

    train_loader = make_loader(train_idx, shuffle=True)
    val_loader = make_loader(val_idx, shuffle=False)

    return train_loader, val_loader, train_idx, val_idx


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
        LOSS_WEIGHTS["relevance"] * F.mse_loss(rel.squeeze(), y_rel)
        + LOSS_WEIGHTS["clarity"] * F.mse_loss(cla.squeeze(), y_cla)
        + LOSS_WEIGHTS["depth"] * F.mse_loss(dep.squeeze(), y_dep)
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
                all_preds[key].extend(pred_t.squeeze().tolist())
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

        # ?? TensorBoard ??
        writer.add_scalar("Loss/train", train_loss, epoch)
        writer.add_scalar("Loss/val", val_loss, epoch)
        writer.add_scalar("LR", optimizer.param_groups[0]["lr"], epoch)
        for key in ["relevance", "clarity", "depth"]:
            writer.add_scalar(f"Metric/{key}_spearman", val_results[f"{key}_spearman"], epoch)
            writer.add_scalar(f"Metric/{key}_mse",      val_results[f"{key}_mse"],      epoch)

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

    # Set seed
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    # Load data
    features, labels = load_data(DATA_FILE)

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
    train_loader, val_loader, _, val_idx = prepare_dataloaders(features, labels)

    # Train
    model, best_epoch = train(model, train_loader, val_loader)

    # Final evaluation
    print("\n" + "=" * 60)
    print("  ? Final Evaluation on Validation Set")
    print("=" * 60)

    val_results = evaluate(model, val_loader)

    print(f"\n  Validation Loss: {val_results['loss']:.4f}")
    print(f"\n  Per-Head Metrics:")
    print(f"  {'Head':<15} {'MSE':>8} {'Spearman ?':>12} {'p-value':>10} {'Target':>8}")
    print(f"  {'-'*55}")

    target_met = True
    for key in ["relevance", "clarity", "depth"]:
        mse = val_results[f"{key}_mse"]
        rho = val_results[f"{key}_spearman"]
        p = val_results[f"{key}_spearman_p"]
        status = "?" if rho > 0.65 else "??"
        if rho <= 0.65:
            target_met = False
        print(f"  {key:<15} {mse:>8.2f} {rho:>12.4f} {p:>10.4f} {status} > 0.65")

    if target_met:
        print(f"\n  ? All heads exceed Spearman target of 0.65!")
    else:
        print(f"\n  ??  Some heads below Spearman target. Consider more data or longer training.")

    # MC Dropout uncertainty test (only if model supports it)
    if hasattr(model, "predict_with_uncertainty"):
        print("\n  MC Dropout Uncertainty Test (10 forward passes):")
        test_features = torch.tensor(features[:5], dtype=torch.float32)
        means, stds = model.predict_with_uncertainty(test_features, n_forward=10)
        for key in ["relevance", "clarity", "depth"]:
            print(f"    {key}: mean={means[key][:3].tolist()}, std={stds[key][:3].tolist()}")

    # Save checkpoint
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save(model.state_dict(), CHECKPOINT_PATH)
    print(f"\n  ? Model saved to {CHECKPOINT_PATH}")

    print(f"\n? Training complete! Next step:")
    print(f"   python training/train_cross_encoder.py")


if __name__ == "__main__":
    main()
