import json
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import os

from models.candidate_ranker import NeuralCandidateRanker
from training.metrics import ranking_metrics, make_writer


class RealRankingDataset(Dataset):
    """
    Loads real developer ranking triplets from the SO 2018 survey.
    Each item: (anchor, positive, negative) as 8-D feature tensors.
    anchor   = mean feature vector for a DevType
    positive = high-salary developer in that DevType (top 25%)
    negative = low-salary developer in that DevType (bottom 25%)
    """
    def __init__(self, json_path: str):
        with open(json_path, encoding="utf-8") as f:
            self.data = json.load(f)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        anchor   = torch.tensor(item["anchor"],   dtype=torch.float32)
        positive = torch.tensor(item["positive"], dtype=torch.float32)
        negative = torch.tensor(item["negative"], dtype=torch.float32)
        return anchor, positive, negative


class DummyRankingDataset(Dataset):
    """Fallback when real data file is missing."""
    def __init__(self, num_samples=200):
        self.num_samples = num_samples

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        ideal_profile     = torch.tensor([1.0] * 8, dtype=torch.float32)
        hired_features    = ideal_profile * torch.empty(8).uniform_(0.8, 1.0)
        rejected_features = ideal_profile * torch.empty(8).uniform_(0.3, 0.7)
        return ideal_profile, hired_features, rejected_features


def evaluate_ranking(model, val_loader, device):
    """
    Collect similarity scores and binary labels for ranking metric computation.
    """
    model.eval()
    all_scores, all_labels = [], []

    with torch.no_grad():
        for ideal, hired, rejected in val_loader:
            ideal    = ideal.to(device)
            hired    = hired.to(device)
            rejected = rejected.to(device)

            ideal_emb    = model(ideal)
            hired_emb    = model(hired)
            rejected_emb = model(rejected)

            sim_hired    = F.cosine_similarity(hired_emb,    ideal_emb).cpu().tolist()
            sim_rejected = F.cosine_similarity(rejected_emb, ideal_emb).cpu().tolist()

            for sh, sr in zip(sim_hired, sim_rejected):
                # Treat each (hired, rejected) pair as a ranking task:
                # scores = [sim_hired, sim_rejected], labels = [1, 0]
                all_scores.append([sh, sr])
                all_labels.append([1,   0])

    return ranking_metrics(all_scores, all_labels, k=5)


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Pairwise Ranking training on {device}...")

    # 1. Data — 80/20 split
    real_data_path = "data/ranking_pairs.json"
    if os.path.exists(real_data_path):
        dataset = RealRankingDataset(real_data_path)
        print(f"Loaded {len(dataset)} real SO survey triplets from {real_data_path}")
    else:
        print("WARNING: Real data not found, falling back to DummyRankingDataset")
        dataset = DummyRankingDataset(num_samples=300)
    train_size = int(0.8 * len(dataset))
    val_size   = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=16)

    # 2. Model, optimizer, scheduler
    model     = NeuralCandidateRanker(input_features=8, embedding_dim=32).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", patience=3, factor=0.5)
    criterion = nn.MarginRankingLoss(margin=0.2)
    writer    = make_writer("candidate_ranker")

    epochs          = 20
    best_loss       = float("inf")
    patience        = 5
    patience_counter = 0

    # 3. Training loop
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0

        for ideal, hired, rejected in train_loader:
            ideal    = ideal.to(device)
            hired    = hired.to(device)
            rejected = rejected.to(device)

            optimizer.zero_grad()
            ideal_emb    = model(ideal)
            hired_emb    = model(hired)
            rejected_emb = model(rejected)

            sim_hired    = F.cosine_similarity(hired_emb,    ideal_emb)
            sim_rejected = F.cosine_similarity(rejected_emb, ideal_emb)
            target       = torch.ones_like(sim_hired)

            loss = criterion(sim_hired, sim_rejected, target)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss     = total_loss / len(train_loader)
        rank_metrics = evaluate_ranking(model, val_loader, device)

        # LR scheduler step
        scheduler.step(avg_loss)

        # TensorBoard
        writer.add_scalar("Loss/train",              avg_loss,                          epoch)
        writer.add_scalar("Metric/ndcg_at_5",        rank_metrics["ndcg_at_k"],         epoch)
        writer.add_scalar("Metric/pairwise_accuracy",rank_metrics["pairwise_accuracy"], epoch)

        if (epoch + 1) % 2 == 0:
            print(
                f"Epoch {epoch+1}/{epochs} | "
                f"Ranking Loss: {avg_loss:.4f} | "
                f"NDCG@5: {rank_metrics['ndcg_at_k']:.4f}  "
                f"Pairwise Acc: {rank_metrics['pairwise_accuracy']:.4f}"
            )

        if avg_loss < best_loss:
            best_loss        = avg_loss
            patience_counter = 0
            os.makedirs("models/checkpoints", exist_ok=True)
            torch.save(
                model.state_dict(),
                "models/checkpoints/candidate_ranker_v1.pt"
            )
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch+1} (best loss: {best_loss:.4f})")
                break

    writer.close()
    print("\nCheckpoint saved: models/checkpoints/candidate_ranker_v1.pt")

    # 4. Inference test
    print("\n--- Quick Inference Test ---")
    model.eval()
    with torch.no_grad():
        ideal  = torch.tensor([[1.0] * 8])
        cand_a = torch.tensor([[0.9, 0.85, 0.9, 0.95, 0.8, 0.9, 0.85, 0.9]])
        cand_b = torch.tensor([[0.4, 0.5,  0.6, 0.3,  0.5, 0.4, 0.2,  0.5]])
        candidates = torch.cat([cand_a, cand_b], dim=0)
        scores, indices = model.rank_candidates(candidates, ideal)
        for rank, idx in enumerate(indices):
            name = "Candidate A (Strong)" if idx == 0 else "Candidate B (Weak)"
            print(f"Rank {rank+1}: {name} — Match Score: {scores[rank]:.4f}")


if __name__ == "__main__":
    main()
