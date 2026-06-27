# MyHR — Comprehensive Training + Enterprise Engineering Audit
**Date:** 2026-06-27 · **Auditor:** Claude Opus 4.8 (Staff-level review) · **Branch:** enterprise
**Every finding is verified against the actual code, not comments or intentions.**

---

## 1. Executive Summary

MyHR is an adaptive AI-interview platform with three genuine subsystems: a **LangGraph/Groq LLM
layer**, a **hybrid RAG layer** (BM25 + Pinecone dense + RRF + cross-encoder rerank), and a custom
**PyTorch neural layer** (8 models). The system is functionally complete end-to-end and, after recent
work, has matured substantially: the enterprise branch is now a **proper layered module** (routes →
`hr_services/` → repository helpers, with Pydantic DTOs and 60 passing tests), and the neural layer is
**no longer decorative** — checkpoints exist, the historic train/inference embedding mismatch is fixed
and guarded, and both neural scorers contribute 35% of every score.

The dominant remaining weakness is **scientific rigor, not architecture**: the evaluator is trained on
LLM-generated labels and an LLM is also the 65% judge at inference, so accuracy is *self-referential*.
Held-out test reporting was just added (code) but not yet run; the human-rating study is built but not
yet conducted; the emotion model is effectively single-fold; the candidate ranker is trained on
synthetic data. Production hardening (real object storage, observability, lazy ML init) is also
outstanding.

**Verdict in one line:** demo-ready and architecturally healthy; not yet defensible as "validated
against human ground truth" nor hardened for open enterprise scale.

## 2. Overall Project Score: **6.5 / 10**

| Subsystem | Score | Basis |
|---|---|---|
| Training pipeline | 6.5 | Pro hygiene (seeds/early-stop/MLflow/Spearman); test-split just added, emotion 1-fold |
| Enterprise branch | 7.0 | Real service layer + Pydantic + atomic stats + tests |
| AI/ML correctness | 5.0 | Models discriminate, but labels & judge both LLM-derived |
| Architecture | 6.5 | Enterprise layered; `agent.py`/`server.py` still god-files |
| Code quality | 7.0 | Readable, typed, documented |
| Security | 6.5 | Auth/RBAC/tokens/CORS/rate-limit solid; print-logging remains |
| Production readiness | 5.0 | Local-disk storage, no observability, ML loads at import |

## 3. Training Branch Audit

**Dataset / labels:** Training data is LLM-generated (`generate_eval_data.py`). **Root weakness:**
labels are one LLM's opinion — there is no human ground truth, so every downstream metric measures
"agreement with the labeler," not correctness. Class imbalance (≈325 excellent / 10 poor) is real but
**handled** via `WeightedRandomSampler` (`train_evaluator.py:141-153`).

**Data split / leakage:** Until today, every `train_*.py` used train/val only and reported final
metrics on the val set used for early stopping (optimistic). **Now fixed in code** — `train_evaluator.py`
and `train_scorer.py` use **70/15/15** with a held-out TEST fold excluded from training and selection,
printing Val vs Test side by side. *Not yet re-run* to produce the numbers. The remaining `train_*.py`
(ranker, predictor, difficulty, skill, emotion) still need the same treatment.

**Pipeline:** Strong hygiene — `set_all_seeds(42)`, `AdamW`, `CosineAnnealingLR`, early stopping with
patience + best-state restore, dual MLflow+TensorBoard (`ExperimentLogger` + `make_writer`),
Spearman/NDCG/F1 metrics, embedder-stamped checkpoints. **The embedding-alignment fix is the highlight**
(`train_evaluator.py:90-103`): training answers are re-encoded with `all-mpnet-base-v2` to match
inference, and the checkpoint records the embedder so the registry rejects a mismatched model.

**Weaknesses:** (1) **Emotion model is 1-fold** — `train_emotion.py:237` literally prints
"(Running 1 fold for time efficiency)"; the "5-fold CV" mean±std is over one element. (2) **Re-encode
every run** — `load_data` instantiates a fresh `SentenceTransformer` and encodes the whole dataset each
run (no feature cache); slow + non-deterministic across HF versions. (3) No mixed precision / GPU
assumptions documented (CPU-bound encoding dominates).

**Verdict:** Professional-grade loop engineering; the gaps are scientific (test sets just added, emotion
folds, human validation), not mechanical.

## 4. Enterprise Branch Audit

**This is the strongest-improved area.** Verified present and integrated:

- **Service layer**: `CandidateIngestionService`, `InvitationService`, `RankingService`, `TokenService`
  (`hr_services/`). Routes delegate (`hr_routes.py` instantiates `_ingestion_svc`, `_invitation_svc`,
  `_ranking_svc`, `_token_svc` and calls them).
- **DTOs / validation**: full Pydantic request + response models with constraints
  (`models/hr_models.py` — `matchScore: ge=0,le=100`, `title: max_length=300`); `response_model=` on
  every route.
- **Exception handling**: services raise domain exceptions (`TokenExpiredError`, `OwnershipError`, …)
  translated to HTTP codes at the route boundary — a clean architecture boundary.
- **Thread safety / resource mgmt**: `asyncio.to_thread` around skill-matcher + ranker;
  `asyncio.wait_for(..., timeout=10)` around CV extraction; lazy `get_db()` (no Firebase connect at
  import).
- **Data integrity**: job stats updated via `@fs_admin.transactional` read-modify-write
  (`ingestion_service.py:299-313`) — the lost-update bug is fixed.
- **Security**: Firebase token auth, admin allowlist, tenant isolation (`_get_authorized_job`),
  `secrets.token_urlsafe` tokens, server-side-only interview scores, `html.escape` on all email fields,
  ownership check in `TokenService` (T24), file-size guard (5 MB), `@limiter.limit("10/minute")` on rank.

**Remaining enterprise gaps:** (1) `get_analytics` still aggregates in memory (reads jobs then loops
candidates) — not cursor-paginated. (2) `sync_user_email` still streams; `uid` is now stored on
candidates (`ingestion_service.py:216`) so the prerequisite for a collection-group query exists, but the
query isn't converted. (3) Two inline paths remain in routes (`get_candidate` rich-report enrichment,
analytics) not behind services. (4) `print()`-based logging persists in routes.

**Verdict:** Genuinely enterprise-shaped now; the residue is scale (analytics/pagination) and
observability.

## 5. AI / ML Audit

The blend is sound: **65% LLM / 20% evaluator / 15% MOD-1** with a Q↔A cosine **relevance gate** that
suppresses the neural score on off-topic answers (`agent.py:558-568`). Both neural scorers discriminate
quality (evaluator EXCELLENT≈78 vs POOR≈16; MOD-1 de-leaked, Spearman 0.925).

**Fundamental correctness limit (root cause):** labels are LLM-generated and the LLM is also the
primary inference judge → metrics are **self-referential**. They prove the neural net mimics the LLM,
not that either matches human hiring judgment. **No precision/recall/F1 against human truth exists** —
the human-rating study (`human_rating_study.py`) is built and a 40-pair sheet is exported, but not yet
rated.

**Secondary:** the **candidate ranker is trained on synthetic data** — the code admits this in its
`score_quality` response string and only avoids tautology by anchoring on a *different* DevType's mean
(`generate_ranking_data.py:187`). Correctly used as a tiebreaker only. **Calibration/confidence:** MC
Dropout uncertainty exists on the evaluator but isn't surfaced to users or used to gate decisions.

## 6. Architecture Audit

Enterprise: now correctly three-tiered (routes/controllers → services → repository helpers) with
dependency direction inward and domain exceptions at the boundary — good SoC, reasonable SOLID. ML/training:
flat-but-organized (`models/`, `training/`, `recommender/`, `hr_services/`). **Main violation:**
`agent.py` and `server.py` are large multi-responsibility modules (LLM orchestration + blending + synth
+ WebSocket + persistence) — the last god-files. No overengineering observed; the new service layer is
proportionate, not gold-plated.

## 7. Code Quality Audit

Strengths: consistent naming, typed signatures, docstrings, dataclass result types in services.
Issues: `agent.py`/`server.py` size; `print()` logging across ML modules; some magic numbers remain in
`agent.py`/`server.py` (blend weights are now named in services but not everywhere); `cv_parser.py` mixes
`typing.List`/`Optional` with native generics. Dead code largely removed (`now_utc` etc. flagged
earlier). Testability: enterprise now unit-testable; `agent.py` evaluation logic still hard to test in
isolation.

## 8. Project Structure Audit

Reasonable. `hr_services/` + `models/hr_models.py` give the enterprise side a clean package shape.
Recommended tightening: move `candidate_ranker` consumers and `recommender/` under a clear `ml/` or
`inference/` boundary; split `agent.py` into `EvaluationService` + graph nodes; keep one shared embedder
module. `app.py` (legacy Streamlit) remains for reference but unused — candidate for removal.

## 9. Performance Audit

Enterprise hot paths fixed (thread offload + timeout). Remaining: **ML models load at import**
(`tone.py`/`ingest.py` pull 361 MB + 400 MB; mpnet loaded 3–4× across modules) → ~60 s startup, ~1.5 GB
wasted RAM; training **re-encodes every run** (no cache); `get_analytics` O(jobs×candidates) in memory.
Expected wins: FastAPI `lifespan` + shared embedder → seconds-fast startup, ~1 GB RAM saved; analytics
pre-compute → dashboard from 2500 reads to 1.

## 10. Security Audit

Strong overall. Secrets via env; input validation via Pydantic max-lengths; file uploads size-capped +
timed-out; auth on all admin/company routes; tenant isolation enforced; cryptographic tokens;
server-side scores; HTML-escaped emails. Gaps: `print()` logging has no PII-redaction policy and isn't
shipped anywhere; a few list endpoints (`get_analytics` internals) remain unbounded; `torch.load` on
checkpoints is trusted (acceptable for first-party files but worth `weights_only=True`).

## 11. Maintainability Audit

Markedly improved by the service extraction + Pydantic + 60 tests — onboarding and extension on the
enterprise side are now plausible. Debugging is still hampered by `print()` logging. The ML side remains
harder to extend due to god-files and import-time model loading. Technical debt is concentrated, not
pervasive.

## 12. Cross-Branch Consistency Audit

**Best result of the audit.** The historic train/inference mismatch (MiniLM-Q+A at train vs
mpnet-answer at inference) is **fixed and enforced**: training re-encodes with the inference embedder,
the checkpoint records the embedder identity, and `registry.load_evaluator` refuses a mismatched model —
so the Training output and Enterprise inference now share one feature space. **Remaining inconsistency:**
reported metrics still come from val (until the new test split is run), so "training metrics" and
"real-world performance" differ by an unknown optimism gap. Preprocessing for MOD-1 and MOD-4 is
consistent (mpnet); the ranker's feature_store path is the one place to re-verify train==inference.

## 13. Missing Features

Human-rating validation (built, not run) · held-out TEST numbers (code added, not run) · real object
storage (S3 is local disk; `MockS3` dead) · structured logging / `/metrics` / alerting · model
registry/versioning beyond `_v1.pt` filenames · drift monitoring · load testing · CD rollback strategy ·
`sync_user_email` collection-group query · analytics pre-compute.

## 14. Technical Debt

`agent.py`/`server.py` god-files · `print()` logging across ML modules · re-encode-every-run in training ·
emotion 1-fold · in-memory analytics · legacy `app.py` · ranker on synthetic data.

## 15. Critical Issues

| # | Severity | Problem | Root cause | Why it matters / impact | Recommended fix |
|---|---|---|---|---|---|
| C1 | **High** | ML metrics are self-referential | Labels + 65% judge both from one LLM | Accuracy claims unfalsifiable; weak defense | Run human study; report Spearman + Cohen's κ |
| C2 | **High** | Reported metrics from val, not test | train/val only (now code-fixed, not run) | Optimistic, overstated generalization | Re-run `train_evaluator.py`/`train_scorer.py`; extend split to all `train_*.py` |
| C3 | **Med** | Emotion model 1-fold | `break`/"time efficiency" | "5-fold CV" claim unbacked; weak multimodal | Run all 5 folds; mean±std F1 |
| C4 | **Med** | ML loads at import; local-disk storage | No `lifespan`; `MockS3` | Slow start, ~1.5 GB RAM, no durability | FastAPI lifespan + shared embedder + boto3 S3 |
| C5 | **Med** | Ranker trained on synthetic data | No real comparative labels | Scores not validated vs outcomes | Collect real pairwise labels; retrain (already flagged as tiebreaker) |
| C6 | **Low** | `print()` logging everywhere | No logging setup | Operationally blind; no redaction | `logging`/`structlog` + `/metrics` |

## 16. Recommended Refactors

Lazy-init ML registry/embedder in a FastAPI `lifespan` (one shared mpnet) · extract `EvaluationService`
from `agent.py` (synth + blend + gate) · convert `sync_user_email` to a `collection_group` query · move
`get_analytics` to a pre-computed company-stats document · replace `print()` with structured logging.

## 17. Phase-by-Phase Improvement Roadmap

**Phase 1 – Critical (defense credibility).** *Status: code done 2026-06-27.*
- Re-enable corporate-email gate ✅ · held-out test-set code ✅ · human-study sheet ✅.
- **Remaining to close:** run the two trainings for real TEST numbers; collect human ratings → `--analyze`.
- *Why first:* converts every accuracy claim from "trust me" to evidence. *Complexity: Small (compute/people).*

**Phase 2 – Architecture.** Lazy ML `lifespan` + shared embedder · split `agent.py`/`server.py` ·
`sync_user_email` collection-group query. *Removes startup pain + last cross-tenant scan. Medium.*

**Phase 3 – AI/ML.** Finish emotion 5-fold (C3) · extend 70/15/15 to all `train_*.py` · retrain ranker
on real labels when available · cache training features. *Medium. Depends on Phase 1 data discipline.*

**Phase 4 – Performance.** Pre-computed analytics doc · cursor pagination on list endpoints · embedding
cache. *Medium.*

**Phase 5 – Production.** Real S3 (C4) · structured logging + `/metrics` + alerting · CI rollback +
load test. *Medium–Large.*

**Phase 6 – Long-term.** Model registry/versioning · drift monitoring · deployment automation. *Large.*

## 18. What Should Be Done Next

- **Immediate:** Run `train_evaluator.py` + `train_scorer.py` to capture held-out TEST numbers, and
  collect human ratings. Phase 1 code is in place; these produce the defensible metrics. *(Order: this
  first because it validates the core claim before any scaling spend.)*
- **Short-term:** Lazy ML init + god-file split — biggest DX/perf relief.
- **Medium-term:** Emotion 5-fold, test-split the remaining trainers, analytics pre-compute.
- **Long-term:** Real storage, observability, registry, drift. *Prove the science is real before
  investing in infrastructure to scale it.*

## 19. Final Verdict

**Conditionally production-capable for a controlled pilot; demo-ready today.** The engineering has
matured: the enterprise branch is genuinely layered and tested, and the catastrophic train/inference
embedding bug is fixed and guarded. The blocker is **scientific, not architectural** — until the
human-rating study runs and the (now-implemented) held-out test sets are actually executed, the central
claim rests on one LLM grading another. Run the two trainings, collect the human ratings, then harden
storage/observability — and this is a credible, defensible graduation-grade system with a real path to
production.

---

*Companion documents: `AUDIT_REPORT.md` (codebase-wide status), and the Phase-1 implementation already
landed on this branch (corporate-email gate, held-out test-set code, human-study sheet).*
