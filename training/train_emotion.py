"""
Emotion Classifier Training Script
=====================================
Trains a PyTorch emotion classifier on preprocessed audio features
with 5-fold stratified cross-validation, early stopping, and comprehensive metrics.

Pipeline:
1. Load features from data/interview_emotions_train.csv
2. Run 5-fold stratified cross-validation
3. Per fold: train with ReduceLROnPlateau + early stopping
4. Report: classification_report + confusion matrix per fold
5. Final: averaged metrics + confusion matrix plot
6. Save best model to models/checkpoints/emotion_finetuned_v2.pt

Usage:
    python training/train_emotion.py
    
Prerequisites:
    python training/preprocessing.py  (extracts audio features first)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ─── Configuration ───────────────────────────────────────────────────────────

DATA_FILE = os.path.join(PROJECT_ROOT, "data", "interview_emotions_train.csv")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "checkpoints", "emotion_finetuned_v2.pt")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "training", "results")

# Emotion labels (must match preprocessing.py)
EMOTION_LABELS = [
    "neutral", "calm", "enthusiastic", "hesitant",
    "frustrated", "nervous", "confident", "engaged",
]

# Training hyperparameters
N_FOLDS = 5
EPOCHS = 80
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 0.01
LR_PATIENCE = 3       # ReduceLROnPlateau patience
LR_FACTOR = 0.5        # ReduceLROnPlateau factor
EARLY_STOP_PATIENCE = 5
DROPOUT = 0.3

SEED = 42


# ─── Model ───────────────────────────────────────────────────────────────────

class EmotionClassifier(nn.Module):
    """
    Feed-forward emotion classifier.
    
    Architecture:
        Input → Linear(256) → BN → ReLU → Dropout
              → Linear(128) → BN → ReLU → Dropout
              → Linear(num_classes) → Softmax
    """

    def __init__(self, input_dim: int, num_classes: int = 8, dropout: float = DROPOUT):
        super().__init__()
        self.input_dim = input_dim
        self.num_classes = num_classes

        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.network(x)

    def predict_proba(self, x):
        """Return class probabilities."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            return F.softmax(logits, dim=-1)


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_data(data_path: str) -> tuple:
    """
    Load preprocessed audio features.
    
    Returns:
        features: np.array (N, D)
        labels: np.array (N,) — integer class indices
        label_names: list of str
    """
    print(f"📂 Loading data from {data_path}...")

    df = pd.read_csv(data_path)
    print(f"   Shape: {df.shape}")

    # Extract features (all columns starting with 'feature_')
    feature_cols = [c for c in df.columns if c.startswith("feature_")]
    X = df[feature_cols].values.astype(np.float32)

    # Map emotion strings to indices
    label_to_idx = {label: i for i, label in enumerate(EMOTION_LABELS)}
    valid_mask = df["emotion"].isin(EMOTION_LABELS)

    if not valid_mask.all():
        unknown = df[~valid_mask]["emotion"].unique()
        print(f"   ⚠️  Dropping {(~valid_mask).sum()} samples with unknown emotions: {unknown}")
        df = df[valid_mask]
        X = X[valid_mask.values]

    y = df["emotion"].map(label_to_idx).values.astype(np.int64)

    # Handle NaN features
    nan_mask = np.isnan(X).any(axis=1)
    if nan_mask.any():
        print(f"   ⚠️  Dropping {nan_mask.sum()} samples with NaN features")
        X = X[~nan_mask]
        y = y[~nan_mask]

    print(f"   Features: {X.shape[1]}-dim")
    print(f"   Samples: {len(y)}")
    print(f"   Class distribution:")
    for i, label in enumerate(EMOTION_LABELS):
        count = (y == i).sum()
        if count > 0:
            print(f"     {label:15s}: {count:5d}")

    return X, y, EMOTION_LABELS


# ─── Training ────────────────────────────────────────────────────────────────

def train_one_fold(
    model: EmotionClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    fold: int,
) -> tuple:
    """
    Train one fold with early stopping and LR scheduling.
    
    Returns:
        (best_model_state, best_val_f1, training_history)
    """
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", patience=LR_PATIENCE, factor=LR_FACTOR, verbose=False
    )
    criterion = nn.CrossEntropyLoss()

    best_val_loss = float("inf")
    best_val_f1 = 0.0
    best_state = None
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "val_f1": []}

    for epoch in range(1, EPOCHS + 1):
        # ── Train ──
        model.train()
        train_loss = 0.0
        n_batches = 0

        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            n_batches += 1

        train_loss /= max(n_batches, 1)

        # ── Validate ──
        model.eval()
        val_loss = 0.0
        val_batches = 0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                val_loss += loss.item()
                val_batches += 1

                preds = logits.argmax(dim=1)
                all_preds.extend(preds.tolist())
                all_labels.extend(y_batch.tolist())

        val_loss /= max(val_batches, 1)
        val_f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_f1"].append(val_f1)

        # LR scheduling
        scheduler.step(val_loss)

        # Logging
        if epoch % 10 == 0 or epoch == 1:
            current_lr = optimizer.param_groups[0]["lr"]
            print(
                f"    Epoch {epoch:3d}/{EPOCHS} | "
                f"Train: {train_loss:.4f} | Val: {val_loss:.4f} | "
                f"F1: {val_f1:.4f} | LR: {current_lr:.2e}"
            )

        # Early stopping (based on val_loss)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_f1 = val_f1
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= EARLY_STOP_PATIENCE:
                print(f"    ⏹️  Early stopping at epoch {epoch}")
                break

    return best_state, best_val_f1, history


# ─── Evaluation ──────────────────────────────────────────────────────────────

def evaluate_fold(model, val_loader, label_names, fold):
    """Evaluate a single fold and print classification report."""
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            preds = model(X_batch).argmax(dim=1)
            all_preds.extend(preds.tolist())
            all_labels.extend(y_batch.tolist())

    # Only include labels that appear in true or predicted
    present_labels = sorted(set(all_labels) | set(all_preds))
    present_names = [label_names[i] for i in present_labels]

    print(f"\n  📋 Fold {fold} Classification Report:")
    print(classification_report(
        all_labels, all_preds,
        labels=present_labels,
        target_names=present_names,
        zero_division=0,
    ))

    cm = confusion_matrix(all_labels, all_preds, labels=present_labels)
    return all_preds, all_labels, cm


def plot_confusion_matrix(cm, label_names, save_path):
    """Save confusion matrix as an image."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=label_names, yticklabels=label_names,
            ax=ax,
        )
        ax.set_xlabel("Predicted", fontsize=12)
        ax.set_ylabel("True", fontsize=12)
        ax.set_title("Emotion Classification — Confusion Matrix (Averaged)", fontsize=14)
        plt.tight_layout()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  📊 Confusion matrix saved to {save_path}")

    except ImportError:
        print("  ⚠️  matplotlib/seaborn not installed — skipping confusion matrix plot")
        # Save as text instead
        text_path = save_path.replace(".png", ".txt")
        np.savetxt(text_path, cm, fmt="%d", header=" ".join(label_names))
        print(f"  💾 Confusion matrix (text) saved to {text_path}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🎙️  Emotion Classifier Training (5-Fold CV)")
    print("=" * 60)

    # Check for preprocessed data
    if not Path(DATA_FILE).exists():
        print(f"\n❌ Preprocessed data not found at {DATA_FILE}")
        print("   Run first: python training/preprocessing.py")
        sys.exit(1)

    # Set seeds
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    # Load data
    X, y, label_names = load_data(DATA_FILE)
    input_dim = X.shape[1]
    num_classes = len(label_names)

    # Standardize features
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    print(f"\n  Model config: input_dim={input_dim}, num_classes={num_classes}")
    print(f"  Hyperparams: epochs={EPOCHS}, batch={BATCH_SIZE}, lr={LEARNING_RATE}")
    print(f"  Early stopping: patience={EARLY_STOP_PATIENCE}")
    print(f"  LR scheduling: ReduceLROnPlateau(patience={LR_PATIENCE}, factor={LR_FACTOR})")

    # ── 5-Fold Cross-Validation ──
    kfold = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)

    fold_results = []
    all_val_preds = np.zeros(len(y), dtype=np.int64)
    all_val_labels = np.zeros(len(y), dtype=np.int64)
    best_overall_f1 = 0.0
    best_overall_state = None
    best_fold_scaler = None

    total_cm = None

    print(f"\n{'='*60}")
    print(f"  Starting {N_FOLDS}-Fold Cross-Validation")
    print(f"{'='*60}")

    for fold, (train_idx, val_idx) in enumerate(kfold.split(X, y), 1):
        print(f"\n  ── Fold {fold}/{N_FOLDS} ──")
        print(f"  Train: {len(train_idx)} | Val: {len(val_idx)}")

        # Create data loaders
        X_train = torch.tensor(X[train_idx], dtype=torch.float32)
        y_train = torch.tensor(y[train_idx], dtype=torch.long)
        X_val = torch.tensor(X[val_idx], dtype=torch.float32)
        y_val = torch.tensor(y[val_idx], dtype=torch.long)

        train_ds = TensorDataset(X_train, y_train)
        val_ds = TensorDataset(X_val, y_val)

        train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

        # Create fresh model
        model = EmotionClassifier(input_dim=input_dim, num_classes=num_classes)

        # Train
        best_state, best_f1, history = train_one_fold(model, train_loader, val_loader, fold)

        # Load best state and evaluate
        model.load_state_dict(best_state)
        preds, labels, cm = evaluate_fold(model, val_loader, label_names, fold)

        # Accumulate confusion matrix
        if total_cm is None:
            total_cm = cm
        else:
            # Handle different sizes if some folds have different label sets
            if total_cm.shape == cm.shape:
                total_cm += cm

        # Track predictions for overall metrics
        all_val_preds[val_idx] = preds
        all_val_labels[val_idx] = labels

        fold_results.append({
            "fold": fold,
            "best_f1": best_f1,
            "final_train_loss": history["train_loss"][-1],
            "final_val_loss": history["val_loss"][-1],
        })

        # Track best model
        if best_f1 > best_overall_f1:
            best_overall_f1 = best_f1
            best_overall_state = best_state

        print(f"  ✅ Fold {fold} Best Weighted F1: {best_f1:.4f}")

    # ── Overall Results ──
    print(f"\n{'='*60}")
    print(f"  📊 Overall Cross-Validation Results")
    print(f"{'='*60}")

    # Per-fold summary
    print(f"\n  {'Fold':>6} {'F1':>8} {'Train Loss':>12} {'Val Loss':>10}")
    print(f"  {'-'*38}")
    for r in fold_results:
        print(f"  {r['fold']:>6d} {r['best_f1']:>8.4f} {r['final_train_loss']:>12.4f} {r['final_val_loss']:>10.4f}")

    avg_f1 = np.mean([r["best_f1"] for r in fold_results])
    std_f1 = np.std([r["best_f1"] for r in fold_results])
    print(f"\n  Average Weighted F1: {avg_f1:.4f} ± {std_f1:.4f}")

    target_met = avg_f1 > 0.55
    print(f"  Target (> 55%): {'✅ MET' if target_met else '⚠️  NOT MET'}")

    # Overall classification report
    present_labels = sorted(set(all_val_labels) | set(all_val_preds))
    present_names = [label_names[i] for i in present_labels]
    print(f"\n  📋 Overall Classification Report (All Folds Combined):")
    print(classification_report(
        all_val_labels, all_val_preds,
        labels=present_labels,
        target_names=present_names,
        zero_division=0,
    ))

    # Plot confusion matrix
    if total_cm is not None:
        cm_path = os.path.join(RESULTS_DIR, "emotion_confusion_matrix.png")
        # Use labels that appear in the confusion matrix
        cm_labels = present_names[:total_cm.shape[0]] if len(present_names) >= total_cm.shape[0] else present_names
        plot_confusion_matrix(total_cm, cm_labels, cm_path)

    # ── Save Best Model ──
    print(f"\n  💾 Saving best model (fold with F1={best_overall_f1:.4f})...")

    checkpoint = {
        "model_state_dict": best_overall_state,
        "metadata": {
            "input_dim": input_dim,
            "num_classes": num_classes,
            "emotion_labels": label_names,
            "best_f1": float(best_overall_f1),
            "avg_f1": float(avg_f1),
            "std_f1": float(std_f1),
            "n_folds": N_FOLDS,
            "training_date": datetime.now().isoformat(),
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
        },
    }

    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save(checkpoint, CHECKPOINT_PATH)
    print(f"  ✅ Model saved to {CHECKPOINT_PATH}")

    # Save results JSON
    results_path = os.path.join(RESULTS_DIR, "emotion_training_results.json")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "avg_f1": float(avg_f1),
            "std_f1": float(std_f1),
            "fold_results": fold_results,
            "num_samples": len(y),
            "feature_dim": input_dim,
            "num_classes": num_classes,
        }, f, indent=2)
    print(f"  📄 Results saved to {results_path}")

    print(f"\n✅ Emotion model training complete!")
    print(f"   Best F1: {best_overall_f1:.4f} | Avg F1: {avg_f1:.4f} ± {std_f1:.4f}")


if __name__ == "__main__":
    main()
