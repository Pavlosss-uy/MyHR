"""
Multi-Head Evaluator Model
===========================
PyTorch MLP with 3 regression heads (relevance, clarity, technical_depth).
Supports MC Dropout for uncertainty estimation.

Input: 768-dim sentence embedding feature vector
Output: 3 scores in [0, 100]
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path


class MultiHeadEvaluator(nn.Module):
    """
    Multi-task evaluator with shared backbone and 3 independent regression heads.
    
    Architecture:
        Input (768) → Linear(256) → BN → ReLU → Dropout(0.3)
                     → Linear(128) → BN → ReLU → Dropout(0.3)
                     → 3 heads: Linear(128→64→1) each
    """

    def __init__(self, input_dim: int = 768, dropout: float = 0.3):
        super().__init__()
        self.input_dim = input_dim

        # Shared backbone
        self.backbone = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Head: Relevance (0-100)
        self.head_relevance = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

        # Head: Clarity (0-100)
        self.head_clarity = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

        # Head: Technical Depth (0-100)
        self.head_depth = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> dict:
        """
        Forward pass through shared backbone + 3 heads.
        
        Args:
            x: Tensor of shape (batch_size, input_dim)
            
        Returns:
            dict with keys 'relevance', 'clarity', 'depth', each (batch_size, 1)
        """
        shared = self.backbone(x)
        return {
            "relevance": self.head_relevance(shared),
            "clarity": self.head_clarity(shared),
            "depth": self.head_depth(shared),
        }

    def predict(self, x: torch.Tensor) -> dict:
        """
        Single forward pass, returns clamped scores in [0, 100].
        """
        self.eval()
        with torch.no_grad():
            preds = self.forward(x)
            return {
                "relevance": torch.clamp(preds["relevance"], 0, 100).squeeze(-1),
                "clarity": torch.clamp(preds["clarity"], 0, 100).squeeze(-1),
                "depth": torch.clamp(preds["depth"], 0, 100).squeeze(-1),
            }

    def predict_with_uncertainty(self, features: torch.Tensor, n_forward: int = 10) -> tuple:
        """
        MC Dropout uncertainty estimation.
        
        Runs n_forward stochastic forward passes with dropout ACTIVE,
        then computes mean and std of predictions.
        
        Args:
            features: Tensor of shape (batch_size, input_dim)
            n_forward: Number of stochastic forward passes
            
        Returns:
            (mean_predictions, std_predictions) — each is a dict with keys
            'relevance', 'clarity', 'depth', values are (batch_size,) tensors.
        """
        self.train()  # Keep dropout active for MC sampling

        all_preds = {"relevance": [], "clarity": [], "depth": []}

        with torch.no_grad():
            for _ in range(n_forward):
                preds = self.forward(features)
                for key in all_preds:
                    all_preds[key].append(
                        torch.clamp(preds[key].squeeze(-1), 0, 100)
                    )

        means = {}
        stds = {}
        for key in all_preds:
            stacked = torch.stack(all_preds[key], dim=0)  # (n_forward, batch)
            means[key] = stacked.mean(dim=0)
            stds[key] = stacked.std(dim=0)

        self.eval()
        return means, stds


def load_evaluator(checkpoint_path: str = None) -> MultiHeadEvaluator:
    """Load a MultiHeadEvaluator from checkpoint."""
    model = MultiHeadEvaluator()
    if checkpoint_path and Path(checkpoint_path).exists():
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
        print(f"✅ Loaded evaluator checkpoint from {checkpoint_path}")
    else:
        print("⚠️  No evaluator checkpoint found — using random initialized weights")
    model.eval()
    return model
