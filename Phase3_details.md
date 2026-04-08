# Phase 3 Implementation Plan — MyHR AI Enhancement

## Context

Phase 3 is "Training & Experimentation." It builds on Phase 1 (real feature extraction) and Phase 2 (new models). Its purpose is to make every training script production-quality: proper metrics, real training data, and a rigorous RL environment. Without Phase 3, all trained models produce outputs that cannot be evaluated, compared, or trusted.

Phase 3 has 3 steps:
- **3.1** — Add proper evaluation metrics + TensorBoard to ALL 6 training scripts
- **3.2** — Replace DummySkillDataset (160 hardcoded samples) with 500+ Groq-generated pairs
- **3.3** — Replace trivial RL simulation with a proper Gymnasium environment + PPO (stable-baselines3)

---

## Current State (From Codebase Exploration)

### What Exists
| File | Status |
|------|--------|
| `training/train_emotion.py` | Exists — FocalLoss, 10 epochs, prints loss+acc, NO TensorBoard, NO per-class metrics |
| `training/train_skill_matcher.py` | Exists — DummySkillDataset (160 samples), prints contrastive loss only |
| `training/train_difficulty.py` | Exists — Policy Gradient (REINFORCE), custom simulation, 3D state, NOT Gym |
| `training/train_predictor.py` | Exists — DummyPerformanceDataset (1000 samples), MSE only |
| `training/train_ranker.py` | Exists — DummyRankingDataset (300 samples), ranking loss only |
| `training/train_scorer.py` | Exists — Synthetic embeddings (2500 samples), MSE only |
| `training/metrics.py` | MISSING |
| `training/interview_env.py` | MISSING |
| `training/train_difficulty_ppo.py` | MISSING |
| `training/generate_skill_data.py` | MISSING |
| `training/generate_eval_data.py` | MISSING |
| `training/train_evaluator.py` | MISSING (Phase 2.1 creates this — Phase 3.1 must add metrics to it) |

### Critical Issues Found
1. **No TensorBoard anywhere** — all 6 scripts use print-only logging
2. **No shared metrics utilities** — each script rolls its own (or nothing)
3. **Skill matcher uses fake data** — DummySkillDataset, 160 hardcoded pairs, no real variation
4. **RL environment is not Gym-compliant** — cannot plug in PPO from stable-baselines3
5. **Naming bug**: `train_scorer.py` imports `InterviewScorerMLP` but `scoring_model.py` defines `CandidateScoringMLP` — will crash at import

---

## Step-by-Step Implementation Plan

---

### TASK 3.1-A — Create `training/metrics.py`

**What**: Shared metrics utilities used by all training scripts.

**File**: `training/metrics.py` (new file)

**Logic**:
```python
# Classification metrics (emotion model)
def classification_metrics(y_true, y_pred, label_names) -> dict:
    # Returns: per_class_f1, weighted_f1, macro_f1, confusion_matrix

# Regression metrics (scorer, predictor, evaluator)
def regression_metrics(y_true, y_pred) -> dict:
    # Returns: mae, rmse, pearson_r, spearman_rho

# Ranking metrics (ranker)
def ranking_metrics(scores_list, labels_list, k=5) -> dict:
    # Returns: ndcg_at_k, pairwise_accuracy

# RL metrics (difficulty engine)
def rl_metrics(rewards_per_episode, scores_per_episode) -> dict:
    # Returns: avg_reward, score_variance, pct_in_target_zone (50-80)

# TensorBoard writer factory
def make_writer(model_name: str) -> SummaryWriter:
    return SummaryWriter(f"training/runs/{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
```

**Dependencies**: `sklearn`, `scipy`, `torch.utils.tensorboard`

---

### TASK 3.1-B — Add Metrics + TensorBoard to `train_emotion.py`

**File**: `training/train_emotion.py` (modify)

**Changes**:
1. Import `metrics` module and `make_writer`
2. After each epoch: collect `val_preds`, `val_labels` via `torch.no_grad()` loop
3. Compute `classification_metrics(val_labels, val_preds, EMOTION_LABELS)`
4. Log to TensorBoard:
   - `Loss/train`, `Loss/val` per epoch
   - `Metric/weighted_f1`, `Metric/macro_f1` per epoch
5. Add `ReduceLROnPlateau` scheduler (patience=3, factor=0.5) — already called for in plan
6. Add early stopping (patience=5 on val_loss)
7. Save confusion matrix as PNG to `training/results/emotion_confusion_matrix.png` at end of training
8. Add 5-fold cross-validation using `StratifiedKFold(n_splits=5)`

**Key pseudocode additions**:
```python
writer = make_writer("emotion")
scheduler = ReduceLROnPlateau(optimizer, mode='min', patience=3, factor=0.5)
best_val_loss = float('inf')
patience_counter = 0

for epoch in range(num_epochs):
    # existing training loop ...
    
    # NEW: validation loop
    model.eval()
    val_preds, val_labels_list = [], []
    with torch.no_grad():
        for batch in val_loader:
            outputs = model(...)
            preds = outputs.logits.argmax(dim=-1)
            val_preds.extend(preds.cpu().tolist())
            val_labels_list.extend(batch["labels"].tolist())
    
    metrics_dict = classification_metrics(val_labels_list, val_preds, EMOTION_LABELS)
    writer.add_scalar("Loss/train", train_loss, epoch)
    writer.add_scalar("Loss/val", val_loss, epoch)
    writer.add_scalar("Metric/weighted_f1", metrics_dict["weighted_f1"], epoch)
    
    scheduler.step(val_loss)
    
    # early stopping
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), checkpoint_path)
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= 5:
            print(f"Early stopping at epoch {epoch}")
            break
```

---

### TASK 3.1-C — Add Metrics + TensorBoard to `train_predictor.py`

**File**: `training/train_predictor.py` (modify)

**Changes**:
1. Import metrics module
2. Collect `val_preds`, `val_true` after each epoch
3. Compute `regression_metrics(val_true, val_preds)` → log MAE, RMSE, Spearman ρ, Pearson r
4. TensorBoard: `Loss/train`, `Loss/val`, `Metric/spearman`, `Metric/mae`
5. Add early stopping on val_loss

---

### TASK 3.1-D — Add Metrics + TensorBoard to `train_ranker.py`

**File**: `training/train_ranker.py` (modify)

**Changes**:
1. Import metrics module
2. After each epoch: compute `ranking_metrics(scores, labels)` → NDCG@5, pairwise accuracy
3. TensorBoard: `Loss/train`, `Metric/ndcg_at_5`, `Metric/pairwise_acc`

---

### TASK 3.1-E — Add Metrics + TensorBoard to `train_scorer.py`

**File**: `training/train_scorer.py` (modify)

**Changes**:
1. Fix naming bug: change import from `InterviewScorerMLP` to `CandidateScoringMLP` (or add alias in scoring_model.py)
2. Add train/val split (80/20) — currently uses full dataset
3. Compute `regression_metrics` on val set per epoch
4. TensorBoard: `Loss/train`, `Loss/val`, `Metric/spearman`, `Metric/mae`

---

### TASK 3.1-F — Add Metrics + TensorBoard to `train_skill_matcher.py`

**File**: `training/train_skill_matcher.py` (modify — minimal until Task 3.2 adds real data)

**Changes**:
1. Add TensorBoard writer
2. Log `Loss/train` per epoch
3. After training, compute pairwise accuracy on a held-out set (if data allows)
4. NOTE: Full metrics only meaningful after Task 3.2 replaces dummy data

---

### TASK 3.1-G — Add Metrics + TensorBoard to `train_difficulty.py`

**File**: `training/train_difficulty.py` (modify)

**Changes**:
1. Import metrics module
2. After each episode batch (every 400 epochs per current pattern): compute `rl_metrics`
3. TensorBoard: `Reward/avg`, `Score/variance`, `Score/pct_in_target_zone`

---

### TASK 3.1-H — Create `training/results/` directory marker

**Action**: Create `training/results/.gitkeep` so the results directory exists for plot outputs.

---

### TASK 3.2-A — Create `training/generate_skill_data.py`

**File**: `training/generate_skill_data.py` (new file)

**What**: Uses Groq API (already configured in project) to generate 500+ CV/JD pairs with match labels.

**Logic**:
```python
import json, os
from groq import Groq  # already used in agent.py

DOMAINS = [
    "Backend Python", "Frontend React", "Data Science", "DevOps", "Mobile iOS",
    "Security Engineering", "ML Engineering", "Full Stack", "Game Development",
    "Embedded Systems", "Cloud Architecture", "Database Engineering"
]

PROMPT_MATCH = """Generate a realistic CV skills section and a matching Job Description requirements section for the domain: {domain}.
The CV should clearly qualify for the JD.
Return ONLY valid JSON: {{"cv_skills": "...", "jd_requirements": "...", "is_match": true}}"""

PROMPT_MISMATCH = """Generate a realistic CV skills section and a Job Description for a DIFFERENT domain: cv_domain={cv_domain}, jd_domain={jd_domain}.
The candidate does NOT qualify.
Return ONLY valid JSON: {{"cv_skills": "...", "jd_requirements": "...", "is_match": false}}"""

def generate_dataset(n_match=250, n_mismatch=250, output_path="data/skill_pairs.json"):
    client = Groq()
    samples = []
    
    # Generate matching pairs
    for i in range(n_match):
        domain = DOMAINS[i % len(DOMAINS)]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": PROMPT_MATCH.format(domain=domain)}],
            temperature=0.8  # variety
        )
        sample = json.loads(response.choices[0].message.content)
        samples.append(sample)
    
    # Generate mismatched pairs
    for i in range(n_mismatch):
        cv_domain = DOMAINS[i % len(DOMAINS)]
        jd_domain = DOMAINS[(i + 3) % len(DOMAINS)]  # offset to ensure mismatch
        response = client.chat.completions.create(...)
        sample = json.loads(response.choices[0].message.content)
        samples.append(sample)
    
    with open(output_path, "w") as f:
        json.dump(samples, f, indent=2)
    print(f"Generated {len(samples)} samples → {output_path}")
```

**Output**: `data/skill_pairs.json` — list of `{cv_skills, jd_requirements, is_match}` dicts.

**Error handling**: Wrap each API call in try/except, skip failed samples, log count.

---

### TASK 3.2-B — Modify `training/train_skill_matcher.py` to Load Real Data

**File**: `training/train_skill_matcher.py` (modify)

**Changes**:
1. Add `RealSkillDataset` class that loads from `data/skill_pairs.json`:
```python
class RealSkillDataset(Dataset):
    def __init__(self, json_path):
        with open(json_path) as f:
            self.data = json.load(f)
    
    def __len__(self): return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        return item["cv_skills"], item["jd_requirements"], float(item["is_match"])
```

2. Replace `DummySkillDataset` usage:
```python
# Before:
dataset = DummySkillDataset(num_samples=160)

# After:
json_path = "data/skill_pairs.json"
if os.path.exists(json_path):
    dataset = RealSkillDataset(json_path)
    print(f"Loaded {len(dataset)} real samples")
else:
    print("WARNING: Real data not found, using dummy data")
    dataset = DummySkillDataset(num_samples=160)
```

3. Add 80/20 train/val split
4. Save checkpoint as `skill_matcher_v2.pt`

---

### TASK 3.3-A — Create `training/interview_env.py`

**File**: `training/interview_env.py` (new file)

**What**: A proper Gymnasium-compliant environment modeling candidate dynamics.

**Full implementation** (from plan, with additions):
```python
import gymnasium as gym
from gymnasium import spaces
import numpy as np

class InterviewEnv(gym.Env):
    metadata = {"render_modes": ["human"]}
    
    def __init__(self, max_questions=5):
        super().__init__()
        self.max_questions = max_questions
        
        # Action: difficulty level 1-5
        self.action_space = spaces.Discrete(5)
        
        # State: [avg_score_norm, trend, current_diff_norm, engagement, topic_diversity, questions_remaining_norm]
        self.observation_space = spaces.Box(
            low=np.zeros(6, dtype=np.float32),
            high=np.ones(6, dtype=np.float32),
            dtype=np.float32
        )
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.candidate_skill = self.np_random.uniform(1.0, 5.0)
        self.engagement = 1.0
        self.fatigue = 0.0
        self.scores = []
        self.difficulties_used = set()
        self.step_count = 0
        return self._get_obs(), {}
    
    def step(self, action):
        difficulty = action + 1  # map 0-4 → 1-5
        
        skill_gap = self.candidate_skill - difficulty
        base_score = 65.0 + skill_gap * 12.0
        
        # Engagement dynamics
        self.engagement = max(0.3, self.engagement - 0.05 - self.fatigue * 0.02)
        base_score *= self.engagement
        
        # Fatigue from hard questions
        if difficulty >= 4:
            self.fatigue = min(1.0, self.fatigue + 0.15)
        else:
            self.fatigue = max(0.0, self.fatigue - 0.05)
        
        score = float(np.clip(
            base_score + self.np_random.normal(0, 8), 0, 100
        ))
        self.scores.append(score)
        self.difficulties_used.add(difficulty)
        self.step_count += 1
        
        # Multi-objective reward
        score_reward = -abs(score - 65.0) / 100.0        # keep near 65
        engagement_reward = (self.engagement - 0.5) * 0.3  # maintain engagement
        variety_bonus = 0.05 if len(self.difficulties_used) > 1 else 0.0  # encourage variety
        
        reward = score_reward + engagement_reward + variety_bonus
        
        terminated = self.step_count >= self.max_questions
        truncated = False
        info = {"score": score, "difficulty": difficulty, "engagement": self.engagement}
        
        return self._get_obs(), reward, terminated, truncated, info
    
    def _get_obs(self):
        avg_score_norm = (np.mean(self.scores) / 100.0) if self.scores else 0.5
        
        if len(self.scores) >= 2:
            trend = (self.scores[-1] - self.scores[-2]) / 100.0
            trend = float(np.clip((trend + 1.0) / 2.0, 0.0, 1.0))  # normalize to [0,1]
        else:
            trend = 0.5
        
        current_diff_norm = (len(self.scores) > 0 and
                             self.scores[-1] > 0 and
                             (self.difficulties_used and max(self.difficulties_used) / 5.0)) or 0.5
        
        topic_diversity = len(self.difficulties_used) / 5.0
        questions_remaining_norm = 1.0 - (self.step_count / self.max_questions)
        
        return np.array([
            avg_score_norm,
            trend,
            float(current_diff_norm) if current_diff_norm else 0.5,
            self.engagement,
            topic_diversity,
            questions_remaining_norm
        ], dtype=np.float32)
```

**Edge cases**:
- Empty scores list → obs uses default 0.5 values
- Seed reproducibility via `super().reset(seed=seed)`
- Clamp all reward components to prevent gradient explosion in PPO

---

### TASK 3.3-B — Create `training/train_difficulty_ppo.py`

**File**: `training/train_difficulty_ppo.py` (new file)

**What**: Train PPO on InterviewEnv and run 3-way comparison (heuristic, REINFORCE, PPO).

```python
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback
from training.interview_env import InterviewEnv
import numpy as np, json

def train_ppo():
    # Vectorized env for faster training
    env = make_vec_env(InterviewEnv, n_envs=4)
    
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        tensorboard_log="training/runs/difficulty_ppo",
        learning_rate=3e-4,
        n_steps=128,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.01,  # entropy regularization (mirrors REINFORCE entropy bonus)
    )
    
    eval_env = InterviewEnv()
    eval_callback = EvalCallback(eval_env, eval_freq=5000, n_eval_episodes=50)
    
    model.learn(total_timesteps=50_000, callback=eval_callback)
    model.save("models/checkpoints/difficulty_ppo_v1")
    return model

def run_heuristic(n_simulations=500):
    """Baseline: if score > 70 increase difficulty, if score < 50 decrease."""
    env = InterviewEnv()
    results = []
    for _ in range(n_simulations):
        obs, _ = env.reset()
        current_diff = 2  # start at medium
        scores = []
        for _ in range(env.max_questions):
            obs, reward, terminated, truncated, info = env.step(current_diff - 1)
            scores.append(info["score"])
            if info["score"] > 70 and current_diff < 5:
                current_diff += 1
            elif info["score"] < 50 and current_diff > 1:
                current_diff -= 1
            if terminated: break
        results.append(scores)
    return results

def run_reinforce(n_simulations=500):
    """Use existing AdaptiveDifficultyEngine (REINFORCE policy)."""
    from models.registry import registry
    engine = registry.load_difficulty_engine()
    env = InterviewEnv()
    results = []
    for _ in range(n_simulations):
        obs, _ = env.reset()
        scores = []
        for _ in range(env.max_questions):
            action = engine.decide_next_difficulty(scores, len(scores)+1) - 1
            obs, reward, terminated, truncated, info = env.step(action)
            scores.append(info["score"])
            if terminated: break
        results.append(scores)
    return results

def run_ppo(model, n_simulations=500):
    env = InterviewEnv()
    results = []
    for _ in range(n_simulations):
        obs, _ = env.reset()
        scores = []
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            scores.append(info["score"])
            done = terminated or truncated
        results.append(scores)
    return results

def compare_methods():
    ppo_model = train_ppo()
    
    heuristic_results = run_heuristic()
    reinforce_results = run_reinforce()
    ppo_results = run_ppo(ppo_model)
    
    def compute_stats(results):
        all_scores = [s for episode in results for s in episode]
        return {
            "score_variance": float(np.var(all_scores)),
            "pct_in_target_zone": float(np.mean([50 <= s <= 80 for s in all_scores]) * 100),
            "mean_score": float(np.mean(all_scores))
        }
    
    report = {
        "heuristic": compute_stats(heuristic_results),
        "reinforce": compute_stats(reinforce_results),
        "ppo": compute_stats(ppo_results)
    }
    
    print("\n=== Comparison Table ===")
    print(f"{'Method':<15} {'Variance':<12} {'%In50-80':<12} {'Mean Score'}")
    for method, stats in report.items():
        print(f"{method:<15} {stats['score_variance']:<12.2f} {stats['pct_in_target_zone']:<12.1f} {stats['mean_score']:.1f}")
    
    with open("training/results/difficulty_comparison.json", "w") as f:
        json.dump(report, f, indent=2)
    
    return report
```

---

### TASK 3.3-C — Update `requirements.txt`

**File**: `requirements.txt` (modify)

**Add these lines** (respecting what already exists):
```
gymnasium==0.29.1
stable-baselines3==2.3.0
tensorboard==2.16.2
rank-bm25==0.2.2
scikit-learn>=1.3.0
scipy>=1.11.0
```

Also ensure these ML dependencies are present (likely missing):
```
torch>=2.0.0
transformers>=4.35.0
librosa>=0.10.0
pandas>=2.0.0
numpy>=1.24.0
soundfile>=0.12.0
```

---

## Execution Order

1. `training/metrics.py` — must exist before modifying any train_*.py
2. `training/results/` directory
3. Modify all 6 `train_*.py` files in parallel (independent)
4. Fix naming bug in `train_scorer.py` (CandidateScoringMLP)
5. `training/generate_skill_data.py` — creates data
6. Run `generate_skill_data.py` to populate `data/skill_pairs.json`
7. Modify `train_skill_matcher.py` to use real data
8. `training/interview_env.py` — Gym environment
9. `training/train_difficulty_ppo.py` — PPO training + comparison
10. `requirements.txt` — update dependencies

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `training/train_emotion.py` | Add TensorBoard, k-fold, per-class F1, LR scheduler, early stopping |
| `training/train_predictor.py` | Add TensorBoard, val split, Spearman/Pearson/MAE/RMSE |
| `training/train_ranker.py` | Add TensorBoard, val split, NDCG@5, pairwise accuracy |
| `training/train_scorer.py` | Fix import bug, add val split, TensorBoard, regression metrics |
| `training/train_skill_matcher.py` | Add TensorBoard, RealSkillDataset loader |
| `training/train_difficulty.py` | Add TensorBoard, RL metrics |
| `requirements.txt` | Add gymnasium, stable-baselines3, tensorboard, scikit-learn, scipy |

## Critical Files to Create

| File | Purpose |
|------|---------|
| `training/metrics.py` | Shared metrics: classification, regression, ranking, RL |
| `training/generate_skill_data.py` | Groq-powered skill pair generator |
| `training/interview_env.py` | Gymnasium-compliant interview simulation |
| `training/train_difficulty_ppo.py` | PPO training + 3-way method comparison |
| `training/results/.gitkeep` | Results directory marker |

---

## Bug to Fix

**In `training/train_scorer.py`**: Import says `InterviewScorerMLP` but `models/scoring_model.py` only defines `CandidateScoringMLP`. This will crash at runtime. Fix by either:
- Changing the import in `train_scorer.py` to `CandidateScoringMLP`, OR
- Adding `InterviewScorerMLP = CandidateScoringMLP` alias in `scoring_model.py`

Prefer option 1 (change the import).

---

## Verification Plan

| Task | Test | Pass Criteria |
|------|------|--------------|
| 3.1 metrics.py | Import all functions, call with dummy data | No exceptions, correct dtypes returned |
| 3.1 TensorBoard | Run any train script, then `tensorboard --logdir training/runs` | Loss curves visible in browser |
| 3.1 emotion | Run train_emotion.py for 2 epochs | classification_report printed, confusion matrix saved to training/results/ |
| 3.2 generate | Run generate_skill_data.py with n=10 (test mode) | data/skill_pairs.json created with valid JSON |
| 3.2 skill | Run train_skill_matcher.py | Loads from JSON, prints "Loaded N real samples" |
| 3.3 env | `env = InterviewEnv(); obs, _ = env.reset(); env.step(2)` | No exception, obs shape (6,) |
| 3.3 PPO | Run train_difficulty_ppo.py | PPO converges (reward increases), comparison table printed |
| scorer bug | `from training.train_scorer import *` | No ImportError |
