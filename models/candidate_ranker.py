import torch
import torch.nn as nn
import torch.nn.functional as F

class NeuralCandidateRanker(nn.Module):
    def __init__(self, input_features=8, embedding_dim=32):
        super(NeuralCandidateRanker, self).__init__()
        
        # MLP to project candidate features into a comparable latent embedding space
        # We take the 8 core features of a candidate and map them to a 32-dimensional vector
        self.projector = nn.Sequential(
            nn.Linear(input_features, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, embedding_dim)
        )

    def forward(self, features):
        """Projects raw candidate features into a normalized dense embedding."""
        embeddings = self.projector(features)
        # Normalize so we can use cosine similarity for ranking
        return F.normalize(embeddings, p=2, dim=1)

    def rank_candidates(self, candidate_features_matrix, ideal_profile_features):
        """
        Ranks a batch of candidates against an ideal job profile.
        candidate_features_matrix: Tensor of shape (num_candidates, input_features)
        ideal_profile_features: Tensor of shape (1, input_features)
        """
        self.eval()
        with torch.no_grad():
            # Project all candidates and the ideal profile into the same mathematical space
            candidate_embeddings = self.forward(candidate_features_matrix)
            ideal_embedding = self.forward(ideal_profile_features)
            
            # Calculate how close each candidate is to the perfect ideal profile
            similarities = F.cosine_similarity(candidate_embeddings, ideal_embedding)
            
            # Sort them from best match to worst match
            scores, indices = torch.sort(similarities, descending=True)
            
        return scores.tolist(), indices.tolist()