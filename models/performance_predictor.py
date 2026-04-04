import torch
import torch.nn as nn

class PerformancePredictor(nn.Module):
    def __init__(self, input_dim=8):
        super(PerformancePredictor, self).__init__()
        
        # A deep MLP to capture complex non-linear relationships between interview scores
        # and actual on-the-job performance.
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.LayerNorm(32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1) # Outputs a single continuous value
        )

    def forward(self, features):
        """
        Passes candidate features through the network.
        We use a Sigmoid at the end to bound the output between 0 and 1,
        and then multiply by 9 and add 1 to scale it exactly from 1.0 to 10.0.
        """
        raw_output = self.network(features)
        
        # Scale output strictly to a 1.0 - 10.0 range
        scaled_output = (torch.sigmoid(raw_output) * 9.0) + 1.0
        return scaled_output

    def predict_performance(self, candidate_features):
        """Helper function for inference during the final report generation."""
        self.eval()
        with torch.no_grad():
            prediction = self.forward(candidate_features)
            
        return round(prediction.item(), 1)