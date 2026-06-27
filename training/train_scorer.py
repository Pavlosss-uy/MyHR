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

import hashlib
import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.scoring_model import CandidateScoringMLP
from training.metrics import regression_metrics, make_writer
from utils.seeding import set_all_seeds
from utils.trainer_logger import ExperimentLogger

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "embed_cache")


def _cached_encode(embedder, texts: list, tag: str) -> np.ndarray:
    """Encode texts with SentenceTransformer, using a file cache keyed by content hash."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5("\n".join(texts).encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{tag}_{h}.npy")
    if os.path.exists(cache_path):
        print(f"  [CACHE HIT] {tag} — loading from {os.path.basename(cache_path)}")
        return np.load(cache_path)
    embs = embedder.encode(texts, show_progress_bar=True, batch_size=16,
                           convert_to_numpy=True).astype(np.float32)
    np.save(cache_path, embs)
    return embs


def load_real_data(data_path: str):
    """
    Load Q+A pairs from eval_training_data.json, compute all-mpnet-base-v2
    embeddings, and return (X, y) tensors.

    Tone features were REMOVED: they were derived from the quality tier (label
    leakage) and were a near-constant at inference, which made the deployed model
    score noise. MOD-1 now learns purely from the question+answer content.

    Returns:
        X: FloatTensor shape (N, 1536)   # 768 question + 768 answer
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

    print("Encoding questions (cached)...")
    q_embs = _cached_encode(embedder, questions, "scorer_questions")
    print("Encoding answers (cached)...")
    a_embs = _cached_encode(embedder, answers, "scorer_answers")

    X_list, y_list = [], []
    for i, s in enumerate(valid):
        feature = np.concatenate([q_embs[i], a_embs[i]])  # (1536,) — Q + A only
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

    set_all_seeds(42)
    X, y = load_real_data(data_path)

    # 70/15/15 split — test set held out entirely from training and early-stop selection
    n = len(X)
    perm = torch.randperm(n)
    train_end = int(0.70 * n)
    val_end   = int(0.85 * n)
    train_idx = perm[:train_end]
    val_idx   = perm[train_end:val_end]
    test_idx  = perm[val_end:]
    X_train, y_train = X[train_idx], y[train_idx]
    X_val,   y_val   = X[val_idx],   y[val_idx]
    X_test,  y_test  = X[test_idx],  y[test_idx]

    print(f"\nTrain: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    model     = CandidateScoringMLP(input_dim=1536)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150)
    criterion = nn.MSELoss()
    writer    = make_writer("scorer")
    logger    = ExperimentLogger("scorer", params={"lr": 1e-3, "epochs": 300})

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
                y_val.view(-1).tolist(),
                val_preds.view(-1).tolist()
            )

        writer.add_scalar("Loss/train",     loss.item(),             epoch)
        writer.add_scalar("Loss/val",        val_loss,                epoch)
        writer.add_scalar("Metric/mae",      metrics["mae"],          epoch)
        writer.add_scalar("Metric/rmse",     metrics["rmse"],         epoch)
        writer.add_scalar("Metric/spearman", metrics["spearman_rho"], epoch)
        logger.log_metric("loss/train", loss.item(), step=epoch)
        logger.log_metric("loss/val",   val_loss,    step=epoch)
        logger.log_metric("mae",        metrics["mae"],          step=epoch)
        logger.log_metric("spearman",   metrics["spearman_rho"], step=epoch)

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
    logger.finish()
    print(f"\n[OK] Training complete.  Best val loss: {best_val_loss:.4f}")
    print(f"     Checkpoint: {save_path}")

    # --- Held-out TEST set evaluation ---
    best_state = torch.load(save_path, weights_only=True)
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        test_preds = model(X_test) / 100.0
        test_metrics = regression_metrics(
            y_test.view(-1).tolist(),
            test_preds.view(-1).tolist(),
        )
    print(f"\nTEST SET — MAE={test_metrics['mae']:.4f}  "
          f"RMSE={test_metrics['rmse']:.4f}  Spearman={test_metrics['spearman_rho']:.4f}")
    print("\nNext step: the scorer is ready to use in agent.py (already wired).")


if __name__ == "__main__":
    train()
