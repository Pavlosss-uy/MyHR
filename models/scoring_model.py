import logging
import os
import threading
import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# --- 1. THE DEEP LEARNING ARCHITECTURE ---
class CandidateScoringMLP(nn.Module):
    def __init__(self, input_dim=1536): # 768(Q) + 768(A) — tone removed (was leaky proxy)
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
        logger.info("Loading Semantic Embedding Model for DL Scorer...")
        self.embedder = SentenceTransformer("all-mpnet-base-v2")
        self._cache: dict = {}  # Task 3.8 — in-process embedding cache
        self._cache_lock = threading.Lock()  # guards _cache against asyncio.to_thread races

    def _encode_cached(self, text: str) -> torch.Tensor:
        """Encode text, returning a cached tensor if the same text was seen before.

        Thread-safe: endpoints run this via asyncio.to_thread, so concurrent
        interviews could otherwise race on the unguarded dict.
        """
        with self._cache_lock:
            if text not in self._cache:
                with torch.no_grad():
                    self._cache[text] = self.embedder.encode(text, convert_to_tensor=True)
            return self._cache[text]

    def extract(self, question: str, answer: str, tone_data: dict = None) -> torch.Tensor:
        """Build the MOD-1 feature vector: concat(mpnet(question), mpnet(answer)).

        Tone features were REMOVED: in training they were derived from the quality
        tier (label leakage) and at inference they were a near-constant (0.8), so
        they made the model score noise. tone_data is accepted but ignored for
        backward compatibility with callers.
        """
        if not answer or answer.strip() == "(No speech detected)":
            return torch.zeros(1, 1536)

        q_emb = self._encode_cached(question)
        a_emb = self._encode_cached(answer)

        features = torch.cat([q_emb, a_emb], dim=0)
        return features.unsqueeze(0)


# --- 3. SHARED SINGLETON (P7) ---
# All modules should call get_shared_embedder() instead of creating their own
# SentenceTransformer instance. This saves ~420 MB RAM per extra instance.
_shared_embedding_extractor: "EmbeddingExtractor | None" = None

def get_shared_embedder() -> "EmbeddingExtractor":
    global _shared_embedding_extractor
    if _shared_embedding_extractor is None:
        _shared_embedding_extractor = EmbeddingExtractor()
    return _shared_embedding_extractor


# --- 4. INFERENCE PIPELINE ---
class ScoringPipeline:
    def __init__(self):
        self.model = CandidateScoringMLP(input_dim=1536)
        self.extractor = get_shared_embedder()

        checkpoint_path = os.path.join(os.path.dirname(__file__), 'checkpoints', 'scorer_v2.pt')
        if os.path.exists(checkpoint_path):
            self.model.load_state_dict(torch.load(checkpoint_path, weights_only=True))
            logger.info("[OK] True Deep Learning Scoring Model (v2) Loaded Successfully!")
        else:
            logger.warning("[WARN] No trained v2 model found. Using random weights.")

        self.model.eval()

    def predict_score(self, question: str, answer: str, tone_data: dict) -> int:
        with torch.no_grad():
            features = self.extractor.extract(question, answer, tone_data)
            score_tensor = self.model(features)
            score = int(score_tensor.item())
            return min(max(score, 0), 100)

# Lazy singleton — import this module without triggering model loading.
# Use ScoringPipeline() directly when you need the standalone pipeline.
_scorer_pipeline = None

def get_scorer_pipeline() -> "ScoringPipeline":
    global _scorer_pipeline
    if _scorer_pipeline is None:
        _scorer_pipeline = ScoringPipeline()
    return _scorer_pipeline
