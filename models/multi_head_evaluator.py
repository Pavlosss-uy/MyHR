import torch
import torch.nn as nn

class MultiHeadEvaluator(nn.Module):
    def __init__(self, input_dim=8):
        super(MultiHeadEvaluator, self).__init__()
        
        # Shared Feature Backbone (Extracts general quality patterns from the 8 input features)
        self.shared_backbone = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        
        # Head 1: Relevance Score
        self.relevance_head = nn.Sequential(
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid() # Sigmoid forces the output to be between 0.0 and 1.0
        )
        
        # Head 2: Clarity Score
        self.clarity_head = nn.Sequential(
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )
        
        # Head 3: Technical Depth Score
        self.depth_head = nn.Sequential(
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        """Passes features through the backbone and splits them into the 3 heads."""
        shared_features = self.shared_backbone(x)
        
        # We multiply by 100 to convert the 0.0-1.0 Sigmoid output into a 0-100 score
        relevance = self.relevance_head(shared_features) * 100
        clarity = self.clarity_head(shared_features) * 100
        depth = self.depth_head(shared_features) * 100
        
        return relevance, clarity, depth

    def evaluate_answer(self, features_tensor):
        """
        Helper function for inference during the interview. 
        Returns a structured dictionary of scores.
        """
        self.eval()
        with torch.no_grad():
            rel, clar, dep = self.forward(features_tensor)
            
            # Calculate the overall score (we can weight this differently for specific jobs later)
            overall = (rel + clar + dep) / 3.0
            
        return {
            "relevance": round(rel.item(), 1),
            "clarity": round(clar.item(), 1),
            "technical_depth": round(dep.item(), 1),
            "overall": round(overall.item(), 1)
        }