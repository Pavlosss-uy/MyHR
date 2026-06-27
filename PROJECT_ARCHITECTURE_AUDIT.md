# MyHR — Comprehensive Project Architecture & Logic Audit
**Date:** 2026-06-27 · **Auditor:** Claude Opus 4.8 (lead-architect review) · **Branch:** enterprise
**Evidence-based:** execution flow traced; claims verified against current code, not naming or comments.
**Companion docs:** `AUDIT_REPORT.md` (codebase status), `TRAINING_ENTERPRISE_AUDIT.md` (deep T+E audit).

> **Current-state note (verified this pass):** The corporate-email gate at `hr_routes.py:223` is
> **commented out again** (was re-enabled in Phase 1, now reverted — presumably for gmail testing).
> Both `train_evaluator.py` and `train_scorer.py` now have **70/15/15 splits with held-out TEST
> evaluation AND an embedding cache** (`_cached_encode`) — two prior findings fixed.

---

## 1. Layer-by-Layer Architecture Review

| Layer | Files | Responsibility | Verdict |
|---|---|---|---|
| API / Routes (B2B) | `hr_routes.py` | HTTP controllers; delegate to services | ✅ Correct — thin orchestrators now |
| API / Routes (interview) | `server.py` | REST + WebSocket interview protocol | ⚠️ Doing too much (routing + orchestration + persistence) |
| Services (enterprise) | `hr_services/*` | Ingestion, invitation, ranking, token logic | ✅ Clean, single-responsibility, testable |
| Services (interview) | — | *(none — logic lives in `agent.py`)* | ❌ Missing; agent.py is the de-facto service |
| Business logic | `agent.py`, `prompts.py` | LangGraph nodes, blend, synth, prompts | ⚠️ God-file; mixes graph + scoring + synthesis |
| Domain models / DTOs | `models/hr_models.py` | Pydantic request/response + entities | ✅ Enterprise only; interview side has none |
| Data access (repo) | `firestore_client.py`, `recommender/feature_store.py` | Firestore CRUD + atomic transforms; ranker features | ✅ Generic but works; lazy `get_db()` |
| RAG | `retriever.py`, `ingest.py` | BM25+dense+RRF+rerank; Pinecone ingest | ✅ Complete, 4-stage |
| AI/ML models | `models/*` | 8 model architectures + registry | ✅ Registry clean; some models synthetic/1-fold |
| Training | `training/*` | Per-model train scripts + eval | ✅ Good hygiene; test splits + cache now added |
| Auth | `server.py`, `hr_routes.py` | Firebase token verify, admin allowlist | ✅ Enforced; tenant isolation correct |
| Background tasks | `BackgroundTasks`, `asyncio.to_thread` | Email send; ML offload | ✅ Correct usage |
| Config | env vars + `ruff.toml` | Configuration | ⚠️ No central config/validation module |
| Utilities / shared | `utils/seeding.py`, `utils/trainer_logger.py`, `s3_utils.py`, `services.py`, `tone.py` | Seeds, logging, storage, STT/TTS, emotion | ⚠️ `s3_utils` is local-disk; `tone` loads model at import |
| Middleware | CORS + `slowapi` limiter | Cross-origin + rate limit | ✅ Present |
| Tests | `tests/*` | 60 passing (integration + service units) | ✅ Enterprise covered; interview/ML thin |

**Overengineering:** none material — the new service layer is proportionate. **Under-engineering:**
the interview side (`server.py` + `agent.py`) lacks the service/DTO discipline the enterprise side now
has — that's the biggest structural asymmetry.

## 2. Enterprise Layer Audit

**Design is logical and workflows are complete:** request-access → admin approval → invite → accept →
jobs → CV upload (scored) → invite-interview → complete (server-side score) → rank. Each step has auth,
ownership checks, and Pydantic validation. Data flow is correct and tenant-isolated.

**Issues:** (1) **Corporate-email gate disabled** (`hr_routes.py:223`) — anyone can request access with
a free email. (2) **`get_analytics`** aggregates in memory (reads jobs then loops candidates) — a
scalability ceiling past ~30 jobs. (3) **`sync_user_email`** streams all jobs to find one user's records
(cross-tenant reads); `uid` is now stored on candidates so a `collection_group` query is possible but
not done. (4) **`print()` logging** in routes — no observability. **No dead features** found; no hidden
bugs found in the traced flows (token expiry, ownership, atomic stats all correct).

## 3. Training Layer Audit

**Production-grade hygiene:** seeds, AdamW, CosineAnnealingLR, early stopping + best-state restore,
MLflow+TensorBoard, Spearman/F1/NDCG, embedder-stamped checkpoints, **70/15/15 with held-out TEST**
(evaluator + scorer), and a new **embedding cache** (`_cached_encode`) that fixes the re-encode-per-run
cost. **Remaining:** (1) emotion model **1-fold** (`train_emotion.py:237`); (2) the 70/15/15 + cache
pattern should propagate to `train_ranker/predictor/difficulty/skill`; (3) **resume-training not
supported** (no optimizer/epoch checkpointing — only best weights saved); (4) no mixed precision (CPU
encode dominates anyway). **Not production-ready only because** the trainings haven't been re-run to
emit the new TEST numbers, and labels remain LLM-sourced.

## 4. AI / ML Audit

Blend = **65% LLM / 20% evaluator / 15% MOD-1** with a Q↔A cosine **relevance gate** (`agent.py:558-568`).
RAG retrieval is sound (hybrid + RRF + rerank). **Core weakness (unchanged):** labels are LLM-generated
and the LLM is also the 65% inference judge → **self-referential**; no precision/recall/F1 vs human
truth (study built, not run). Ranker is **synthetic-trained** (admitted in its `score_quality` string).
**Thresholds/calibration:** the relevance gate is a sensible heuristic; MC-Dropout uncertainty exists
but isn't surfaced. **Inference perf:** ML offloaded to threads on the enterprise side; on the interview
side embeddings are computed per turn (cached) — acceptable.

## 5. Functional Audit (execution traced)

- **Interview completion** (`/candidate-interview/{token}/complete`): traced — reads score from
  server-side report on disk, ignores client; 409 if no report. ✅ Correct, not forgeable.
- **CV upload**: traced through `CandidateIngestionService._process_single` — size guard → hash dedup →
  threaded extract w/ timeout → validate → S3 → score → email dedup → persist → atomic stats. ✅
- **Ranking**: `RankingService.rank` skips candidates whose sessions can't load, offloads torch. ✅
- **Edge cases handled:** duplicate CVs (hash + email), expired/used tokens, missing report, no
  completed candidates. **Race conditions:** job-stats now transactional ✅; **but** `invite-interview`
  and `complete` do separate read→write on candidate status (low-risk, single-actor).
- **State inconsistency risk:** `interviewed` count increments on complete but isn't reconciled if a
  report is regenerated — minor.

## 6. Logic Audit

No circular dependencies found (services depend on repo helpers, not routes). **Redundant logic
removed** (expiry check centralized; skills no longer double-extracted in scorer). **Remaining
duplication:** token-expiry validation exists in both `InvitationService.validate_token_expiry` and
`TokenService._validate_expiry` (two near-identical copies across services) — should be one shared util.
**Hidden complexity:** `agent.py` blend + synth + gate in one module. **Under-engineering:** interview
side has no DTO layer.

## 7. Code Quality Audit

Readable, typed, documented; dataclass result types in services. **DRY:** one cross-service expiry
duplication (above). **KISS:** good. **Naming:** clear. **Large files:** `agent.py`, `server.py`.
**Magic values:** mostly named in services now; some remain in `agent.py`/`server.py`. **Dead code:**
legacy `app.py` (Streamlit) unused; `cross_encoder` retired but present. **Mixed typing styles** in
`cv_parser.py` (`typing.List` vs native).

## 8. Security Audit

Strong: Firebase token auth, admin allowlist, tenant isolation (`_get_authorized_job`), cryptographic
tokens, server-side-only scores, HTML-escaped emails, file-size guards, rate limits, Pydantic input
caps. **Gaps:** (1) corporate-email gate **off** (`hr_routes.py:223`); (2) `print()` logging has no
PII-redaction; (3) some internal reads unbounded; (4) `torch.load` without `weights_only=True` (first-
party files, low risk). No injection or path-traversal vectors found in traced flows.

## 9. Performance Audit

Enterprise hot paths fixed (thread offload + timeout). Training re-encode fixed (cache). **Remaining:**
(1) **ML models load at import** (`tone.py`/`ingest.py`: 361 MB + 400 MB; mpnet ×3–4) → slow start,
~1.5 GB RAM; (2) `get_analytics` O(jobs×candidates) in memory; (3) `_hybrid_cache`/retriever process-dict
can grow unbounded. **Expected wins:** lifespan + shared embedder → fast start, ~1 GB saved; analytics
pre-compute → 2500 reads → 1.

## 10. Error Handling Audit

Domain exceptions translated to HTTP codes at the route boundary (good). Service S3/semantic failures
logged + degraded gracefully. **Gaps:** `print()` not a logger; **no retry** on email send or transient
Firestore errors; no monitoring/alerting hooks; user-facing errors are reasonable HTTP details.

## 11. Dependency Audit

Direction is correct: routes → services → repo/ML; services raise domain exceptions (no FastAPI
coupling). No circular refs. **Missing abstraction:** `firestore_client` is a generic CRUD wrapper with
no collection enum/repository interface — acceptable but allows typos. ML registry is a clean singleton.

## 12. Folder Structure Audit

Good shape: `hr_services/`, `models/`, `training/`, `recommender/`, `tests/`, `utils/`. **Recommend:**
(1) delete legacy `app.py`; (2) group interview orchestration into an `interview/` package mirroring
`hr_services/`; (3) move `s3_utils.py`/`services.py`/`tone.py` under `infra/`; (4) one `config.py` for
env validation. Three audit `.md` files now exist at root — consolidate under `docs/audits/`.

## 13. Missing Features

**Critical:** human-rating validation run (built, not executed) · executed held-out TEST metrics (code
ready) · real object storage (S3 local-disk) · structured logging + monitoring.
**Important:** central config + validation · retry on email/Firestore · analytics pre-compute · emotion
5-fold · resume-training checkpoints · model registry/versioning.
**Nice to have:** drift monitoring · load testing · CD rollback · uncertainty surfaced to users ·
collection-group `sync_user_email`.

## 14. Refactoring Plan

**Phase 1 — Critical Fixes**
- *Issue:* email gate disabled. *Why critical:* anyone gets enterprise access. *Impact:* B2B trust.
  *Solution:* uncomment with `BYPASS_EMAIL_CHECK` env (keep dev override).
- *Issue:* metrics not yet from TEST / human study not run. *Why critical:* core claim unproven.
  *Impact:* defense credibility. *Solution:* run both trainers; collect ratings → `--analyze`.

**Phase 2 — Architecture Improvements**
- Extract `EvaluationService` from `agent.py` (blend+synth+gate). *Impact:* testable scoring.
- Lazy ML init via FastAPI `lifespan` + one shared embedder. *Impact:* fast start, ~1 GB saved.
- Unify the two token-expiry helpers into one shared util. *Impact:* DRY in security path.

**Phase 3 — AI / ML Improvements**
- Emotion 5-fold. *Benefit:* real CV result.
- Propagate 70/15/15 + cache to remaining `train_*.py`. *Benefit:* honest, fast retrains.
- Retrain ranker on real comparative labels. *Benefit:* validated, not synthetic.

**Phase 4 — Performance & Scalability**
- Pre-computed analytics doc · cursor pagination · bound `_hybrid_cache` (LRU).

**Phase 5 — Code Quality & Maintainability**
- Replace `print()` with structured logging · central `config.py` · delete `app.py` · consolidate audit
  docs · modernize `cv_parser` typing.

## 15. Task Breakdown (for parallel developers, minimal merge conflict)

| ID | Task | Files | Deps | Complexity | Parallel? | Blocks |
|---|---|---|---|---|---|---|
| A1 | Re-enable email gate | `hr_routes.py` | — | S | Yes | — |
| A2 | Run train_evaluator + train_scorer → TEST numbers | `training/*` (run) | — | S | Yes | — |
| A3 | Collect human ratings → `--analyze` | `data/human_ratings/` | — | S (people) | Yes | — |
| B1 | Lazy ML `lifespan` + shared embedder | `server.py`, `tone.py`, `ingest.py`, `models/registry.py` | — | M | No (touches server) | C1 |
| B2 | Extract `EvaluationService` | `agent.py` (+ new `interview/`) | — | L | No (agent.py) | — |
| B3 | Unify token-expiry util | `hr_services/*` | — | S | Yes | — |
| C1 | Pre-computed analytics doc | `hr_routes.py`, `firestore_client.py` | B1 opt | M | Partial | — |
| C2 | Structured logging | all backend | — | M | Partial (many files) | — |
| C3 | central `config.py` + delete `app.py` | new + `app.py` | — | S | Yes | — |
| D1 | Emotion 5-fold | `training/train_emotion.py` | — | M | Yes | — |
| D2 | 70/15/15+cache to remaining trainers | `training/train_{ranker,predictor,difficulty,skill}.py` | — | M | Yes | — |

**Sequential (same hot files):** B1 → C1 (both touch server/firestore); B2 alone owns `agent.py`.
**Parallel-safe together:** A1, A2, A3, B3, C3, D1, D2 (disjoint files).
**Independent:** A2/A3 (run-only, no code conflict), D1/D2 (training scripts).

## 16. Final Report

**Executive Summary:** A genuinely capable, now-layered AI-interview platform. Enterprise branch is
service-oriented, validated, and tested; the neural layer is real and guarded; RAG is complete. The
gating weakness is scientific validation (self-referential metrics; TEST numbers + human study not yet
produced) plus production hardening (storage, observability, lazy ML). One regression to note: the
corporate-email gate is currently disabled.

| Dimension | Score /10 |
|---|---|
| Overall project health | 6.5 |
| Architecture | 6.5 |
| Code quality | 7.0 |
| AI/ML | 5.0 |
| Enterprise | 7.0 |
| Training | 6.5 |
| Security | 6.5 |
| Performance | 5.5 |
| Production readiness | 5.0 |

**Strengths:** layered+tested enterprise module; fixed+guarded train/inference embedding; complete RAG;
solid auth/tenant isolation/score-integrity; pro training hygiene with test splits + caching now in.

**Weaknesses:** self-referential ML validation; email gate off; `agent.py`/`server.py` god-files;
ML loads at import; local-disk storage; `print()` logging; emotion 1-fold.

**Critical risks:** (1) accuracy claims unfalsifiable until human study + TEST runs; (2) open enterprise
signup via free email; (3) no durable storage / observability for production incidents.

**Recommended immediate actions:** re-enable the email gate (A1); run the two trainers for TEST metrics
(A2); collect human ratings (A3). All three are small and unblock the core credibility story.

**Long-term improvements:** lazy ML init + EvaluationService extraction; real S3 + structured logging +
monitoring; emotion 5-fold + ranker real labels; analytics pre-compute + pagination; model
registry/versioning + drift monitoring.

**Final verdict:** Demo-ready and architecturally sound; close the scientific-validation gap (Phase 1)
and the email-gate regression, then harden storage/observability for a credible production pilot.

---

*Generated by Claude Code — claude-opus-4-8 — 2026-06-27.*
