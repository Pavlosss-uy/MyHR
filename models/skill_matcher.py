import torch
import torch.nn as nn
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

class SkillMatchSiameseNet(nn.Module):
    def __init__(self, embedding_model="all-mpnet-base-v2"):
        super(SkillMatchSiameseNet, self).__init__()
        
        self.embedder = SentenceTransformer(embedding_model)
        
        for param in self.embedder.parameters():
            param.requires_grad = False
            
        self.shared_mlp = nn.Sequential(
            nn.Linear(768, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 64)
        )

    def forward_once(self, text_input):
        with torch.no_grad():
            embeddings = self.embedder.encode(text_input, convert_to_tensor=True)
            
        embeddings = embeddings.clone().detach()
        
        # FIX: If the input is a single sentence, it returns a 1D tensor.
        # We use .unsqueeze(0) to turn shape [768] into [1, 768] to simulate a batch size of 1.
        if embeddings.dim() == 1:
            embeddings = embeddings.unsqueeze(0)
            
        projected_vector = self.shared_mlp(embeddings)
        
        return F.normalize(projected_vector, p=2, dim=1)

    def forward(self, cv_skills, jd_skills):
        cv_vector = self.forward_once(cv_skills)
        jd_vector = self.forward_once(jd_skills)
        
        return cv_vector, jd_vector

    def calculate_match_score(self, cv_skills, jd_skills):
        self.eval()
        with torch.no_grad():
            cv_vector, jd_vector = self.forward(cv_skills, jd_skills)
            cosine_sim = F.cosine_similarity(cv_vector, jd_vector)
            match_score = (cosine_sim + 1.0) / 2.0
            
        return match_score.item()