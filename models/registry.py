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
from models.cross_encoder_scorer import InterviewCrossEncoderScorer

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
            "scorer": "scorer_v1.pt", # Or v2 depending on your latest
            "emotion": "emotion_finetuned_v2.pt",
            "skill_matcher": "skill_matcher_v1.pt",
            "evaluator": "evaluator_v1.pt", # Evaluator shares the scorer backbone (MOD-4)
            "difficulty": "difficulty_engine_v1.pt",
            "ranker": "candidate_ranker_v1.pt",
            "predictor": "performance_predictor_v1.pt",
            "cross_encoder": "cross_encoder_scorer_v1"
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

    def load_difficulty_engine(self):
        if "difficulty" not in self.loaded_models:
            print("Loading Difficulty Engine...")
            model = AdaptiveDifficultyEngine().to(self.device)
            model.load_state_dict(torch.load(self._get_path("difficulty"), map_location=self.device))
            model.eval()
            self.loaded_models["difficulty"] = model
        return self.loaded_models["difficulty"]

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
            model = MultiHeadEvaluator(input_dim=768).to(self.device)
            
            # If you saved a specific checkpoint for it, load it. 
            # Otherwise, it will safely initialize with default weights.
            try:
                model.load_state_dict(torch.load(self._get_path("evaluator"), map_location=self.device))
            except Exception as e:
                print("No weights found for evaluator, using base initialized weights.")
                
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

    def load_cross_encoder(self):
        if "cross_encoder" not in self.loaded_models:
            print("Loading Cross-Encoder Scorer...")
            model_path = self._get_path("cross_encoder")
            try:
                # The InterviewCrossEncoderScorer handles loading the directory
                model = InterviewCrossEncoderScorer(model_name_or_path=model_path)
            except Exception as e:
                print(f"Failed to load cross-encoder from path {model_path}, falling back to base. Error: {e}")
                model = InterviewCrossEncoderScorer()
            self.loaded_models["cross_encoder"] = model
        return self.loaded_models["cross_encoder"]

# Create a global singleton instance to be imported across the app
registry = ModelRegistry()