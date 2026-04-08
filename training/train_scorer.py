import torch
import torch.nn as nn
import torch.optim as optim
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Fixed: was 'InterviewScorerMLP' — the actual class is 'CandidateScoringMLP'
from models.scoring_model import CandidateScoringMLP
from training.metrics import regression_metrics, make_writer


def generate_synthetic_embeddings(num_samples=2500):
    print(f"Generating {num_samples} synthetic 1538-dim embedding pairs...")

    X = torch.rand(num_samples, 1538)
    y = torch.zeros(num_samples, 1)

    X[:, 0:768]    = torch.nn.functional.normalize(X[:, 0:768],    p=2, dim=1)
    X[:, 768:1536] = torch.nn.functional.normalize(X[:, 768:1536], p=2, dim=1)

    for i in range(num_samples):
        q_emb      = X[i, 0:768]
        f_valence  = X[i, 1537].item()

        if i % 4 == 0:
            # Perfect answer: embedding close to question
            X[i, 768:1536] = torch.nn.functional.normalize(
                q_emb + torch.rand(768) * 0.05, p=2, dim=0
            )
            score = 0.95
        elif i % 4 == 1:
            # Terrible answer: unrelated direction
            score = 0.20
        else:
            # Average answer: cosine-similarity based score
            sim = torch.nn.functional.cosine_similarity(
                q_emb.unsqueeze(0), X[i, 768:1536].unsqueeze(0)
            ).item()
            score = (sim + 1.0) / 2.0

        if f_valence < 0.5:
            score -= 0.2

        y[i][0] = max(0.0, min(score, 1.0))

    return X, y


def train():
    print("Starting Scorer training pipeline...")

    model = CandidateScoringMLP(input_dim=1538)
    X, y  = generate_synthetic_embeddings(2500)

    # 80/20 split
    split    = int(0.8 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    optimizer = optim.Adam(model.parameters(), lr=0.005)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", patience=10, factor=0.5)
    criterion = nn.MSELoss()
    writer    = make_writer("scorer")

    epochs           = 200
    best_loss        = float("inf")
    patience         = 20
    patience_counter = 0

    for epoch in range(epochs):
        # Training step
        model.train()
        optimizer.zero_grad()
        predictions = model(X_train) / 100.0
        loss = criterion(predictions, y_train)
        loss.backward()
        optimizer.step()

        # Validation every epoch
        model.eval()
        with torch.no_grad():
            val_preds_raw = model(X_val) / 100.0
            val_loss      = criterion(val_preds_raw, y_val).item()
            metrics = regression_metrics(
                y_val.squeeze().tolist(),
                val_preds_raw.squeeze().tolist()
            )

        scheduler.step(val_loss)

        writer.add_scalar("Loss/train",      loss.item(),             epoch)
        writer.add_scalar("Loss/val",         val_loss,                epoch)
        writer.add_scalar("Metric/mae",       metrics["mae"],          epoch)
        writer.add_scalar("Metric/rmse",      metrics["rmse"],         epoch)
        writer.add_scalar("Metric/spearman",  metrics["spearman_rho"], epoch)

        if (epoch + 1) % 40 == 0:
            print(
                f"Epoch [{epoch+1}/{epochs}] "
                f"train_loss={loss.item():.4f}  val_loss={val_loss:.4f} | "
                f"MAE={metrics['mae']:.4f}  Spearman={metrics['spearman_rho']:.4f}"
            )

        if val_loss < best_loss:
            best_loss        = val_loss
            patience_counter = 0
            save_path = os.path.join(
                os.path.dirname(__file__), "..", "models", "checkpoints", "scorer_v2.pt"
            )
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            torch.save(model.state_dict(), save_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch+1} (best val loss: {best_loss:.4f})")
                break

    writer.close()
    print(f"\nTraining complete. Best val loss: {best_loss:.4f}")
    print(f"Checkpoint: models/checkpoints/scorer_v2.pt")


if __name__ == "__main__":
    train()
