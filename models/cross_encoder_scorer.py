"""
Cross-Encoder Answer Quality Scorer
=====================================
Fine-tuned cross-encoder that processes (question, answer) as a single input,
enabling deep cross-attention between all token pairs.

Unlike bi-encoder + MLP which computes embeddings independently, this model
jointly attends to Q and A tokens via transformer self-attention layers,
capturing token-level interactions.

Base model: cross-encoder/ms-marco-MiniLM-L-12-v2
"""

import os
import torch
import numpy as np
from pathlib import Path
from sentence_transformers import CrossEncoder


class InterviewCrossEncoderScorer:
    """
    Cross-encoder for interview answer quality scoring.
    
    Processes (question, answer) pairs through a shared transformer encoder,
    producing a single quality score (0-100).
    """

    DEFAULT_BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    CHECKPOINT_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "checkpoints",
        "cross_encoder_scorer_v1",
    )

    def __init__(self, model_path: str = None, base_model: str = None):
        """
        Initialize the cross-encoder scorer.
        
        Args:
            model_path: Path to fine-tuned model directory. If None, tries
                        default checkpoint, then falls back to base model.
            base_model: Base model name (default: ms-marco-MiniLM-L-12-v2)
        """
        base = base_model or self.DEFAULT_BASE_MODEL

        # Determine which model to load
        load_path = model_path or self.CHECKPOINT_DIR

        if Path(load_path).exists() and any(Path(load_path).iterdir()):
            print(f"✅ Loading fine-tuned cross-encoder from {load_path}")
            self.model = CrossEncoder(load_path, num_labels=1)
            self.is_finetuned = True
        else:
            print(f"⚠️  No fine-tuned checkpoint found. Loading base model: {base}")
            self.model = CrossEncoder(base, num_labels=1)
            self.is_finetuned = False

    def predict_score(self, question: str, answer: str) -> float:
        """
        Predict answer quality score for a single (question, answer) pair.
        
        Args:
            question: Interview question text
            answer: Candidate's answer text
            
        Returns:
            Quality score in [0, 100]
        """
        score = self.model.predict([(question, answer)])[0]
        return float(np.clip(score * 100, 0, 100))

    def predict_scores_batch(self, pairs: list) -> list:
        """
        Predict quality scores for a batch of (question, answer) pairs.
        
        Args:
            pairs: List of (question, answer) tuples
            
        Returns:
            List of quality scores in [0, 100]
        """
        raw_scores = self.model.predict(pairs)
        return [float(np.clip(s * 100, 0, 100)) for s in raw_scores]

    def save(self, output_path: str = None):
        """Save the model to disk."""
        save_path = output_path or self.CHECKPOINT_DIR
        os.makedirs(save_path, exist_ok=True)
        self.model.save(save_path)
        print(f"✅ Cross-encoder saved to {save_path}")
