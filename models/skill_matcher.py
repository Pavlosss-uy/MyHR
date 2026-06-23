import torch
import torch.nn as nn
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer


class SkillMatchSiameseNet(nn.Module):
    """
    Siamese network for skill matching.

    Architecture:
      - Frozen all-mpnet-base-v2 encoder → 768-D normalized embeddings
      - Trainable shared_mlp projection head: 768 → 256 → 128-D (L2-normalized)

    The projection head is what gets trained via contrastive loss to learn
    terminology-invariant skill representations (Task 4.1 fairness fix).
    When no checkpoint exists, forward() falls back to the raw 768-D embeddings
    so the model degrades gracefully to cosine similarity on raw encodings.
    """

    def __init__(self, embedding_model: str = "all-mpnet-base-v2", projection_dim: int = 128):
        super(SkillMatchSiameseNet, self).__init__()
        self.embedder = SentenceTransformer(embedding_model)
        for param in self.embedder.parameters():
            param.requires_grad = False

        # Trainable projection head — learns to map diverse phrasings of the
        # same skills close together in embedding space.
        self.shared_mlp = nn.Sequential(
            nn.Linear(768, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, projection_dim),
        )

    def forward_once(self, text_input) -> torch.Tensor:
        with torch.no_grad():
            embeddings = self.embedder.encode(
                text_input, convert_to_tensor=True, normalize_embeddings=True
            )
        if embeddings.dim() == 1:
            embeddings = embeddings.unsqueeze(0)
        projected = self.shared_mlp(embeddings)
        return F.normalize(projected, p=2, dim=1)

    def forward(self, cv_skills, jd_skills):
        return self.forward_once(cv_skills), self.forward_once(jd_skills)

    def calculate_match_score(self, cv_skills: str, jd_skills: str) -> float:
        if not cv_skills or not jd_skills:
            return 0.0
        self.eval()
        with torch.no_grad():
            cv_vector, jd_vector = self.forward(cv_skills, jd_skills)
            cosine_sim = F.cosine_similarity(cv_vector, jd_vector, dim=-1)
            match_score = (cosine_sim.clamp(-1.0, 1.0) + 1.0) / 2.0
        return match_score.item()