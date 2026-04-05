# MyHR — FINAL AI Enhancement Roadmap

---

## Context: Why This Plan Exists

MyHR is a graduation project with impressive architecture (8 PyTorch models, LangGraph, RL, Siamese networks) but **3 fatal execution failures** that undermine all the AI work:

1. **Every model trains on fake data** — the emotion model trains on silence, the scorer on random vectors
2. **Feature extraction is hardcoded** — `agent.py:157-166` feeds constants (0.7, 0.8, 0.6) to every neural model, making their outputs identical regardless of answer quality
3. **Multi-Head Evaluator has no training script** — runs with random weights

This plan fixes those failures first, then layers on contributions that go beyond the original MOD plan.

---

## PHASE 1: Foundation — Real Feature Extraction Pipeline

**Problem**: `agent.py:157-166` hardcodes 6 of 8 features. The MultiHeadEvaluator and PerformancePredictor receive the same input for every answer. Their outputs are decorative.

**Solution**: Build `models/feature_extractor.py` that computes all 8 features from actual Q&A text.

### Step 1.1 — Create `models/feature_extractor.py`

```
class AnswerFeatureExtractor:
    def __init__(self):
        self.embedder = SentenceTransformer("all-mpnet-base-v2")  # already loaded elsewhere, reuse
        self.nlp = spacy.load("en_core_web_sm")

    def extract(self, question, answer, jd_text, cv_text, tone_data, conversation_history) -> torch.Tensor:
        # Returns [8] tensor: all features 0.0-1.0 normalized
```

**The 8 features and how to compute each:**

| # | Feature | Method | Non-trivial Because |
|---|---------|--------|-------------------|
| 0 | **skill_match** | Call existing `SkillMatchSiameseNet.calculate_match_score(cv_text, jd_text)` from registry | Wires an existing model that currently isn't called |
| 1 | **relevance** | Cosine similarity between `embedder.encode(question)` and `embedder.encode(answer)` | Measures semantic alignment between Q and A |
| 2 | **clarity** | Composite: `0.4 * (1 - avg_sentence_length/50) + 0.3 * type_token_ratio + 0.3 * discourse_marker_ratio` — discourse markers = ["because", "therefore", "for example", "specifically", "however", "first", "second"] | Captures linguistic structure quality, not just content |
| 3 | **technical_depth** | Extract JD technical terms via TF-IDF (fit on general corpus, transform JD). Count how many appear in the answer. Normalize by total JD terms. | Measures domain-specific vocabulary match |
| 4 | **confidence** | From `tone_data.get("confidence", 0.5)` — but properly wired from Celery result, not default | Connects the async tone analysis that currently goes unused |
| 5 | **consistency** | If `len(conversation_history) >= 2`: cosine similarity between current answer embedding and mean of previous answer embeddings. Else: 0.7 | Tracks whether candidate maintains coherent narrative |
| 6 | **gaps_inverted** | Extract JD requirement keywords (nouns + noun chunks via spaCy). Check which ones appear across ALL answers so far. `coverage = found / total`. Return coverage. | Measures how thoroughly the candidate addresses JD |
| 7 | **experience** | Regex for year patterns (`\d+ years?`, `since 20\d{2}`), project mentions (`led`, `built`, `managed`, `developed`), and spaCy NER for ORG entities. Normalize count / 10, clamp to 1.0 | Extracts concrete experience signals from text |

### Step 1.2 — Wire into `agent.py:145-202`

Replace lines 157-166 in `evaluate_answer_node`:
```python
# BEFORE (hardcoded):
features = torch.tensor([[0.5, 0.7, 0.8, 0.6, 0.5, 0.9, 0.8, 0.7]])

# AFTER (real extraction):
from models.feature_extractor import extractor  # singleton instance
features = extractor.extract(
    question=state["last_question"],
    answer=state["last_answer"],
    jd_text=state["initial_job_context"]["jd_text"],
    cv_text=state.get("retrieved_context", ""),
    tone_data=tone_data,
    conversation_history=state.get("conversation_history", [])
)
```

### Step 1.3 — Wire Skill Matcher into the flow

In `server.py` `/start_interview` endpoint (after Pinecone ingestion), add:
```python
skill_matcher = registry.load_skill_matcher()
skill_score = skill_matcher.calculate_match_score(cv_text, jd)
initial_state["skill_match_score"] = skill_score
```

**Files to create**: `models/feature_extractor.py`
**Files to modify**: `agent.py` (lines 145-170), `server.py` (lines 62-78)
**Libraries to add**: `spacy`, download `en_core_web_sm`
**Difficulty**: Medium
**Expected output**: Different answers now produce measurably different feature vectors. Run 3 test answers (good/mediocre/bad) and verify features diverge.

---

## PHASE 2: Core AI Contributions

### Step 2.1 — Train Multi-Head Evaluator (Currently Has NO Training)

**Problem**: `MultiHeadEvaluator` in `models/multi_head_evaluator.py` has no training script. It runs with **random initialized weights** (`registry.py:100` catches the missing checkpoint silently).

**Create**: `training/train_evaluator.py`

**Training data strategy** — LLM-as-labeler (500+ samples):
```python
# Use Groq (already configured) to generate labeled training data
# For each (question, answer) pair, ask the LLM to rate:
#   - relevance (0-100)
#   - clarity (0-100)
#   - technical_depth (0-100)

prompt = """Rate this interview answer on three dimensions (0-100 each):
Question: {question}
Answer: {answer}
Return JSON: {{"relevance": int, "clarity": int, "technical_depth": int}}"""
```

**Data pipeline**:
1. Generate 200 Q&A pairs using Groq (vary quality: 50 excellent, 50 good, 50 mediocre, 50 poor)
2. Label each with the LLM judge → 200 labeled triples (relevance, clarity, depth)
3. Run each through the feature extractor (Phase 1) → 200 feature vectors
4. Train/val split: 160/40

**Training loop**:
```python
# Multi-task weighted loss
loss = (
    0.35 * F.mse_loss(pred_relevance, target_relevance) +
    0.30 * F.mse_loss(pred_clarity, target_clarity) +
    0.35 * F.mse_loss(pred_depth, target_depth)
)
optimizer = AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
scheduler = CosineAnnealingLR(optimizer, T_max=50)
```

**Add MC Dropout for uncertainty** (the model already has `Dropout(0.3)` in its backbone):
```python
def predict_with_uncertainty(self, features, n_forward=10):
    self.train()  # Keep dropout active
    predictions = [self.forward(features) for _ in range(n_forward)]
    mean = torch.stack(predictions).mean(dim=0)
    std = torch.stack(predictions).std(dim=0)
    return mean, std  # std = model's uncertainty
```

**Evaluation metrics**: Spearman rank correlation per head vs. LLM labels on validation set. Target: > 0.65.

**Files to create**: `training/train_evaluator.py`, `training/generate_eval_data.py`
**Files to modify**: `models/multi_head_evaluator.py` (add `predict_with_uncertainty`), `models/registry.py` (add evaluator checkpoint version)
**Difficulty**: Medium
**Checkpoint**: `models/checkpoints/evaluator_v1.pt`

---

### Step 2.2 — Fine-Tune Cross-Encoder for Answer Quality Scoring

**Problem**: The current `CandidateScoringMLP` concatenates bi-encoder embeddings (768+768+2=1538 dims) and feeds them to an MLP. This loses token-level interaction — the model can't see which specific words in the answer relate to which words in the question.

**Solution**: Fine-tune a cross-encoder that processes (question, answer) as a single input, enabling deep cross-attention between all token pairs.

**Why this is a real AI contribution**: A cross-encoder jointly attends to Q and A tokens via transformer self-attention layers. This captures interactions like "the question asked about 'distributed systems' and the answer mentioned 'microservices' and 'load balancing'" — something a bi-encoder+MLP cannot do because embeddings are computed independently.

**Create**: `models/cross_encoder_scorer.py`
```python
from sentence_transformers import CrossEncoder

class InterviewCrossEncoderScorer:
    def __init__(self, model_path=None):
        base = "cross-encoder/ms-marco-MiniLM-L-12-v2"  # already in project
        self.model = CrossEncoder(base, num_labels=1)  # regression
        if model_path:
            self.model.model.load_state_dict(torch.load(model_path))

    def predict_score(self, question: str, answer: str) -> float:
        # Returns 0-100 quality score
        score = self.model.predict([(question, answer)])[0]
        return float(np.clip(score * 100, 0, 100))
```

**Create**: `training/train_cross_encoder.py`

**Training data** (reuse from Step 2.1 + expand):
- 500+ (question, answer, quality_score) triples
- Generate via Groq: "Rate this answer 0-100 for overall quality"
- Include diversity: technical Q&A, behavioral Q&A, vague answers, off-topic answers

**Training**:
```python
from sentence_transformers import CrossEncoder, InputExample
from torch.utils.data import DataLoader

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2", num_labels=1)
train_examples = [InputExample(texts=[q, a], label=score/100.0) for q, a, score in data]
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

model.fit(
    train_dataloader=train_dataloader,
    epochs=5,
    warmup_steps=100,
    optimizer_params={'lr': 2e-5},
    output_path="models/checkpoints/cross_encoder_scorer_v1"
)
```

**Key experiment** — compare 3 approaches on held-out test set:
| Method | How | Metric |
|--------|-----|--------|
| Bi-encoder + MLP (current) | `CandidateScoringMLP` | Spearman ρ vs. LLM labels |
| Cross-encoder (fine-tuned) | New model | Spearman ρ vs. LLM labels |
| LLM-as-judge (baseline) | Direct Groq scoring | Spearman ρ vs. human labels (if available) |

This comparison table is **publishable methodology** and demonstrates you understand the trade-offs.

**Integration**: Add to `models/registry.py`, wire into `evaluate_answer_node` alongside or replacing the MLP scorer.

**Files to create**: `models/cross_encoder_scorer.py`, `training/train_cross_encoder.py`
**Libraries**: sentence-transformers (already installed)
**Difficulty**: Medium-Hard
**Checkpoint**: `models/checkpoints/cross_encoder_scorer_v1/`

---

### Step 2.3 — Train Emotion Model on Real Data (RAVDESS + CREMA-D)

**Problem**: The emotion model trains on 16 silent WAV files created by `create_dummy_data.py` (literally `np.zeros()`).

**Solution**: Use real speech emotion datasets. The `training/preprocessing.py` already has RAVDESS parsing code — just needs real data.

**Data acquisition**:
- **RAVDESS**: ~1,440 speech files, 8 emotions, freely downloadable from Zenodo
- **CREMA-D**: ~7,442 files, 6 emotions, freely downloadable from GitHub
- Combined after mapping to the 8-class taxonomy: ~5,000+ usable samples

**Steps**:
1. Download RAVDESS to `data/raw/RAVDESS/` (each actor in a subfolder)
2. Download CREMA-D to `data/raw/CREMA-D/`
3. Add CREMA-D parser to `training/preprocessing.py`:
```python
CREMA_EMOTION_MAP = {
    "ANG": "frustrated",
    "DIS": "frustrated",
    "FEA": "nervous",
    "HAP": "enthusiastic",
    "NEU": "neutral",
    "SAD": "hesitant"
}
```
4. Run `preprocessing.py` → generates `data/interview_emotions_train.csv`
5. Modify `training/train_emotion.py`:

**Training improvements**:
```python
# Add 5-fold cross-validation
from sklearn.model_selection import StratifiedKFold

kfold = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
for fold, (train_idx, val_idx) in enumerate(kfold.split(X, y)):
    # Train fold, compute metrics

# Add proper validation with metrics
from sklearn.metrics import classification_report, confusion_matrix
# After each epoch:
val_preds = []
val_labels = []
# ... collect predictions ...
print(classification_report(val_labels, val_preds, target_names=EMOTION_LABELS))
cm = confusion_matrix(val_labels, val_preds)
```

**Add learning rate scheduling + early stopping**:
```python
scheduler = ReduceLROnPlateau(optimizer, mode='min', patience=3, factor=0.5)
# Early stop if val_loss doesn't improve for 5 epochs
```

**Expected results**: Weighted F1 > 55-65% on 8 classes (state-of-art on RAVDESS alone is ~70-80% on the original 8 emotions).

**Report**: Save confusion matrix plot to `training/results/emotion_confusion_matrix.png`

**Files to modify**: `training/preprocessing.py` (add CREMA-D parser), `training/train_emotion.py` (add k-fold, metrics, scheduling)
**Files to create**: `training/results/` directory for plots
**Difficulty**: Hard (data download + processing is the bottleneck)
**Checkpoint**: `models/checkpoints/emotion_finetuned_v2.pt`

---

## PHASE 3: Training & Experimentation

### Step 3.1 — Add Proper Evaluation Metrics to ALL Training Scripts

Every training script needs these additions:

**For classification models** (emotion):
```python
from sklearn.metrics import classification_report, confusion_matrix, f1_score
# Per-class F1, weighted F1, confusion matrix
```

**For regression models** (scorer, predictor, evaluator):
```python
from scipy.stats import spearmanr, pearsonr
# Spearman rank correlation, Pearson correlation, MAE, RMSE
```

**For ranking models** (ranker):
```python
# NDCG@k, pairwise accuracy
```

**For RL** (difficulty engine):
```python
# Average reward per episode, score variance, % of scores in target zone (50-80)
```

**Add TensorBoard logging to all scripts**:
```python
from torch.utils.tensorboard import SummaryWriter
writer = SummaryWriter(f"training/runs/{model_name}")
writer.add_scalar("Loss/train", train_loss, epoch)
writer.add_scalar("Loss/val", val_loss, epoch)
writer.add_scalar("Metric/f1", f1, epoch)
```

**Create**: `training/metrics.py` — shared metrics utilities
**Modify**: All 6 `train_*.py` files
**Libraries to add**: `tensorboard`
**Difficulty**: Easy-Medium

---

### Step 3.2 — Improve Skill Matcher Training Data

**Problem**: Trains on 4 hardcoded CV/JD pairs repeated 160 times.

**Solution**: Generate 500+ realistic pairs using Groq:
```python
# training/generate_skill_data.py
prompt = """Generate a realistic CV skills section and a matching Job Description requirements section.
Vary the domain: {domain}
Return JSON: {{"cv_skills": "...", "jd_requirements": "...", "is_match": true/false}}"""

domains = ["Backend Python", "Frontend React", "Data Science", "DevOps", "Mobile",
           "Security", "ML Engineering", "Full Stack", "Game Dev", "Embedded Systems"]
```

Generate 250 matching pairs + 250 mismatched pairs. Train with contrastive loss as before.

**Files to create**: `training/generate_skill_data.py`
**Files to modify**: `training/train_skill_matcher.py` (load real data instead of DummySkillDataset)
**Difficulty**: Easy-Medium
**Checkpoint**: `models/checkpoints/skill_matcher_v2.pt`

---

### Step 3.3 — Proper RL Environment for Adaptive Difficulty (Gym + PPO)

**Problem**: Current simulation is trivial: `score = 65 + (skill - difficulty) * 15 + noise`. The RL agent learns a lookup table, not a policy.

**Solution**: Build a proper Gymnasium environment with realistic candidate dynamics.

**Create**: `training/interview_env.py`
```python
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class InterviewEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.action_space = spaces.Discrete(5)  # difficulty 1-5
        self.observation_space = spaces.Box(low=0, high=1, shape=(6,), dtype=np.float32)
        # State: [avg_score_norm, trend, current_diff_norm, engagement, topic_diversity, questions_remaining_norm]

    def reset(self, seed=None):
        self.candidate_skill = np.random.uniform(1, 5)  # latent skill
        self.engagement = 1.0  # decays over time
        self.fatigue = 0.0  # accumulates
        self.scores = []
        self.topics_seen = set()
        self.step_count = 0
        return self._get_obs(), {}

    def step(self, action):
        difficulty = action + 1  # 1-5

        # Candidate response model (non-trivial)
        skill_gap = self.candidate_skill - difficulty
        base_score = 65 + skill_gap * 12

        # Engagement decay (candidates get tired/bored)
        self.engagement = max(0.3, self.engagement - 0.05 - self.fatigue * 0.02)
        base_score *= self.engagement

        # Fatigue from consecutive hard questions
        if difficulty >= 4:
            self.fatigue = min(1.0, self.fatigue + 0.15)
        else:
            self.fatigue = max(0.0, self.fatigue - 0.05)

        # Noise
        score = np.clip(base_score + np.random.normal(0, 8), 0, 100)
        self.scores.append(score)
        self.step_count += 1

        # Multi-objective reward
        score_reward = -abs(score - 65) / 100  # keep scores near 65
        engagement_reward = (self.engagement - 0.5) * 0.3  # maintain engagement
        variety_bonus = 0.05 if difficulty not in [self.scores[-2] if len(self.scores) > 1 else -1] else 0

        reward = score_reward + engagement_reward + variety_bonus

        done = self.step_count >= 5
        return self._get_obs(), reward, done, False, {}
```

**Train with PPO** (stable-baselines3):
```python
from stable_baselines3 import PPO

env = InterviewEnv()
model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="training/runs/difficulty_ppo")
model.learn(total_timesteps=50_000)
```

**Key experiment — compare 3 approaches**:
| Method | Description | Metric: Score Variance | Metric: % in 50-80 zone |
|--------|-------------|----------------------|------------------------|
| Rule-based heuristic | if score>70: diff+1, if score<50: diff-1 | Baseline | Baseline |
| Current policy gradient | `training/train_difficulty.py` as-is | vs. baseline | vs. baseline |
| PPO (new) | Gym env + stable-baselines3 | vs. baseline | vs. baseline |

Run 500 simulated interviews per method, report mean and std.

**Files to create**: `training/interview_env.py`, `training/train_difficulty_ppo.py`
**Libraries to add**: `gymnasium`, `stable-baselines3`
**Difficulty**: Medium
**Checkpoint**: Convert PPO policy to match `AdaptiveDifficultyEngine` architecture, or wrap SB3 model in the engine class

---

## PHASE 4: Optimization & Enhancement

### Step 4.1 — Implement Hybrid Search (BM25 + Dense + RRF)

**Problem**: Your research document (Section 2.2) explicitly mandates hybrid search. Current implementation is dense-only + reranker. Missing BM25 and Reciprocal Rank Fusion.

**Modify**: `retriever.py`

```python
from rank_bm25 import BM25Okapi

class HybridRetriever:
    def __init__(self):
        self.bm25_corpus = []  # populated during ingestion
        self.bm25 = None

    def index_documents(self, documents: list[str]):
        tokenized = [doc.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized)
        self.bm25_corpus = documents

    def retrieve(self, session_id, query, top_k=20):
        # Stage 1a: Dense retrieval (existing)
        dense_nodes = vector_retriever.retrieve(query)  # top_k=20

        # Stage 1b: Sparse retrieval (new)
        bm25_scores = self.bm25.get_scores(query.lower().split())
        bm25_top = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k]

        # Stage 2: Reciprocal Rank Fusion
        k = 60  # smoothing constant
        fused_scores = {}
        for rank, node in enumerate(dense_nodes):
            fused_scores[node.text] = fused_scores.get(node.text, 0) + 1 / (k + rank)
        for rank, idx in enumerate(bm25_top):
            text = self.bm25_corpus[idx]
            fused_scores[text] = fused_scores.get(text, 0) + 1 / (k + rank)

        # Sort by fused score, take top 20
        fused_ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:20]

        # Stage 3: Cross-encoder rerank (existing) → top 3
        reranker = get_reranker()
        # ... rerank fused_ranked ...
        return top_3_results
```

**Also modify**: `ingest.py` — store raw document texts for BM25 indexing alongside Pinecone vectors.

**Files to modify**: `retriever.py`, `ingest.py`
**Libraries to add**: `rank_bm25`
**Difficulty**: Easy-Medium

---

### Step 4.2 — Model Compression for Wav2Vec2

**Problem**: Wav2Vec2 is the largest model (~360MB). Loading it for every tone analysis is memory-intensive.

**Steps**:
1. **Quantize to INT8**:
```python
import torch.quantization
model = InterviewEmotionModel()
model.eval()
quantized_model = torch.quantization.quantize_dynamic(
    model, {nn.Linear}, dtype=torch.qint8
)
# Save and benchmark
```

2. **Export to ONNX** for faster CPU inference:
```python
dummy_input = torch.randn(1, 16000 * 5)  # 5 seconds audio
torch.onnx.export(model, dummy_input, "models/checkpoints/emotion_model.onnx")
```

3. **Benchmark table**:
| Version | Size (MB) | Inference (ms) | F1 Score |
|---------|-----------|----------------|----------|
| Original FP32 | ~360 | X | Y |
| INT8 Quantized | ~90 | X | Y |
| ONNX Runtime | ~180 | X | Y |

**Files to create**: `training/benchmark_models.py`
**Libraries**: `onnxruntime` (optional)
**Difficulty**: Medium

---

## PHASE 5: Explainability & Analysis

### Step 5.1 — SHAP Analysis for Feature-Based Models

**Create**: `models/explainer.py`

```python
import shap
import numpy as np

class ModelExplainer:
    def __init__(self, model, feature_names):
        self.model = model
        self.feature_names = feature_names
        # ["skill_match", "relevance", "clarity", "depth",
        #  "confidence", "consistency", "gaps_inverted", "experience"]

    def explain_prediction(self, features_tensor, background_data):
        """Returns SHAP values showing which features drove the prediction."""

        def model_fn(x):
            with torch.no_grad():
                t = torch.tensor(x, dtype=torch.float32)
                # For MultiHeadEvaluator: return overall score
                r, c, d = self.model(t)
                return ((r + c + d) / 3.0).numpy()

        explainer = shap.KernelExplainer(model_fn, background_data)
        shap_values = explainer.shap_values(features_tensor.numpy())
        return shap_values

    def plot_waterfall(self, shap_values, features, save_path=None):
        """Generates a waterfall plot showing feature contributions."""
        shap.waterfall_plot(
            shap.Explanation(
                values=shap_values[0],
                base_values=50.0,  # baseline score
                feature_names=self.feature_names,
                data=features[0]
            )
        )
        if save_path:
            plt.savefig(save_path, bbox_inches='tight')
```

### Step 5.2 — Integrate Explainability into Streamlit Report

**Modify**: `app.py` — in the final report section, add:
```python
# After radar chart
st.subheader("Score Explanation")
fig = create_shap_waterfall(evaluation["shap_values"], evaluation["features"])
st.plotly_chart(fig)

# Show which features had the most positive/negative impact
st.caption("Green bars pushed the score UP. Red bars pushed it DOWN.")
```

**Modify**: `agent.py` `evaluate_answer_node` — compute SHAP values and include in report_entry:
```python
report_entry["feature_values"] = features.tolist()
report_entry["shap_values"] = explainer.explain_prediction(features, background).tolist()
```

**Files to create**: `models/explainer.py`
**Files to modify**: `agent.py` (add SHAP to evaluation), `app.py` (add visualizations)
**Libraries to add**: `shap`
**Difficulty**: Medium

---

### Step 5.3 — Fairness Audit

**Create**: `training/fairness_audit.py`

**Tests to implement**:
1. **Accent bias on emotion model**: Run RAVDESS audio from male vs. female actors. Compare per-group emotion distributions. If `P(nervous | female) >> P(nervous | male)`, flag bias.

2. **Skill matcher terminology bias**: Compare scores for:
   - "Python, Django, REST APIs" vs. "Completed Python bootcamp, built web apps"
   - Same skills, different phrasing (academic vs. self-taught)

3. **Counterfactual fairness**: Create 10 CVs. Swap names (John Smith → Aisha Mohammed) while keeping all skills identical. Run through full pipeline. If scores differ by > 5%, flag.

4. **Disparate impact (4/5ths rule)**: `pass_rate_minority / pass_rate_majority >= 0.8`

**Output**: `training/results/fairness_report.json` with per-test pass/fail and metrics.

**Difficulty**: Medium

---

## PHASE 6: Deployment & Integration

### Step 6.1 — Registry Updates

**Modify** `models/registry.py`:
- Add `load_cross_encoder_scorer()` method
- Add `load_feature_extractor()` method
- Update version dict:
```python
self.versions = {
    "scorer": "scorer_v2.pt",
    "cross_encoder": "cross_encoder_scorer_v1/",   # NEW
    "emotion": "emotion_finetuned_v2.pt",           # UPDATED
    "skill_matcher": "skill_matcher_v2.pt",          # UPDATED
    "evaluator": "evaluator_v1.pt",                  # NEW (was None)
    "difficulty": "difficulty_engine_v2.pt",          # UPDATED
    "ranker": "candidate_ranker_v1.pt",
    "predictor": "performance_predictor_v1.pt"
}
```

### Step 6.2 — Updated `agent.py` Evaluation Node

The refactored `evaluate_answer_node` will look like:
```python
def evaluate_answer_node(state: AgentState):
    # 1. Real feature extraction (Phase 1)
    features = extractor.extract(
        state["last_question"], state["last_answer"],
        state["initial_job_context"]["jd_text"],
        state.get("retrieved_context", ""),
        state.get("multimodal_analysis", {}),
        state.get("conversation_history", [])
    )

    # 2. Multi-Head Neural Evaluation (Phase 2.1 — now with trained weights)
    evaluator = registry.load_evaluator()
    neural_results = evaluator.evaluate_answer(features)

    # 3. Cross-Encoder Scoring (Phase 2.2 — new)
    cross_scorer = registry.load_cross_encoder_scorer()
    cross_score = cross_scorer.predict_score(state["last_question"], state["last_answer"])

    # 4. Performance Prediction
    predictor = registry.load_performance_predictor()
    job_prediction = predictor.predict_performance(features)

    # 5. Explainability (Phase 5)
    shap_values = explainer.explain_prediction(features, background_data)

    # 6. LLM feedback (unchanged)
    ...

    # 7. Combined report entry
    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": neural_results["overall"],
        "cross_encoder_score": cross_score,
        "detailed_scores": neural_results,
        "predicted_job_performance": job_prediction,
        "feature_values": features.squeeze().tolist(),
        "shap_values": shap_values.tolist(),
        "feedback": res.feedback
    }
```

### Step 6.3 — Updated Requirements

Add to `requirements.txt`:
```
spacy==3.7.4
rank-bm25==0.2.2
shap==0.45.0
gymnasium==0.29.1
stable-baselines3==2.3.0
tensorboard==2.16.2
```

---

## Verification Plan

| Phase | Test | Pass Criteria |
|-------|------|--------------|
| 1 | Feed 3 different answers (excellent, mediocre, terrible) to feature extractor | Features differ by > 0.2 on at least 5 of 8 dimensions |
| 2.1 | Train evaluator, predict on validation set | Spearman ρ > 0.6 per head vs. LLM labels |
| 2.2 | Fine-tune cross-encoder, compare to bi-encoder MLP | Cross-encoder Spearman ρ > bi-encoder by ≥ 0.05 |
| 2.3 | Train emotion model on RAVDESS+CREMA-D | Weighted F1 > 55% on held-out fold |
| 3.1 | Check TensorBoard for all training runs | Loss curves converge, no NaN |
| 3.3 | Compare PPO vs heuristic over 500 simulations | PPO achieves lower score variance |
| 4.1 | Run retrieval queries with and without BM25 | At least 1 query where BM25 finds relevant content dense missed |
| 5.1 | Generate SHAP plots for 5 test predictions | Plots are readable, features align with intuition |
| E2E | Run a full interview session | All components produce variable, meaningful outputs |

---

## Key Contributions Summary

| # | Contribution | What Makes It Non-Trivial |
|---|-------------|--------------------------|
| 1 | Custom NLP feature extraction pipeline (8 metrics) | Combines semantic similarity, lexical analysis, NER, TF-IDF — not just API calls |
| 2 | Fine-tuned cross-encoder for answer quality scoring | Modifies a pretrained model's architecture (regression head), trains on domain data, compares against baselines |
| 3 | Multi-task evaluator with MC Dropout uncertainty | Custom loss weighting, uncertainty quantification via stochastic forward passes |
| 4 | Speech emotion recognition on real data with k-fold CV | Full ML pipeline: data processing, class imbalance handling (Focal Loss), rigorous evaluation |
| 5 | Custom Gym environment + PPO for adaptive difficulty | Original environment design with engagement/fatigue dynamics, RL algorithm comparison |
| 6 | Hybrid retrieval (BM25 + Dense + RRF + Reranker) | Multi-stage information retrieval pipeline with fusion algorithm |
| 7 | SHAP explainability for scoring decisions | Model-agnostic interpretability applied to HR decision-making |
| 8 | Fairness audit with counterfactual testing | Ethical AI applied to hiring — accent bias, terminology bias, disparate impact |

---

## CV / Interview Positioning Tips

### How to Describe the Project (1 line)
> "Built an AI interview platform with 8 custom PyTorch models, including a fine-tuned cross-encoder for answer scoring, RL-based adaptive difficulty, and SHAP-based explainable evaluation."

### Key Bullets for CV
- Designed and trained a **multi-task neural evaluator** with MC Dropout uncertainty estimation for interview answer assessment across 3 quality dimensions
- **Fine-tuned a cross-encoder** (MiniLM-L-12) for domain-specific answer quality regression, achieving X% improvement in Spearman correlation vs. bi-encoder baseline
- Built a **custom Gymnasium RL environment** modeling candidate engagement dynamics; trained PPO agent achieving X% lower score variance than rule-based baselines
- Implemented **SHAP-based explainability** and **fairness auditing** (disparate impact analysis, counterfactual testing) for responsible AI in hiring
- Engineered a **multi-stage hybrid retrieval pipeline** (BM25 + dense + RRF + cross-encoder reranking) for context-aware question generation
- Trained **speech emotion recognition** on RAVDESS + CREMA-D (5,000+ samples) with Focal Loss and 5-fold cross-validation, achieving X% weighted F1

### Interview Talking Points

**"What was your biggest technical challenge?"**
> "The hardest part was making the evaluation pipeline actually meaningful. I discovered that hardcoded feature proxies made all neural model outputs identical. I built a custom NLP feature extractor computing 8 metrics from raw text — semantic similarity, lexical clarity, domain-term coverage — which finally gave the neural evaluator real signal to learn from."

**"What's your most impressive ML contribution?"**
> "I fine-tuned a cross-encoder for interview answer quality scoring. Unlike bi-encoders that embed Q and A independently, the cross-encoder's self-attention sees all token pairs simultaneously. I ran a controlled experiment comparing it against the bi-encoder+MLP baseline and LLM-as-judge, measuring Spearman rank correlation. The cross-encoder outperformed because it captures token-level interactions like 'the question asked about distributed systems and the answer referenced microservices.'"

**"How did you ensure fairness?"**
> "I implemented counterfactual fairness testing — swapping candidate names and demographics while keeping skills identical, then measuring score variance. I also tested the emotion model for accent bias across RAVDESS speakers and computed disparate impact ratios using the 4/5ths rule."

**"What would you do differently?"**
> "I'd collect real interview data earlier. We generated training data using LLM-as-labeler, which works but introduces the LLM's biases. With real human-labeled data, the models would be more robust. I'd also add online learning — updating models from actual interview sessions over time."
