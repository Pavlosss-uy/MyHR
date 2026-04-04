import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import os
import random

from models.performance_predictor import PerformancePredictor

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
        # Generate random normalized features (0.0 to 1.0)
        # Features: [skill_match, relevance, clarity, depth, confidence, consistency, gaps_inverted, experience]
        features = torch.empty(8).uniform_(0.2, 1.0)
        
        # We simulate a "ground truth" performance score based heavily on their interview skills
        # We give high weight to skill_match (idx 0), clarity (idx 2), and depth (idx 3)
        base_score = (features[0]*2.5 + features[2]*2.0 + features[3]*2.5 + features.mean()*3.0)
        
        # Add some real-world randomness/noise
        noise = random.uniform(-1.0, 1.0)
        final_score = base_score + noise
        
        # Clamp between 1.0 and 10.0
        final_score = max(1.0, min(10.0, final_score.item()))
        
        return features, torch.tensor([final_score], dtype=torch.float32)

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Performance Predictor training on {device}...")

    # 1. Setup Data
    dataset = DummyPerformanceDataset(num_samples=1000)
    # 80/20 train-validation split
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    # 2. Setup Model and Optimizer
    model = PerformancePredictor(input_dim=8).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.01)
    
    # MSE Loss is the standard for regression (predicting continuous numbers)
    criterion = nn.MSELoss()

    epochs = 30
    best_loss = float('inf')

    # 3. Training Loop
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0

        for features, target_score in train_loader:
            features = features.to(device)
            target_score = target_score.to(device)

            optimizer.zero_grad()
            
            # Predict the 1-10 score
            predictions = model(features)
            
            # Calculate how far off the prediction was from the actual score
            loss = criterion(predictions, target_score)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        
        # Print every 5 epochs
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1}/{epochs} | MSE Loss: {avg_loss:.4f}")

        # Save the best model
        if avg_loss < best_loss:
            best_loss = avg_loss
            os.makedirs("models/checkpoints", exist_ok=True)
            torch.save(model.state_dict(), "models/checkpoints/performance_predictor_v1.pt")
    
    print("\n--> Checkpoint saved: models/checkpoints/performance_predictor_v1.pt")

    # 4. Quick Inference Test
    print("\n--- Quick Inference Test ---")
    
    # Candidate 1: Rockstar interview (all features around 0.9 - 1.0)
    rockstar_features = torch.tensor([[0.95, 0.9, 0.92, 0.98, 0.85, 0.9, 0.95, 0.9]])
    
    # Candidate 2: Mediocre interview (all features around 0.4 - 0.6)
    mediocre_features = torch.tensor([[0.5, 0.4, 0.55, 0.45, 0.6, 0.5, 0.4, 0.5]])
    
    rockstar_pred = model.predict_performance(rockstar_features)
    mediocre_pred = model.predict_performance(mediocre_features)
    
    print(f"Predicted Job Performance for Rockstar Candidate: {rockstar_pred} / 10.0")
    print(f"Predicted Job Performance for Mediocre Candidate: {mediocre_pred} / 10.0")

if __name__ == "__main__":
    main()