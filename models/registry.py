"""
Model Registry
===============
Centralized model loading and versioning for all ML models.
Handles checkpoint discovery, version management, and graceful fallbacks.
"""

import os
import torch
from pathlib import Path

# Base directory for all checkpoints
CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# Version registry — maps model name to latest version info
MODEL_VERSIONS = {
    "evaluator": {
        "latest": "v1",
        "checkpoint_pattern": "evaluator_{version}.pt",
    },
    "cross_encoder": {
        "latest": "v1",
        "checkpoint_pattern": "cross_encoder_scorer_{version}",  # directory
    },
    "emotion": {
        "latest": "v2",
        "checkpoint_pattern": "emotion_finetuned_{version}.pt",
    },
}


def get_checkpoint_path(model_name: str, version: str = None) -> str:
    """
    Get the full checkpoint path for a model.
    
    Args:
        model_name: One of 'evaluator', 'cross_encoder', 'emotion'
        version: Version string (e.g., 'v1'). If None, uses latest.
        
    Returns:
        Full path to checkpoint file or directory.
    """
    if model_name not in MODEL_VERSIONS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_VERSIONS.keys())}")

    info = MODEL_VERSIONS[model_name]
    ver = version or info["latest"]
    filename = info["checkpoint_pattern"].format(version=ver)
    return os.path.join(CHECKPOINT_DIR, filename)


def load_evaluator(version: str = None):
    """
    Load MultiHeadEvaluator from checkpoint.
    
    Args:
        version: Checkpoint version (default: latest)
        
    Returns:
        MultiHeadEvaluator instance (eval mode), or None if checkpoint missing.
    """
    from models.multi_head_evaluator import MultiHeadEvaluator

    checkpoint_path = get_checkpoint_path("evaluator", version)
    model = MultiHeadEvaluator()

    if Path(checkpoint_path).exists():
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
        print(f"✅ Loaded evaluator {version or MODEL_VERSIONS['evaluator']['latest']} from {checkpoint_path}")
        model.eval()
        return model
    else:
        print(f"⚠️  Evaluator checkpoint not found at {checkpoint_path}")
        print("   Run `python training/train_evaluator.py` to train the model.")
        return None


def load_cross_encoder(version: str = None):
    """
    Load InterviewCrossEncoderScorer from checkpoint.
    
    Args:
        version: Checkpoint version (default: latest)
        
    Returns:
        InterviewCrossEncoderScorer instance, or None if checkpoint missing.
    """
    from models.cross_encoder_scorer import InterviewCrossEncoderScorer

    checkpoint_path = get_checkpoint_path("cross_encoder", version)

    if Path(checkpoint_path).exists() and any(Path(checkpoint_path).iterdir()):
        scorer = InterviewCrossEncoderScorer(model_path=checkpoint_path)
        print(f"✅ Loaded cross-encoder {version or MODEL_VERSIONS['cross_encoder']['latest']}")
        return scorer
    else:
        print(f"⚠️  Cross-encoder checkpoint not found at {checkpoint_path}")
        print("   Run `python training/train_cross_encoder.py` to fine-tune the model.")
        return None


def load_emotion_model(version: str = None):
    """
    Load emotion classifier from checkpoint.
    
    Args:
        version: Checkpoint version (default: latest)
        
    Returns:
        dict with 'model' (nn.Module) and 'metadata' (dict), or None if missing.
    """
    checkpoint_path = get_checkpoint_path("emotion", version)

    if Path(checkpoint_path).exists():
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

        # Reconstruct model from saved architecture info
        from training.train_emotion import EmotionClassifier

        metadata = checkpoint.get("metadata", {})
        input_dim = metadata.get("input_dim", 162)
        num_classes = metadata.get("num_classes", 8)

        model = EmotionClassifier(input_dim=input_dim, num_classes=num_classes)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        print(f"✅ Loaded emotion model {version or MODEL_VERSIONS['emotion']['latest']}")
        print(f"   Classes: {metadata.get('emotion_labels', 'unknown')}")
        print(f"   Best val F1: {metadata.get('best_f1', 'N/A'):.4f}")
        return {"model": model, "metadata": metadata}
    else:
        print(f"⚠️  Emotion checkpoint not found at {checkpoint_path}")
        print("   Run `python training/train_emotion.py` to train the model.")
        return None


def list_available_checkpoints():
    """List all available model checkpoints."""
    print(f"\n📦 Model Checkpoints ({CHECKPOINT_DIR}):")
    print("=" * 60)

    for model_name, info in MODEL_VERSIONS.items():
        ver = info["latest"]
        path = get_checkpoint_path(model_name, ver)
        exists = Path(path).exists()
        status = "✅ Available" if exists else "❌ Not trained"
        print(f"  {model_name:15s} ({ver}): {status}")

    print()


if __name__ == "__main__":
    list_available_checkpoints()
