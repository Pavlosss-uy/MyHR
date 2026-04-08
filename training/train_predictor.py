import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import os
import random

from models.performance_predictor import PerformancePredictor
from training.metrics import regression_metrics, make_writer


class DummyPerformanceDataset(Dataset):
    """
    Simulates historical HR data where we have the candidate's original
    interview features AND their actual 1-10 performance review score after 1 year.
    """
    def __init__(self, num_samples=500):
        self.num_samples = num_samples

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        features = torch.empty(8).uniform_(0.2, 1.0)
        base_score = (features[0] * 2.5 + features[2] * 2.0 +
                      features[3] * 2.5 + features.mean() * 3.0)
        noise = random.uniform(-1.0, 1.0)
        final_score = max(1.0, min(10.0, (base_score + noise).item()))
        return features, torch.tensor([final_score], dtype=torch.float32)


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Performance Predictor training on {device}...")

    # 1. Setup Data — 80/20 split
    dataset    = DummyPerformanceDataset(num_samples=1000)
    train_size = int(0.8 * len(dataset))
    val_size   = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=32)

    # 2. Model, optimizer, scheduler
    model     = PerformancePredictor(input_dim=8).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.01)
    criterion = nn.MSELoss()
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=5, factor=0.5
    )
    writer = make_writer("performance_predictor")

    epochs      = 30
    best_loss   = float("inf")
    best_spearman = -1.0
    patience_counter = 0

    # 3. Training loop
    for epoch in range(epochs):
        # --- train ---
        model.train()
        train_loss_total = 0.0
        for features, target_score in train_loader:
            features     = features.to(device)
            target_score = target_score.to(device)
            optimizer.zero_grad()
            predictions = model(features)
            loss = criterion(predictions, target_score)
            loss.backward()
            optimizer.step()
            train_loss_total += loss.item()

        avg_train_loss = train_loss_total / len(train_loader)

        # --- validate ---
        model.eval()
        val_loss_total = 0.0
        val_preds, val_true = [], []
        with torch.no_grad():
            for features, target_score in val_loader:
                features     = features.to(device)
                target_score = target_score.to(device)
                predictions  = model(features)
                loss = criterion(predictions, target_score)
                val_loss_total += loss.item()
                val_preds.extend(predictions.squeeze().cpu().tolist())
                val_true.extend(target_score.squeeze().cpu().tolist())

        avg_val_loss = val_loss_total / len(val_loader)
        metrics = regression_metrics(val_true, val_preds)

        # --- TensorBoard ---
        writer.add_scalar("Loss/train",        avg_train_loss,          epoch)
        writer.add_scalar("Loss/val",          avg_val_loss,            epoch)
        writer.add_scalar("Metric/mae",        metrics["mae"],          epoch)
        writer.add_scalar("Metric/rmse",       metrics["rmse"],         epoch)
        writer.add_scalar("Metric/spearman",   metrics["spearman_rho"], epoch)
        writer.add_scalar("Metric/pearson",    metrics["pearson_r"],    epoch)
        writer.add_scalar("LR", optimizer.param_groups[0]["lr"],        epoch)

        if (epoch + 1) % 5 == 0:
            print(
                f"Epoch {epoch+1}/{epochs} | "
                f"train_loss={avg_train_loss:.4f}  val_loss={avg_val_loss:.4f} | "
                f"MAE={metrics['mae']:.4f}  RMSE={metrics['rmse']:.4f}  "
                f"Spearman={metrics['spearman_rho']:.4f}"
            )

        scheduler.step(avg_val_loss)

        # Early stopping on val loss
        if avg_val_loss < best_loss:
            best_loss      = avg_val_loss
            best_spearman  = metrics["spearman_rho"]
            patience_counter = 0
            os.makedirs("models/checkpoints", exist_ok=True)
            torch.save(
                model.state_dict(),
                "models/checkpoints/performance_predictor_v1.pt"
            )
        else:
            patience_counter += 1
            if patience_counter >= 7:
                print(f"Early stopping at epoch {epoch+1}")
                break

    writer.close()
    print(
        f"\nCheckpoint saved: models/checkpoints/performance_predictor_v1.pt"
        f"\nBest val loss: {best_loss:.4f}  |  Best Spearman ρ: {best_spearman:.4f}"
    )

    # 4. Quick inference test
    print("\n--- Quick Inference Test ---")
    model.eval()
    with torch.no_grad():
        rockstar = torch.tensor([[0.95, 0.9, 0.92, 0.98, 0.85, 0.9, 0.95, 0.9]])
        mediocre = torch.tensor([[0.5,  0.4, 0.55, 0.45, 0.6,  0.5, 0.4,  0.5]])
        print(f"Rockstar candidate: {model.predict_performance(rockstar)} / 10.0")
        print(f"Mediocre candidate: {model.predict_performance(mediocre)} / 10.0")


if __name__ == "__main__":
    main()
