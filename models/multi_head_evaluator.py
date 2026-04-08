import torch
import torch.nn as nn
import numpy as np


class MultiHeadEvaluator(nn.Module):
    def __init__(self, input_dim=768):
        super(MultiHeadEvaluator, self).__init__()

        # Shared Feature Backbone
        self.shared_backbone = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
        )

        # Head 1: Relevance Score
        self.relevance_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

        # Head 2: Clarity Score
        self.clarity_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

        # Head 3: Technical Depth Score
        self.depth_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        """Returns a dict with keys 'relevance', 'clarity', 'depth', each scaled 0-100."""
        shared_features = self.shared_backbone(x)

        relevance = self.relevance_head(shared_features) * 100
        clarity = self.clarity_head(shared_features) * 100
        depth = self.depth_head(shared_features) * 100

        return {"relevance": relevance, "clarity": clarity, "depth": depth}

    def evaluate_answer(self, features_tensor):
        """
        Helper function for inference during the interview.
        Returns a structured dictionary of scalar scores.
        """
        self.eval()
        with torch.no_grad():
            preds = self.forward(features_tensor)
            rel = preds["relevance"]
            clar = preds["clarity"]
            dep = preds["depth"]
            overall = (rel + clar + dep) / 3.0

        return {
            "relevance": round(rel.item(), 1),
            "clarity": round(clar.item(), 1),
            "technical_depth": round(dep.item(), 1),
            "overall": round(overall.item(), 1),
        }

    def predict_with_uncertainty(self, x, n_forward=10):
        """
        MC Dropout: run multiple forward passes with dropout enabled
        to estimate prediction uncertainty.
        """
        self.train()  # Enable dropout
        predictions = {k: [] for k in ["relevance", "clarity", "depth"]}

        with torch.no_grad():
            for _ in range(n_forward):
                preds = self.forward(x)
                for k in predictions:
                    predictions[k].append(preds[k].squeeze().cpu().numpy())

        means = {}
        stds = {}
        for k in predictions:
            stacked = np.stack(predictions[k], axis=0)
            means[k] = np.mean(stacked, axis=0)
            stds[k] = np.std(stacked, axis=0)

        self.eval()
        return means, stds