import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import os
import torch.nn.functional as F

from recommender.candidate_ranker import NeuralCandidateRanker

class DummyRankingDataset(Dataset):
    """
    Simulates past interview data. 
    Each item contains an Ideal Profile, a Hired Candidate's features, 
    and a Rejected Candidate's features.
    """
    def __init__(self, num_samples=200):
        self.num_samples = num_samples

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # 8 normalized features: [skill_match, relevance, clarity, depth, confidence, consistency, gaps(inverted), experience]
        ideal_profile = torch.tensor([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=torch.float32)
        
        # Hired candidate: High scores, close to ideal (between 0.8 and 1.0)
        hired_features = ideal_profile * torch.empty(8).uniform_(0.8, 1.0)
        
        # Rejected candidate: Lower scores (between 0.3 and 0.7)
        rejected_features = ideal_profile * torch.empty(8).uniform_(0.3, 0.7)
        
        return ideal_profile, hired_features, rejected_features

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Pairwise Ranking training on {device}...")

    # 1. Setup Data
    dataset = DummyRankingDataset(num_samples=300)
    dataloader = DataLoader(dataset, batch_size=16, shuffle=True)

    # 2. Setup Model and Optimizer
    model = NeuralCandidateRanker(input_features=8, embedding_dim=32).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    
    # MarginRankingLoss pushes sim(hired) to be strictly greater than sim(rejected) by at least 'margin'
    criterion = nn.MarginRankingLoss(margin=0.2)

    epochs = 20
    best_loss = float('inf')

    # 3. Training Loop
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0

        for ideal, hired, rejected in dataloader:
            ideal = ideal.to(device)
            hired = hired.to(device)
            rejected = rejected.to(device)

            optimizer.zero_grad()
            
            # Pass all profiles through the neural network to get their 32-dimensional embeddings
            ideal_emb = model(ideal)
            hired_emb = model(hired)
            rejected_emb = model(rejected)
            
            # Calculate how similar both candidates are to the ideal profile
            sim_hired = F.cosine_similarity(hired_emb, ideal_emb)
            sim_rejected = F.cosine_similarity(rejected_emb, ideal_emb)
            
            # The target is 1, meaning we expect sim_hired to be > sim_rejected
            target = torch.ones_like(sim_hired)
            
            # Calculate loss and update weights
            loss = criterion(sim_hired, sim_rejected, target)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)
        
        # Print every 2 epochs to keep terminal clean
        if (epoch + 1) % 2 == 0:
            print(f"Epoch {epoch+1}/{epochs} | Ranking Loss: {avg_loss:.4f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            os.makedirs("models/checkpoints", exist_ok=True)
            torch.save(model.state_dict(), "models/checkpoints/candidate_ranker_v1.pt")
    
    print("\n--> Checkpoint saved: models/checkpoints/candidate_ranker_v1.pt")

    # 4. Quick Inference Test
    print("\n--- Quick Inference Test ---")
    model.eval()
    with torch.no_grad():
        ideal = torch.tensor([[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]])
        
        # Candidate A: Strong technically, good clarity
        cand_a = torch.tensor([[0.9, 0.85, 0.9, 0.95, 0.8, 0.9, 0.85, 0.9]])
        
        # Candidate B: Weak technical depth, lots of skill gaps
        cand_b = torch.tensor([[0.4, 0.5, 0.6, 0.3, 0.5, 0.4, 0.2, 0.5]])
        
        # Combine into a batch
        candidates = torch.cat([cand_a, cand_b], dim=0)
        
        # Call the rank_candidates function we built
        scores, indices = model.rank_candidates(candidates, ideal)
        
        print("Candidate Profiles Ranked:")
        for rank, idx in enumerate(indices):
            cand_name = "Candidate A (Strong)" if idx == 0 else "Candidate B (Weak)"
            print(f"Rank {rank+1}: {cand_name} - Match Score: {scores[rank]:.4f}")

if __name__ == "__main__":
    main()