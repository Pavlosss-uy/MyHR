import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import os

from models.skill_matcher import SkillMatchSiameseNet

# ---------------------------------------------------------
# 1. Contrastive Loss Function
# ---------------------------------------------------------
class ContrastiveLoss(nn.Module):
    """
    Contrastive loss function.
    Based on: http://yann.lecun.com/exdb/publis/pdf/hadsell-chopra-lecun-06.pdf
    """
    def __init__(self, margin=2.0):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin

    def forward(self, output1, output2, label):
        # label = 1 for match (similar), label = 0 for mismatch (dissimilar)
        euclidean_distance = F.pairwise_distance(output1, output2, keepdim=True)
        
        loss_contrastive = torch.mean(
            (label) * torch.pow(euclidean_distance, 2) +       # If match, minimize distance
            (1 - label) * torch.pow(torch.clamp(self.margin - euclidean_distance, min=0.0), 2) # If mismatch, push apart
        )
        return loss_contrastive

# ---------------------------------------------------------
# 2. Dummy Dataset (So you can run this right now)
# ---------------------------------------------------------
class DummySkillDataset(Dataset):
    def __init__(self, num_samples=100):
        self.num_samples = num_samples
        # Pairs of skills that conceptually mean the same thing
        self.cv_skills = [
            "Python, Django, REST APIs, PostgreSQL",
            "Java, Spring Boot, Microservices",
            "React.js, Node.js, Express, MongoDB",
            "C++, Unreal Engine, 3D Math"
        ]
        self.jd_skills = [
            "Backend Web Developer with Python frameworks",
            "Enterprise Java Engineer",
            "Fullstack JavaScript Developer (MERN)",
            "Game Developer (C++ / Blueprints)"
        ]

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Generate alternating matches and mismatches
        is_match = idx % 2
        base_idx = (idx // 2) % len(self.cv_skills)

        cv_text = self.cv_skills[base_idx]
        
        if is_match:
            jd_text = self.jd_skills[base_idx]
            label = 1.0 # Match
        else:
            # Shift the index by 1 to create a deliberate mismatch
            jd_text = self.jd_skills[(base_idx + 1) % len(self.jd_skills)]
            label = 0.0 # Mismatch

        return cv_text, jd_text, torch.tensor([label], dtype=torch.float32)

# ---------------------------------------------------------
# 3. Main Training Loop
# ---------------------------------------------------------
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Siamese Network training on {device}...")

    # Initialize Dataset and DataLoader
    dataset = DummySkillDataset(num_samples=160)
    dataloader = DataLoader(dataset, batch_size=16, shuffle=True)

    # Initialize Model, Loss, and Optimizer
    model = SkillMatchSiameseNet().to(device)
    criterion = ContrastiveLoss(margin=2.0)
    
    # We only optimize the shared MLP, since the sentence-transformer is frozen
    optimizer = optim.AdamW(model.shared_mlp.parameters(), lr=1e-3)

    epochs = 10
    best_loss = float('inf')

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0

        for batch_idx, (cv_texts, jd_texts, labels) in enumerate(dataloader):
            labels = labels.to(device)

            optimizer.zero_grad()
            
            # Forward pass through the Siamese network
            cv_vectors, jd_vectors = model(cv_texts, jd_texts)
            
            # Calculate loss
            loss = criterion(cv_vectors, jd_vectors, labels)
            
            # Backward pass and optimize
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{epochs} | Contrastive Loss: {avg_loss:.4f}")

        # Save the best model
        if avg_loss < best_loss:
            best_loss = avg_loss
            os.makedirs("models/checkpoints", exist_ok=True)
            torch.save(model.state_dict(), "models/checkpoints/skill_matcher_v1.pt")
            print("--> Checkpoint saved!")

    print("\nTraining Complete!")
    
    # Let's do a quick inference test to see it working
    print("\n--- Quick Inference Test ---")
    model.eval()
    test_cv = "I have 3 years of experience building web apps with Django and Python."
    test_jd_match = "Looking for a Python backend engineer."
    test_jd_mismatch = "Looking for a React frontend developer."
    
    match_score = model.calculate_match_score(test_cv, test_jd_match)
    mismatch_score = model.calculate_match_score(test_cv, test_jd_mismatch)
    
    print(f"Match Score (Should be high): {match_score:.4f}")
    print(f"Mismatch Score (Should be low): {mismatch_score:.4f}")

if __name__ == "__main__":
    main()