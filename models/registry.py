import os
import sys
import torch

# --- BULLETPROOF PATH FIX ---
# This finds the 'MyHR' folder and tells Python to look there for modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now standard imports will work
from models.scoring_model import CandidateScoringMLP
from models.emotion_model import InterviewEmotionModel
from models.skill_matcher import SkillMatchSiameseNet
from models.multi_head_evaluator import MultiHeadEvaluator
from models.difficulty_engine import AdaptiveDifficultyEngine
from models.performance_predictor import PerformancePredictor

# Import from the recommender folder
try:
    from recommender.candidate_ranker import NeuralCandidateRanker
except ModuleNotFoundError:
    # Backup in case the file was moved to models
    from models.candidate_ranker import NeuralCandidateRanker


class ModelRegistry:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.base_path = "models/checkpoints"
        
        # Centralized version control
        self.versions = {
            "scorer": "scorer_v2.pt",           # v2: trained with SentenceTransformer embeddings
            "emotion": "emotion_finetuned_v1.pt",
            "skill_matcher": "skill_matcher_v2.pt",  # v2: trained on SO 2018 survey data
            "evaluator": "evaluator_v1.pt",
            "difficulty": "difficulty_engine_v2.pt",  # v2: 6-D state
            "difficulty_ppo": "difficulty_ppo_v1.zip",
            "ranker": "candidate_ranker_v1.pt",
            "predictor": "performance_predictor_v1.pt"
        }
        
        # Cache to keep models loaded in memory so we don't reload them on every request
        self.loaded_models = {}

    def _get_path(self, model_name):
        filename = self.versions.get(model_name)
        if not filename:
            raise ValueError(f"Model {model_name} not found in registry versions.")
        return os.path.join(self.base_path, filename)

    def load_emotion_model(self):
        if "emotion" not in self.loaded_models:
            print("Loading Emotion Model...")
            model = InterviewEmotionModel().to(self.device)
            model.load_state_dict(torch.load(self._get_path("emotion"), map_location=self.device))
            model.eval()
            self.loaded_models["emotion"] = model
        return self.loaded_models["emotion"]

    def load_skill_matcher(self):
        if "skill_matcher" not in self.loaded_models:
            print("Loading Skill Matcher...")
            model = SkillMatchSiameseNet().to(self.device)
            model.load_state_dict(torch.load(self._get_path("skill_matcher"), map_location=self.device))
            model.eval()
            self.loaded_models["skill_matcher"] = model
        return self.loaded_models["skill_matcher"]

    def load_difficulty_engine(self, use_ppo: bool = False):
        """Load difficulty engine.

        Args:
            use_ppo: If True, load the PPO model (78.6% in-zone).
                     If False, load REINFORCE v2 6-D (70.8% in-zone).
                     Defaults to False for compatibility; set True in production.
        """
        if use_ppo:
            return self.load_difficulty_ppo()

        if "difficulty" not in self.loaded_models:
            print("Loading Difficulty Engine (REINFORCE 6-D)...")
            model = AdaptiveDifficultyEngine(state_dim=6).to(self.device)
            model.load_state_dict(
                torch.load(self._get_path("difficulty"), map_location=self.device)
            )
            model.eval()
            self.loaded_models["difficulty"] = model
        return self.loaded_models["difficulty"]

    def load_difficulty_ppo(self):
        """Load the PPO difficulty engine (best performer: 78.6% in-zone)."""
        if "difficulty_ppo" not in self.loaded_models:
            print("Loading PPO Difficulty Engine...")
            try:
                from stable_baselines3 import PPO
                ppo_path = os.path.join(self.base_path, self.versions["difficulty_ppo"])
                model = PPO.load(ppo_path, device=self.device)
                self.loaded_models["difficulty_ppo"] = model
            except Exception as e:
                print(f"Could not load PPO model ({e}), falling back to REINFORCE.")
                return self.load_difficulty_engine(use_ppo=False)
        return self.loaded_models["difficulty_ppo"]

    def load_scorer(self):
        """Load CandidateScoringMLP (scorer_v2: SentenceTransformer-based)."""
        if "scorer" not in self.loaded_models:
            print("Loading Candidate Scorer (v2)...")
            model = CandidateScoringMLP().to(self.device)
            model.load_state_dict(
                torch.load(self._get_path("scorer"), map_location=self.device)
            )
            model.eval()
            self.loaded_models["scorer"] = model
        return self.loaded_models["scorer"]

    def load_candidate_ranker(self):
        if "ranker" not in self.loaded_models:
            print("Loading Candidate Ranker...")
            model = NeuralCandidateRanker(input_features=8, embedding_dim=32).to(self.device)
            model.load_state_dict(torch.load(self._get_path("ranker"), map_location=self.device))
            model.eval()
            self.loaded_models["ranker"] = model
        return self.loaded_models["ranker"]
        
    def load_evaluator(self):
        if "evaluator" not in self.loaded_models:
            print("Loading Multi-Head Evaluator...")
            # Initialize the Multi-Head Evaluator (MOD-4)
            # input_dim=768: evaluator trained on SentenceTransformer (all-MiniLM-L6-v2) embeddings
            model = MultiHeadEvaluator(input_dim=768).to(self.device)

            # If you saved a specific checkpoint for it, load it.
            # Otherwise, it will safely initialize with default weights.
            try:
                model.load_state_dict(torch.load(self._get_path("evaluator"), map_location=self.device))
            except Exception as e:
                print(f"No weights found for evaluator ({e}), using base initialized weights.")
                
            model.eval()
            self.loaded_models["evaluator"] = model
        return self.loaded_models["evaluator"]

    def load_performance_predictor(self):
        if "predictor" not in self.loaded_models:
            print("Loading Performance Predictor...")
            model = PerformancePredictor(input_dim=8).to(self.device)
            model.load_state_dict(torch.load(self._get_path("predictor"), map_location=self.device))
            model.eval()
            self.loaded_models["predictor"] = model
        return self.loaded_models["predictor"]

# Create a global singleton instance to be imported across the app
registry = ModelRegistry()