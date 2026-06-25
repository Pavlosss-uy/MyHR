"""
Cross-Encoder Answer Quality Scorer
=====================================
NOT PRODUCTION — retired from active architecture (audit Task 2.4).

Status: code preserved as reference; NOT wired into agent.py or registry.py.

Why retired:
  Fine-tuned on 160 samples (80/20 split of 200-sample eval_training_data.json).
  Measured performance on hold-out set (n=98):
    - Fine-tuned model:  Spearman ρ =  0.18, p = 0.069  (not significant)
    - Base model:        Spearman ρ = -0.15, p = 0.133  (not significant)
  Fine-tuning moved the needle by only +0.34 ρ points.  Both p-values exceed
  0.05, meaning neither result is statistically distinguishable from noise at
  the standard significance threshold.

Why this happens:
  Cross-encoders require substantially more fine-tuning data than bi-encoder
  MLPs because every weight update affects the shared attention layers used for
  both inputs.  160 samples is insufficient; the model overfits to the training
  set without generalising to the hold-out.

Reactivation criteria (all must be met before wiring into inference):
  1. Training set >= 1,000 labeled (question, answer, quality_score) samples.
  2. Spearman ρ >= 0.50 on a held-out test set.
  3. p-value < 0.01 on that test set.
  4. Score distribution shows meaningful spread (not collapsed to a narrow band).

Path to reactivation:
  - Run generate_eval_data.py to expand eval_training_data.json beyond 200 samples.
  - Set GENERATE_EXTRA_SAMPLES = True in train_cross_encoder.py to generate the
    additional 300 behavioural/off-topic/vague/concise samples (brings total to ~500).
  - Generate another 500+ via the same pipeline before retraining.
  - Re-evaluate with run_comparison_experiment() and check all three criteria above.

Architecture diagram note:
  This component is listed as INACTIVE in the architecture.  It must not be
  presented as a functioning scoring signal until the criteria above are met.

Fine-tuned cross-encoder that processes (question, answer) as a single input,
enabling deep cross-attention between all token pairs.

Unlike bi-encoder + MLP which computes embeddings independently, this model
jointly attends to Q and A tokens via transformer self-attention layers,
capturing token-level interactions.

Base model: cross-encoder/ms-marco-MiniLM-L-12-v2
"""

import os
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
            model_path: Path to fine-tuned model directory. If None, tries the
                        default checkpoint dir, then falls back to the base model.
            base_model: HuggingFace model name to use as the base. Defaults to
                        DEFAULT_BASE_MODEL (ms-marco-MiniLM-L-12-v2).
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
