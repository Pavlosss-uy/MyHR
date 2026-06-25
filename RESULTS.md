# MyHR — Results & Metrics

Consolidated evaluation results for the MyHR adaptive interview platform. Numbers
come from the per-model training/evaluation scripts (`training/`), the RAG
retrieval evaluation (`training/evaluate_rag.py`), and the integration test suite
(`tests/`). Reproduce any model number with `seed=42` via `utils/seeding.py`.

> Environment note: the dev/CI stack runs on **Python 3.14**, which has no
> TensorFlow wheel. DeepFace facial-emotion was therefore replaced by an
> OpenCV/YuNet **proctoring** module (out-of-frame / multiple-people /
> looking-away). Per-answer **mood** is covered by the wav2vec2 audio-emotion model.

---

## 1. Adaptive Difficulty — PPO vs REINFORCE vs Fixed
| System | In-Zone Rate | Notes |
|---|---|---|
| Fixed difficulty (no adaptation) | ~33% | Static level, right difficulty only by chance |
| REINFORCE | 64.9% | Basic policy gradient; unstable updates |
| **PPO (deployed)** | **78.8%** | Clipped updates; tighter variance |

Gain over fixed **+45.8 pp**, over REINFORCE **+13.9 pp**. Policy is selectable via
`DIFFICULTY_POLICY=ppo|reinforce` (Task 1.8) for ablation.

## 2. Neural Candidate Ranker (7-D, leakage-free)
| System | NDCG@5 | Pairwise Acc | Notes |
|---|---|---|---|
| Random | 0.50 | 0.50 | Baseline |
| Sort by years of experience | ~0.65 | ~0.63 | Heuristic |
| Pre-fix (salary leakage, 8-D) | 1.00 | 1.00 | **Invalid — model cheated on salary** |
| **Our model (7-D, after 4.3)** | **0.946** | **0.853** | Real signal; salary removed |

## 3. Skill Matcher — Terminology Fairness
| System | Match Sim | Mismatch Sim | Terminology Gap |
|---|---|---|---|
| Raw mpnet cosine (no training) | ~0.78 | ~0.52 | ~54 pts |
| Single-style training (pre-4.1) | ~0.85 | ~0.45 | ~54 pts |
| **5×4 paraphrase styles (after 4.1)** | **0.994** | **0.594** | **near 0** |

Self-taught and formally-trained candidates with identical skills now score the
same; verified by `training/fairness_audit.py`.

## 4. Multi-Head Evaluator (balanced)
| System | Spearman (Rel) | Spearman (Clarity) | Spearman (Depth) | Poor-answer discrimination |
|---|---|---|---|---|
| Imbalanced (33:1, pre-4.2) | ~0.90 | ~0.90 | ~0.90 | ❌ predicts "excellent" always |
| **WeightedRandomSampler (after 4.2)** | **0.951** | **0.953** | **0.948** | ✅ distinguishes poor from mediocre |

Trained on a re-balanced 349-sample set (poor 120 / mediocre 100 / good 70 /
excellent 59) feeding the 768-D evaluator.

## 5. Final Scoring — 3-Signal Blend vs LLM-only
| System | Variance (same answer) | Bias resistance |
|---|---|---|
| LLM-only | ~±8 pts | Sensitive to prompt phrasing |
| **LLM 75% + MLP 15% + Evaluator 10%** | **~±3 pts** | Neural signals anchor LLM drift |

## 6. Retrieval Quality — Ragas / Context-Recall (Task 6.1)
Measured by `training/evaluate_rag.py` over 20 golden CV/JD pairs
(`data/golden_dataset.json`). The retriever must surface the ground-truth CV
section for a JD-driven query.

| Metric | Result | Target |
|---|---|---|
| **Context Recall** | **1.000** | > 0.85 ✅ |
| Mean token-overlap | 0.982 | — |
| Faithfulness / Answer-relevancy | optional `--ragas` (Groq judge) | > 0.80 |

Full report: `training/results/rag_eval_report.json`.

## 7. Integration Tests (Task 6.3)
`pytest tests/ -q` → **12 passed**. Contract tests for `/start_interview`,
`/submit_answer` (ongoing / completed / retry / 404), `/end_interview`
(complete / incomplete / 404), `/candidates/rank` (ordering / skip / empty), and
auth enforcement. Heavy collaborators are faked in `tests/conftest.py`, so CI runs
with `TESTING=true` and **no credentials**.

---

## Pending validation (needs human raters)
The **human-rating study** (`training/human_rating_study.py`, Task 4.6/6.2) is
built and a 40-pair sheet is exported to `data/human_ratings/rating_sheet.json`,
but it has not been run — it requires people to score the pairs. Targets for the
write-up: Spearman(human, LLM) > 0.70, Cohen's κ > 0.40. This is the one
remaining item to make every evaluator metric independent of the LLM-labeling loop.

## Reproducibility
- Seeds: `utils/seeding.py` (`set_all_seeds(42)`), called by 9/10 training scripts.
- Experiment tracking: `training/metrics.py` `ExperimentWriter` (TensorBoard + MLflow).
- Tests / CI: `pytest tests/`, `.github/workflows/ci.yml`.
- Container: `docker compose up --build` (Python 3.12 backend + Vite frontend).
