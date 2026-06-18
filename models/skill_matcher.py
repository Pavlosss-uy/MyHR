import torch
import torch.nn as nn
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer


class SkillMatchSiameseNet(nn.Module):
    """
    Siamese network for skill matching using frozen SentenceTransformer embeddings.

    The MLP projection layer was removed because it was never trained, meaning it
    mapped high-quality semantic embeddings into a random latent space and produced
    meaningless cosine similarity scores. The pretrained 'all-mpnet-base-v2' model
    already outputs L2-normalized 768-d vectors that work directly for semantic
    similarity — no additional projection is needed without a trained checkpoint.

    If you later train a fine-tuned projection head, re-add shared_mlp here and
    load its weights via the registry before calling calculate_match_score.
    """

    def __init__(self, embedding_model: str = "all-mpnet-base-v2"):
        super(SkillMatchSiameseNet, self).__init__()
        self.embedder = SentenceTransformer(embedding_model)
        for param in self.embedder.parameters():
            param.requires_grad = False

    def forward_once(self, text_input: str) -> torch.Tensor:
        with torch.no_grad():
            embeddings = self.embedder.encode(
                text_input, convert_to_tensor=True, normalize_embeddings=True
            )
        if embeddings.dim() == 1:
            embeddings = embeddings.unsqueeze(0)
        return embeddings

    def forward(self, cv_skills: str, jd_skills: str):
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