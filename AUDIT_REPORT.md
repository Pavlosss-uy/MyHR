# MyHR — Complete Codebase Audit Report
**Date:** 2026-06-18
**Auditor:** Claude Sonnet 4.6 (Claude Code)
**Branch:** master

---

## A. Executive Summary

MyHR is an AI-powered interview platform with a React/Vite frontend and a FastAPI backend. The core interview loop (CV upload → RAG ingestion → question generation → audio answer → transcription → evaluation → report) is **functionally complete and runnable end-to-end**. A significant B2B/HR layer (job postings, candidate pipelines, invitation flows, Firestore persistence) has also been implemented.

The project claims 8 custom PyTorch models as its research contribution. Of these, **zero have trained checkpoint files** — the `models/checkpoints/` directory does not exist. Training scripts are present and detailed, but **all training was done on a different developer machine ("Remo")**, and **at least two training runs crashed** (evaluator had a `TypeError`, the first training attempt had a `UnicodeEncodeError`). The published evaluation metrics (evaluator Spearman 0.924, ranker 100% accuracy) cannot be reproduced on this machine and show signs of data leakage or overfitting.

The live system falls back gracefully — the evaluator loads with random weights, the skill matcher falls back to keyword overlap, the emotion model fails silently — so the app *runs*, but neural model contributions are not actually active. The system currently operates largely as an LLM-orchestrated interview pipeline with decorative neural layers.

---

## B. Feature Completion Matrix

| Feature | Status | Completion % | Evidence |
|---|---|---|---|
| **Core Interview Loop** (start → Q&A → report) | Complete | 95% | `server.py:378-875`, `agent.py:1-812` |
| **RAG Pipeline** (BM25 + Dense + RRF + Reranker) | Complete | 95% | `retriever.py` — all 4 stages implemented |
| **Question Generation** (3 modes, adaptive difficulty) | Complete | 90% | `agent.py:173-327` — difficulty level passed as text guidance to LLM |
| **Answer Evaluation** (blended LLM + neural) | Partial | 60% | Neural path runs but with random weights — `agent.py:329-457`, `models/registry.py:138-154` |
| **Feature Extractor** (8 real NLP features) | Complete | 95% | `models/feature_extractor.py` — full implementation with embeddings, spaCy, cosine similarity |
| **Multi-Head Evaluator** (MOD-4) | Partial | 50% | Architecture complete, **no checkpoint**, loads with random weights; `registry.py:147-151` has silent fallback |
| **Speech Emotion Model** (MOD-2) | Partial | 40% | Architecture complete; **no checkpoint**; `create_dummy_data.py` trains on silence (zeros); real RAVDESS/CREMA-D data never downloaded to this machine |
| **Skill Matcher Siamese Net** (MOD-3) | Partial | 40% | Architecture complete; **no checkpoint**; fairness audit ran on lexical fallback (not neural) — confirmed by `"feature_source": "fallback_lexical"` in `training/results/fairness_report.json` |
| **Adaptive Difficulty Engine** (MOD-7) | Partial | 50% | REINFORCE + PPO architectures complete; **no checkpoint**; difficulty is passed as text guidance to LLM prompt — effective even without trained weights |
| **Performance Predictor** (MOD-6) | Partial | 30% | Architecture complete; **no checkpoint**; will crash when called (no try-catch unlike evaluator) |
| **Candidate Ranker** (MOD-5) | Partial | 25% | Architecture in `models/candidate_ranker.py`; **no checkpoint**; no API endpoint; `recommender/feature_store.py` does not exist |
| **Scoring MLP** (MOD-1) | Not wired | 20% | Exists in `models/scoring_model.py`; **not called anywhere in pipeline** — `registry.load_scorer()` exists but is never invoked by `agent.py` or `server.py` |
| **Cross-Encoder Scorer** | Partial | 30% | `models/cross_encoder_scorer.py` exists; training attempted; Spearman ρ=0.18 (very poor); **not wired into pipeline** |
| **SHAP Explainability** | Complete | 85% | `models/explainer.py` wired in `agent.py:359-390`; generates waterfall plots per evaluation |
| **Report Generation** | Complete | 90% | `agent.py:649-743` — full structured JSON with normalization, bidirectional key aliases, fallbacks |
| **TTS/STT (Deepgram)** | Complete | 90% | `services.py` — STT (Nova-2) + TTS (Aura Asteria) + PCM streaming |
| **WebSocket Interview Protocol** | Complete | 90% | `server.py:525-694` — full binary audio streaming, utterance-based protocol |
| **Firebase Auth** | Complete | 95% | `firestore_client.py`, `src/lib/firebase.js` |
| **Session Persistence (Firestore)** | Complete | 90% | `firestore_client.py` fully replaces PostgreSQL — atomic field transforms, concurrent-safe |
| **B2B HR Routes** | Complete | 80% | `hr_routes.py` — access requests, jobs, batch CV upload, candidate ranking, interview invitations |
| **HR Dashboard** | Complete | 80% | `src/pages/HRDashboard.jsx` — loads real data via `getJobs()` API, not mock |
| **Candidate Interview Portal** | Complete | 80% | `src/pages/CandidateInterviewPortal.jsx` + `/candidate-interview/{token}/start` endpoint |
| **Feedback Report UI** | Complete | 90% | `src/pages/FeedbackReport.jsx` — radar charts, tone pie chart, SHAP, multi-section |
| **Training Pipeline** | Partial | 50% | All scripts exist; some crashed; **no `data/` directory** on this machine; `generate_eval_data.py` imports `langchain_openai` (not Groq) |
| **Evaluation Metrics** | Partial | 60% | `training/metrics.py`, results JSON files exist but sourced from a different machine ("Remo") |
| **Fairness Audit** | Partial | 40% | Script complete; overall status **FAIL** — skill_matcher terminology bias max_difference=53.5% vs. 5% threshold; emotion audit skipped (no data) |
| **Model Registry + Versioning** (MOD-10) | Partial | 70% | `models/registry.py` — clean singleton, lazy loading, version map; checkpoints don't exist on this machine |
| **Frontend Tests** | Stub | 5% | `src/test/example.test.js` — file exists but contains only setup code |
| **Backend Tests** | None | 0% | No pytest files anywhere in the project |

---

## C. Remaining Work Matrix

| Task | Priority | Estimated Effort | Files Involved |
|---|---|---|---|
| **Generate all model checkpoint files** — run all training scripts to produce `.pt` files in `models/checkpoints/` | CRITICAL | 2–4 days | `training/train_*.py`, `models/checkpoints/` |
| **Fix evaluator training crash** — `TypeError: 'float' object is not iterable` at `train_evaluator.py:162`; `squeeze()` on single-item batch returns a scalar, not a tensor | CRITICAL | 1 hour | `training/train_evaluator.py:162` |
| **Fix registry crash for missing checkpoints** — only evaluator has try-catch; `load_emotion_model()`, `load_skill_matcher()`, `load_difficulty_engine()`, `load_scorer()`, `load_candidate_ranker()`, `load_performance_predictor()` all call `torch.load()` without protection | CRITICAL | 1 hour | `models/registry.py:58-163` |
| **Create `data/` directory and real training data** — `generate_eval_data.py` imports `langchain_openai` not Groq; needs OpenAI API key or rewrite to use Groq | CRITICAL | 1 day | `training/generate_eval_data.py` |
| **Resolve feature dim mismatch on evaluator** — training log shows `Feature dim: 768` (sentence embeddings) but registry creates `MultiHeadEvaluator(input_dim=8)`; any saved checkpoint from the other machine would be incompatible with inference code | CRITICAL | 2 hours | `models/registry.py:143`, `training/train_evaluator.py:301` |
| **Wire `CandidateScoringMLP` into pipeline** — `load_scorer()` exists in registry but is never called anywhere; MOD-1 contribution is completely bypassed | HIGH | 2 hours | `agent.py:329-457`, `models/registry.py:117-127` |
| **Create `recommender/feature_store.py`** — MOD-5 ranker has no persistence layer; no `/candidates/rank` API endpoint exists | HIGH | 4 hours | `models/candidate_ranker.py`, `server.py` |
| **Fix hardcoded `localhost:8000` URLs** — audio URLs in `server.py` will break in any non-local deployment | HIGH | 1 hour | `server.py:449, 515, 859, 860` |
| **Download real emotion training data** (RAVDESS + CREMA-D) and run `train_emotion.py` with real data instead of silent zeros | HIGH | 1 day | `training/train_emotion.py`, `training/preprocessing.py` |
| **Add CORS middleware** — no `CORSMiddleware` configured; all browser requests will be blocked in production | HIGH | 30 min | `server.py` |
| **Add auth guards to core endpoints** — `POST /start_interview` and `POST /submit_answer` have no authentication; any anonymous user can burn API quota | HIGH | 2 hours | `server.py:378, 775` |
| **Fix UnicodeEncodeError in training scripts** — emoji characters in print statements crash on Windows cp1252 terminal encoding | MEDIUM | 30 min | All `training/train_*.py` files |
| **Improve cross-encoder fine-tuning** — Spearman ρ=0.18 (barely above base -0.15); review training data quality and label distribution | MEDIUM | 2 days | `training/train_cross_encoder.py`, `training/results/cross_encoder_comparison.json` |
| **Fix fairness audit — skill terminology bias** — max_difference=53.5% (threshold 5%); Siamese network needs better contrastive training data covering paraphrase equivalence | MEDIUM | 1 day | `training/train_skill_matcher.py`, `training/generate_skill_data.py` |
| **Run emotion model fairness audit** — skipped because emotion model had no checkpoint at audit time; needs RAVDESS checkpoint first | MEDIUM | 4 hours | `training/fairness_audit.py` |
| **Add environment config for base URL** — replace hardcoded `http://localhost:8000` with a `BASE_URL` environment variable | MEDIUM | 30 min | `server.py`, `.env` |
| **Add backend tests** — zero pytest coverage on any endpoint or model | MEDIUM | 3 days | New `tests/` directory |
| **Validate published model evaluation metrics** — `model_evaluation_report.json` was produced on a different machine with different input dimensions; evaluator Spearman 0.924 and ranker 100% are suspect | MEDIUM | 1 day | `training/results/model_evaluation_report.json` |
| **Add `/candidates/rank` API endpoint** | MEDIUM | 3 hours | `server.py`, `hr_routes.py` |
| **Add skill gap → question focus loop** — identified gaps from skill_matcher are not injected into `COT_QUESTION_PROMPT` | LOW | 2 hours | `server.py:415-425`, `prompts.py` |
| **Add frontend tests** — only stub exists in `src/test/` | LOW | 2 days | `src/test/` |
| **Clean up `requirements.txt`** — `sqlalchemy`, `psycopg2-binary`, `streamlit` still listed; project no longer uses PostgreSQL or Streamlit | LOW | 15 min | `requirements.txt` |

---

## D. Technical Debt

### Critical Issues

**1. No checkpoint files exist anywhere**
`models/checkpoints/` directory is absent. `load_emotion_model()`, `load_skill_matcher()`, `load_difficulty_engine()`, `load_scorer()`, `load_candidate_ranker()`, and `load_performance_predictor()` all call `torch.load(path)` without a try-catch and will raise `FileNotFoundError`, crashing the server. Only `load_evaluator()` (`registry.py:147-151`) has a silent fallback.

**2. Feature dimension mismatch on evaluator**
The training log (`evaluator_output2.txt`) shows `Feature dim: 768` (sentence embeddings used as training input). However `registry.py:143` instantiates `MultiHeadEvaluator(input_dim=8)` at inference time. Any checkpoint from the other machine would have 244,355 parameters sized for 768-dim input, incompatible with the 8-feature inference model.

**3. Fairness audit status: FAIL**
`training/results/fairness_report.json` shows `overall_status: "fail"`. The skill matcher scores "direct_professional" phrasing 0.75 vs "academic_phrasing" 0.21 — a 54-point gap for equivalent skills. This is a significant bias issue.

**4. Fairness "passes" are not genuine**
The counterfactual fairness and disparate impact tests both show `"feature_source": "fallback_lexical"` — the neural skill matcher was not running during the audit. The lexical fallback doesn't encode candidate names, so counterfactual fairness trivially passes (scores are identical). The "pass" provides no real fairness guarantee.

**5. CandidateScoringMLP (MOD-1) is completely bypassed**
`registry.load_scorer()` is defined but never called in any code path. The primary MOD-1 research contribution is an orphan.

---

### Security Concerns

| Issue | Severity | Location |
|---|---|---|
| No authentication on `/start_interview` and `/submit_answer` | HIGH | `server.py:378, 775` |
| No CORS middleware configured | HIGH | `server.py` |
| Firebase credentials fall back to Application Default Credentials | MEDIUM | `firestore_client.py:43-45` |
| Hardcoded `localhost:8000` in audio URLs | MEDIUM | `server.py:449, 515, 859` |
| Temp audio files written to `./uploads/` — no size limit on uploads | LOW | `server.py:790-792` |

---

### Performance Concerns

- **Sentence embeddings computed per request** — `AnswerFeatureExtractor` calls `embedder.encode()` twice (question + answer) on each evaluation turn. With `all-mpnet-base-v2` on CPU this adds ~200–400ms latency.
- **SHAP `KernelExplainer` is slow** — `agent.py:377` runs KernelExplainer with 20 background samples per answer evaluation. This is a blocking call in the async event loop.
- **Synchronous model inference in async FastAPI** — All PyTorch inference runs in the event loop without `run_in_executor`. Under concurrent interviews this will queue requests.

---

### Scalability Concerns

- Pinecone namespace per session — will accumulate without cleanup.
- Firestore atomic field transforms are correct — concurrent WebSocket workers won't collide.
- `_hybrid_cache` in `retriever.py` stores session retrievers in a process-level dict — will grow unbounded in a long-running process.

---

### Missing Tests

- **0% backend coverage** — No pytest files, no unit tests for models, no integration tests for endpoints.
- **0% meaningful frontend coverage** — `src/test/example.test.js` contains only vitest setup boilerplate.

---

## E. Branch / Development Progress Analysis

**Branch:** `master` (single branch, no remote comparison available)

Based on file evidence, development has progressed through 4 phases:

| Phase | What Was Built | Status |
|---|---|---|
| Phase 1 | Real feature extraction pipeline (`feature_extractor.py`), replaced hardcoded constants | Complete |
| Phase 2 | Training scripts for all 6 models, `generate_eval_data.py`, `train_evaluator.py`, cross-encoder | Scripts complete; runs crashed |
| Phase 3 | RL environment (`interview_env.py`), PPO difficulty engine, evaluation metrics, fairness audit | Scripts complete; no checkpoints saved here |
| Phase 4 | B2B HR layer (`hr_routes.py`), Firestore migration, email invitations, candidate portal, analytics | Largely complete |

Notable architectural changes in this branch vs. original plan:
- PostgreSQL replaced by Firestore (`firestore_client.py`)
- `celery_worker.py` exists but tone analysis moved back to in-process (`_attach_tone_analysis`)
- `recommender/` directory planned but never created — `candidate_ranker.py` lives in `models/` instead
- `app.py` (Streamlit) still present but unused; backend is pure FastAPI

---

## F. Release Readiness Score: **38 / 100**

| Dimension | Score | Rationale |
|---|---|---|
| Core functionality works | 70/100 | Interview loop runs end-to-end via LLM; all major routes functional |
| AI/ML claims are validated | 5/100 | No checkpoints on this machine; evaluation metrics unverifiable; training crashed |
| Security | 25/100 | No auth on core endpoints; no CORS; hardcoded localhost |
| Test coverage | 2/100 | Effectively zero backend or frontend tests |
| Production readiness | 30/100 | Hardcoded localhost URLs; stale requirements; no CORS; no error monitoring |
| Research contributions demonstrable | 20/100 | Feature extractor is real; training scripts are comprehensive; but no working trained models |

---

## G. Final Verdict

### What has been completed

- Full end-to-end interview pipeline: CV upload → RAG indexing → adaptive LLM questioning → audio STT → tone analysis → blended evaluation → structured report → frontend display
- Hybrid retrieval (BM25 + dense + RRF + cross-encoder reranker) — genuinely complete and wired
- 8 custom neural network architectures with full training scripts, metrics, TensorBoard integration, and evaluation harnesses
- Complete B2B HR layer: job management, batch CV upload, candidate pipeline, interview invitations via email, Firestore-backed persistence
- SHAP explainability integrated into the live evaluation pipeline (waterfall plots generated per answer)
- Fairness audit framework with counterfactual testing, terminology bias detection, and disparate impact analysis
- React frontend with complete UI: interview room, feedback report, HR dashboard, analytics, candidate portal, admin panel

### What is currently being worked on

- Getting all 8 model checkpoints trained and deployed on this machine
- Fixing the evaluator training script crash (tensor squeeze dimension mismatch in loss computation)
- Resolving the 768 vs 8 feature dimension inconsistency between training and inference

### What remains before the project can be considered finished

1. Generate all model checkpoints (none exist on this machine)
2. Fix the evaluator training crash and resolve the 768 vs 8 dim mismatch
3. Add try-catch fallbacks to all registry model loaders
4. Add CORS middleware and authentication guards to core endpoints
5. Fix hardcoded localhost URLs with env-configured base URL
6. Wire `CandidateScoringMLP` into the evaluation pipeline (MOD-1 currently orphaned)
7. Create `recommender/feature_store.py` and `/candidates/rank` endpoint (MOD-5)
8. Retrain emotion model on real RAVDESS/CREMA-D data (currently trains on silence)
9. Fix skill matcher terminology bias (54-point gap is a critical fairness failure)
10. Write at least basic backend tests for the three core endpoints

### Next 10 development tasks in priority order

| # | Task | Effort |
|---|---|---|
| 1 | Fix `train_evaluator.py` crash — squeeze/scalar `TypeError` at line 162 | 1 hour |
| 2 | Add try-catch to all `load_*` methods in `registry.py` | 1 hour |
| 3 | Resolve evaluator input_dim — pick 8 features OR 768 embeddings consistently across registry and training script | 2 hours |
| 4 | Fix `generate_eval_data.py` (`langchain_openai` → Groq), generate training data, run `train_evaluator.py` | 1 day |
| 5 | Run `generate_skill_data.py` with paraphrase-inclusive data, then `train_skill_matcher.py` | 1 day |
| 6 | Download RAVDESS/CREMA-D, run `train_emotion.py` with real data | 1 day |
| 7 | Run `train_scorer.py`, `train_predictor.py`, `train_ranker.py`, `train_difficulty.py` | 1 day |
| 8 | Wire `CandidateScoringMLP` as a third scoring signal in `evaluate_answer_node` | 2 hours |
| 9 | Add CORS, auth guards on `/start_interview` and `/submit_answer`, env-var base URL | 3 hours |
| 10 | Add `/candidates/rank` endpoint and `recommender/feature_store.py` | 4 hours |

---

*Report generated by Claude Code — claude-sonnet-4-6 — 2026-06-18*
