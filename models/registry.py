import importlib
import logging
import os
import sys
import torch

logger = logging.getLogger(__name__)

# Check once at import time whether stable_baselines3 is available
_ppo_available = importlib.util.find_spec("stable_baselines3") is not None

# --- BULLETPROOF PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.scoring_model import CandidateScoringMLP
from models.emotion_model import InterviewEmotionModel
from models.skill_matcher import SkillMatchSiameseNet
from models.multi_head_evaluator import MultiHeadEvaluator
from models.difficulty_engine import AdaptiveDifficultyEngine
from models.performance_predictor import PerformancePredictor
from models.candidate_ranker import NeuralCandidateRanker


class ModelRegistry:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.base_path = "models/checkpoints"
        # Centralized version control
        self.versions = {
            "scorer": "scorer_v2.pt",           # v2: trained with SentenceTransformer embeddings
            "emotion": "emotion_finetuned_v2.pt",
            "skill_matcher": "skill_matcher_v1.pt",  # v1: available checkpoint
            "evaluator": "evaluator_v1.pt",
            "difficulty": "difficulty_engine_v1.pt",  # v1: 3-D state (avg_score, trend, diff)
            "difficulty_ppo": "difficulty_ppo_v1.zip",
            "ranker": "candidate_ranker_v1.pt",
            "predictor": "performance_predictor_v1.pt"
        }

        # Cache to keep models loaded in memory so we don't reload them on every request
        # None means "failed to load" — callers must guard before use
        self.loaded_models: dict = {}

    def _get_path(self, model_name: str) -> str:
        filename = self.versions.get(model_name)
        if not filename:
            raise ValueError(f"Model '{model_name}' not found in registry versions.")
        return os.path.join(self.base_path, filename)

    def _load_state(self, model, model_name: str) -> bool:
        """Load checkpoint into model in-place. Returns True on success."""
        path = self._get_path(model_name)
        if not os.path.exists(path):
            logger.warning("Registry: checkpoint not found — %s", path)
            return False
        try:
            state = torch.load(path, map_location=self.device, weights_only=True)
            model.load_state_dict(state)
            return True
        except Exception as e:
            logger.warning("Registry: could not load '%s' checkpoint (%s)", model_name, e)
            return False

    # ------------------------------------------------------------------
    # Loaders — every method returns either a ready model or None.
    # Callers must check for None before calling model methods.
    # ------------------------------------------------------------------

    def load_emotion_model(self):
        """Returns InterviewEmotionModel or None if checkpoint missing/corrupt."""
        if "emotion" not in self.loaded_models:
            model = InterviewEmotionModel().to(self.device)
            if self._load_state(model, "emotion"):
                logger.info("[OK]   Emotion model loaded.")
            else:
                logger.warning("[WARN] Emotion model unavailable — using HuggingFace pretrained backbone only.")
            model.eval()
            self.loaded_models["emotion"] = model
        return self.loaded_models["emotion"]

    def load_skill_matcher(self):
        """Returns SkillMatchSiameseNet (always — falls back to pretrained embeddings)."""
        if "skill_matcher" not in self.loaded_models:
            # Checkpoint v1 was trained with a 64-D projection head.
            model = SkillMatchSiameseNet(projection_dim=64)
            path = self._get_path("skill_matcher")
            if os.path.exists(path):
                try:
                    model.load_state_dict(
                        torch.load(path, map_location=self.device, weights_only=True),
                        strict=False,
                    )
                    logger.info("[OK]   Skill matcher checkpoint loaded.")
                except Exception as e:
                    logger.warning("Skill matcher checkpoint skipped (%s). Using pretrained embeddings.", e)
            else:
                logger.warning("[WARN] Skill matcher checkpoint missing — using pretrained SentenceTransformer embeddings.")
            model.eval()
            self.loaded_models["skill_matcher"] = model
        return self.loaded_models["skill_matcher"]

    def load_difficulty_engine(self, use_ppo: bool = False):
        """Returns AdaptiveDifficultyEngine or freshly-initialised fallback (never None)."""
        if use_ppo:
            return self.load_difficulty_ppo()

        if "difficulty" not in self.loaded_models:
            model = AdaptiveDifficultyEngine(state_dim=3).to(self.device)
            if self._load_state(model, "difficulty"):
                logger.info("[OK]   Difficulty engine loaded.")
            else:
                logger.warning("[WARN] Difficulty engine using random-init weights — difficulty adaptation disabled.")
            model.eval()
            self.loaded_models["difficulty"] = model
        return self.loaded_models["difficulty"]

    def load_difficulty_ppo(self):
        """Returns PPO model, or falls back to REINFORCE if sb3 unavailable."""
        if not _ppo_available:
            return self.load_difficulty_engine(use_ppo=False)

        if "difficulty_ppo" not in self.loaded_models:
            try:
                from stable_baselines3 import PPO
                ppo_path = os.path.join(self.base_path, self.versions["difficulty_ppo"])
                model = PPO.load(ppo_path, device=self.device)
                logger.info("[OK]   PPO difficulty engine loaded.")
                self.loaded_models["difficulty_ppo"] = model
            except Exception as e:
                logger.warning("PPO difficulty engine failed (%s), falling back to REINFORCE.", e)
                return self.load_difficulty_engine(use_ppo=False)
        return self.loaded_models["difficulty_ppo"]

    def load_scorer(self):
        """Returns CandidateScoringMLP or None if checkpoint missing/corrupt."""
        if "scorer" not in self.loaded_models:
            model = CandidateScoringMLP().to(self.device)
            if self._load_state(model, "scorer"):
                logger.info("[OK]   Candidate scorer (MOD-1) loaded.")
                model.eval()
                self.loaded_models["scorer"] = model
            else:
                logger.warning("[WARN] Candidate scorer unavailable — MOD-1 signal will be omitted.")
                self.loaded_models["scorer"] = None
        return self.loaded_models["scorer"]

    def load_evaluator(self):
        """Returns MultiHeadEvaluator (always — falls back to random-init weights)."""
        if "evaluator" not in self.loaded_models:
            logger.info("Loading Multi-Head Evaluator...")
            # input_dim=768: receives all-mpnet-base-v2 answer embedding, not the 8-D feature vector
            model = MultiHeadEvaluator(input_dim=768).to(self.device)

            try:
                checkpoint = torch.load(self._get_path("evaluator"), map_location=self.device, weights_only=True)
                # Guard against checkpoints trained with a different input_dim
                saved_dim = checkpoint.get("input_dim") if isinstance(checkpoint, dict) else None
                if saved_dim is not None and saved_dim != 768:
                    raise ValueError(
                        f"Checkpoint input_dim={saved_dim} does not match model input_dim=768. "
                        "Retrain the evaluator with the corrected 768-D pipeline."
                    )
                # Guard against the MiniLM/mpnet mix-up: inference feeds
                # all-mpnet-base-v2(answer), so the checkpoint must have been
                # trained on the same embedder. Legacy raw state_dicts have no
                # tag — warn loudly so the mismatch is visible.
                embedder = checkpoint.get("embedder") if isinstance(checkpoint, dict) else None
                if embedder is None:
                    logger.warning(
                        "[WARN] Evaluator checkpoint has no embedder tag — it may predate the "
                        "mpnet alignment fix. Retrain via training/train_evaluator.py."
                    )
                elif embedder != "all-mpnet-base-v2":
                    raise ValueError(
                        f"Checkpoint embedder='{embedder}' != inference embedder 'all-mpnet-base-v2'. "
                        "Retrain the evaluator so training matches inference."
                    )
                state_dict = checkpoint.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
                model.load_state_dict(state_dict)
                logger.info("[OK]   Evaluator checkpoint loaded (input_dim=768, embedder=all-mpnet-base-v2).")
            except Exception as e:
                logger.warning("No weights found for evaluator (%s), using randomly initialised weights.", e)
            model.eval()
            self.loaded_models["evaluator"] = model
        return self.loaded_models["evaluator"]

    def load_performance_predictor(self):
        """Returns PerformancePredictor or None if checkpoint missing/corrupt."""
        if "predictor" not in self.loaded_models:
            model = PerformancePredictor(input_dim=8).to(self.device)
            if self._load_state(model, "predictor"):
                logger.info("[OK]   Performance predictor (MOD-6) loaded.")
                model.eval()
                self.loaded_models["predictor"] = model
            else:
                logger.warning("[WARN] Performance predictor checkpoint not found — omitting performance forecast from report.")
                self.loaded_models["predictor"] = None
        return self.loaded_models["predictor"]

    def load_candidate_ranker(self):
        """Returns NeuralCandidateRanker (always — falls back to random projections)."""
        if "ranker" not in self.loaded_models:
            model = NeuralCandidateRanker(input_features=7, embedding_dim=32).to(self.device)
            path = self._get_path("ranker")
            if os.path.exists(path):
                try:
                    model.load_state_dict(
                        torch.load(path, map_location=self.device, weights_only=True)
                    )
                    logger.info("[OK]   Candidate ranker loaded.")
                except Exception as e:
                    logger.warning("Candidate ranker checkpoint skipped (%s). Rankings use random projections.", e)
            else:
                logger.warning("[WARN] Candidate ranker checkpoint missing — train with training/train_ranker.py.")
            model.eval()
            self.loaded_models["ranker"] = model
        return self.loaded_models["ranker"]

    def health_check(self) -> dict[str, str]:
        """
        Log and return the load status of every registered model.
        Call after startup to know the system's actual operating mode.
        """
        results = {}
        checkpoints = {
            "scorer":        self.versions["scorer"],
            "emotion":       self.versions["emotion"],
            "skill_matcher": self.versions["skill_matcher"],
            "evaluator":     self.versions["evaluator"],
            "difficulty":    self.versions["difficulty"],
            "ranker":        self.versions["ranker"],
            "predictor":     self.versions["predictor"],
        }
        logger.info("=" * 55)
        logger.info("  ModelRegistry — Startup Health Check")
        logger.info("=" * 55)
        for name, filename in checkpoints.items():
            path = os.path.join(self.base_path, filename)
            if name in self.loaded_models:
                status = "loaded" if self.loaded_models[name] is not None else "UNAVAILABLE"
            elif os.path.exists(path):
                status = "checkpoint present (not yet loaded)"
            else:
                status = "MISSING checkpoint"
            tag = "[OK]  " if status == "loaded" or "present" in status else "[WARN]"
            logger.info("  %s %-16s %s", tag, name, status)
            results[name] = status
        logger.info("=" * 55)
        return results


# Global singleton
registry = ModelRegistry()
registry.health_check()
