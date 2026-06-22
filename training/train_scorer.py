"""
Candidate Scoring MLP Training Script (MOD-1)
==============================================
Trains CandidateScoringMLP on real Q+A pairs from eval_training_data.json.

Input features (1538-dim per sample):
  - 768-dim question embedding (all-mpnet-base-v2)
  - 768-dim answer embedding   (all-mpnet-base-v2)
  -   2-dim tone features      (confidence, valence — derived from quality tier)

Target: overall_quality / 100  (regressed to 0-1, model output scaled ×100)

Usage:
    python training/train_scorer.py

Prerequisites:
    python training/generate_eval_data.py  (builds data/eval_training_data.json)
"""

import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.scoring_model import CandidateScoringMLP
from training.metrics import regression_metrics, make_writer

# ---------------------------------------------------------------------------
# Tone feature proxy — maps quality tier to (confidence, valence)
# Real inference uses the live emotion model; training uses these proxies
# because the emotion model expects audio, not text.
# ---------------------------------------------------------------------------
TIER_TONE = {
    "excellent": (0.90, 1.0),
    "good":      (0.72, 0.8),
    "mediocre":  (0.50, 0.4),
    "poor":      (0.28, 0.1),
}


def load_real_data(data_path: str):
    """
    Load Q+A pairs from eval_training_data.json, compute all-mpnet-base-v2
    embeddings, attach tone proxies, and return (X, y) tensors.

    Returns:
        X: FloatTensor shape (N, 1538)
        y: FloatTensor shape (N, 1)
    """
    print(f"Loading training data from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data["samples"]
    print(f"  Found {len(samples)} samples.")

    # Filter samples that have the required fields
    valid = [s for s in samples if "question" in s and "answer" in s and "overall_quality" in s]
    print(f"  {len(valid)} samples have question/answer/overall_quality.")

    # Lazy-load the embedding model once
    print("Loading all-mpnet-base-v2 embedder (this may take a minute)...")
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("all-mpnet-base-v2")

    questions = [s["question"] for s in valid]
    answers   = [s["answer"]   for s in valid]

    print("Encoding questions...")
    q_embs = embedder.encode(questions, show_progress_bar=True, batch_size=16,
                              convert_to_numpy=True)
    print("Encoding answers...")
    a_embs = embedder.encode(answers,   show_progress_bar=True, batch_size=16,
                              convert_to_numpy=True)

    X_list, y_list = [], []
    for i, s in enumerate(valid):
        tier = s.get("quality_tier", "mediocre")
        tone_conf, tone_val = TIER_TONE.get(tier, (0.5, 0.5))

        tone = np.array([tone_conf, tone_val], dtype=np.float32)
        feature = np.concatenate([q_embs[i], a_embs[i], tone])  # (1538,)
        X_list.append(feature)

        target = float(s["overall_quality"]) / 100.0
        y_list.append([target])

    X = torch.tensor(np.array(X_list, dtype=np.float32))
    y = torch.tensor(np.array(y_list, dtype=np.float32))
    print(f"\nDataset ready: X={tuple(X.shape)}, y={tuple(y.shape)}")
    return X, y


def train():
    print("=" * 60)
    print("  MOD-1: CandidateScoringMLP Training (Real Embeddings)")
    print("=" * 60)

    data_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "eval_training_data.json"
    )
    if not os.path.exists(data_path):
        print(f"[ERROR] Training data not found at {data_path}")
        print("        Run: python training/generate_eval_data.py first.")
        sys.exit(1)

    X, y = load_real_data(data_path)

    # 80/20 split
    indices = torch.randperm(len(X))
    split   = int(0.8 * len(X))
    train_idx, val_idx = indices[:split], indices[split:]
    X_train, y_train = X[train_idx], y[train_idx]
    X_val,   y_val   = X[val_idx],   y[val_idx]

    print(f"\nTrain: {len(X_train)} | Val: {len(X_val)}")

    model     = CandidateScoringMLP(input_dim=1538)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150)
    criterion = nn.MSELoss()
    writer    = make_writer("scorer")

    epochs           = 300
    best_val_loss    = float("inf")
    patience_max     = 40
    patience_counter = 0

    save_path = os.path.join(
        os.path.dirname(__file__), "..", "models", "checkpoints", "scorer_v2.pt"
    )
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        preds = model(X_train) / 100.0
        loss  = criterion(preds, y_train)
        loss.backward()
        optimizer.step()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            val_preds = model(X_val) / 100.0
            val_loss  = criterion(val_preds, y_val).item()
            metrics   = regression_metrics(
                y_val.squeeze().tolist(),
                val_preds.squeeze().tolist()
            )

        writer.add_scalar("Loss/train",     loss.item(),             epoch)
        writer.add_scalar("Loss/val",        val_loss,                epoch)
        writer.add_scalar("Metric/mae",      metrics["mae"],          epoch)
        writer.add_scalar("Metric/rmse",     metrics["rmse"],         epoch)
        writer.add_scalar("Metric/spearman", metrics["spearman_rho"], epoch)

        if (epoch + 1) % 50 == 0:
            print(
                f"Epoch [{epoch+1:3d}/{epochs}] "
                f"train={loss.item():.4f}  val={val_loss:.4f} | "
                f"MAE={metrics['mae']:.4f}  Spearman={metrics['spearman_rho']:.4f}"
            )

        if val_loss < best_val_loss:
            best_val_loss    = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), save_path)
        else:
            patience_counter += 1
            if patience_counter >= patience_max:
                print(f"Early stopping at epoch {epoch + 1}  (best val: {best_val_loss:.4f})")
                break

    writer.close()
    print(f"\n[OK] Training complete.  Best val loss: {best_val_loss:.4f}")
    print(f"     Checkpoint: {save_path}")
    print("\nNext step: the scorer is ready to use in agent.py (already wired).")


if __name__ == "__main__":
    train()
