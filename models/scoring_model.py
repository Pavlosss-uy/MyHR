import os
import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer

# --- 1. THE DEEP LEARNING ARCHITECTURE ---
# RENAME: Changed from InterviewScorerMLP to CandidateScoringMLP to match your Registry
class CandidateScoringMLP(nn.Module):
    def __init__(self, input_dim=1538): # 768(Q) + 768(A) + 2(Tone)
        super(CandidateScoringMLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid() 
        )

    def forward(self, x):
        return self.network(x) * 100.0

# --- 2. PURE EMBEDDING EXTRACTOR ---
class EmbeddingExtractor:
    def __init__(self):
        print("[AI] Loading Semantic Embedding Model for DL Scorer...")
        self.embedder = SentenceTransformer("all-mpnet-base-v2")

    def extract(self, question: str, answer: str, tone_data: dict) -> torch.Tensor:
        if not answer or answer.strip() == "(No speech detected)":
            return torch.zeros(1, 1538)

        # 1. Convert words into raw semantic mathematics (768 dims each)
        with torch.no_grad():
            q_emb = self.embedder.encode(question, convert_to_tensor=True)
            a_emb = self.embedder.encode(answer, convert_to_tensor=True)
        
        # 2. Extract Tone Data 
        f_tone_conf = 0.8
        f_valence = 1.0 
        
        if tone_data and "primary_emotion" in tone_data:
            primary = tone_data["primary_emotion"].lower()
            if "processing" not in primary:
                f_valence = 1.0 if primary in ["happy", "neutral", "neu", "hap"] else 0.0

        tone_tensor = torch.tensor([f_tone_conf, f_valence], dtype=torch.float32).to(q_emb.device)
        
        # 3. Concatenate: 768 + 768 + 2 = 1538
        features = torch.cat([q_emb, a_emb, tone_tensor], dim=0)
        return features.unsqueeze(0) 

# --- 3. INFERENCE PIPELINE ---
class ScoringPipeline:
    def __init__(self):
        # FIX: Ensure this matches the renamed class above
        self.model = CandidateScoringMLP(input_dim=1538)
        self.extractor = EmbeddingExtractor()
        
        checkpoint_path = os.path.join(os.path.dirname(__file__), 'checkpoints', 'scorer_v2.pt')
        if os.path.exists(checkpoint_path):
            self.model.load_state_dict(torch.load(checkpoint_path, weights_only=True))
            print("[OK] True Deep Learning Scoring Model (v2) Loaded Successfully!")
        else:
            print("[WARN] No trained v2 model found. Using random weights.")
            
        self.model.eval()

    def predict_score(self, question: str, answer: str, tone_data: dict) -> int:
        with torch.no_grad():
            features = self.extractor.extract(question, answer, tone_data)
            score_tensor = self.model(features)
            score = int(score_tensor.item())
            return min(max(score, 0), 100) 

scorer = ScoringPipeline()