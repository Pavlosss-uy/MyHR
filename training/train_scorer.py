import torch
import torch.nn as nn
import torch.optim as optim
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.scoring_model import InterviewScorerMLP

def generate_synthetic_embeddings(num_samples=2500):
    print(f"🧬 Generating {num_samples} synthetic 1538-dim embedding pairs for training...")
    
    X = torch.rand(num_samples, 1538) 
    y = torch.zeros(num_samples, 1)
    
    # Normalize the embeddings so they behave like real semantic vectors
    X[:, 0:768] = torch.nn.functional.normalize(X[:, 0:768], p=2, dim=1)
    X[:, 768:1536] = torch.nn.functional.normalize(X[:, 768:1536], p=2, dim=1)
    
    for i in range(num_samples):
        q_emb = X[i, 0:768]
        f_valence = X[i, 1537].item()
        
        if i % 4 == 0:
            # PERFECT ANSWER: The Answer vector is mathematically identical to the Question vector
            X[i, 768:1536] = q_emb + (torch.rand(768) * 0.05) 
            X[i, 768:1536] = torch.nn.functional.normalize(X[i, 768:1536], p=2, dim=0)
            score = 0.95
        elif i % 4 == 1:
            # TERRIBLE ANSWER: Completely unrelated mathematical direction
            score = 0.20
        else:
            # AVERAGE ANSWER: Real cosine similarity of random vectors
            sim = torch.nn.functional.cosine_similarity(q_emb.unsqueeze(0), X[i, 768:1536].unsqueeze(0)).item()
            score = (sim + 1.0) / 2.0 
            
        # Penalize bad tone
        if f_valence < 0.5:
            score -= 0.2
            
        y[i][0] = max(0.0, min(score, 1.0))
        
    return X, y

def train():
    print("🎓 Starting True Deep Learning Training Pipeline...")
    model = InterviewScorerMLP(input_dim=1538)
    X_train, y_train = generate_synthetic_embeddings(2500)
    
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    criterion = nn.MSELoss()
    
    epochs = 200
    for epoch in range(epochs):
        optimizer.zero_grad()
        predictions = model(X_train) / 100.0 
        loss = criterion(predictions, y_train)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 40 == 0:
            print(f"🔄 Epoch [{epoch+1}/{epochs}] - Loss: {loss.item():.4f}")
            
    # SAVING AS VERSION 2
    save_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'checkpoints', 'scorer_v2.pt')
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    torch.save(model.state_dict(), save_path)
    print(f"✅ Deep Learning Training Complete! Model saved to: {save_path}")

if __name__ == "__main__":
    train()