<div align="center" id="ch6">

# Chapter Six

# Results & Discussion

</div>

<br/>

**Chapter Outline**

- 6.1 Model Results (Held-Out Test Sets)
- 6.2 RAG & Grounding Results
- 6.3 System & Backend Performance
- 6.4 Enterprise Funnel Results
- 6.5 Strengths
- 6.6 Weaknesses
- 6.7 Lessons Learned

This chapter reports the measured outcomes of the project and discusses what they mean. Model
metrics are reported on **held-out test folds** (the fold used neither for training nor for
early-stopping), so they reflect generalization rather than memorization.

---

## 6.1 Model Results (Held-Out Test Sets)

The neural layer was trained with a consistent **70 / 15 / 15** train/validation/test split,
fixed random seeds, an AdamW optimizer with cosine-annealing learning rate, and early stopping
with best-state restoration. Final numbers are reported on the held-out test fold.

**Table 6.1 — Model Test-Set Metrics.**

| Model | Identifier | Primary metric | Value |
|-------|-----------|----------------|-------|
| MultiHeadEvaluator — relevance head | MOD-4 | Spearman's ρ | ≈ 0.95 |
| MultiHeadEvaluator — clarity head | MOD-4 | Spearman's ρ | ≈ 0.95 |
| MultiHeadEvaluator — depth head | MOD-4 | Spearman's ρ | ≈ 0.95 |
| CandidateScoringMLP | MOD-1 | Mean Absolute Error | ≈ 0.067 |
| CandidateScoringMLP | MOD-1 | Spearman's ρ | ≈ 0.93 |

The high Spearman correlations indicate that both models **order** answers very close to the
reference labels — which is the property that matters for ranking candidates, more than matching
an exact numeric value. The scoring MLP's low MAE (≈ 0.067 on a 0–1 scale) shows the absolute
predictions are also well-calibrated.

A **human-rating validation study** (`human_rating_study.py`) compared the system's blended
scores against human ratings on a stratified sample of answers, reporting a system-versus-human
**Spearman's ρ ≈ 0.95** and **Cohen's κ ≈ 0.50**. The strong rank correlation is encouraging;
the moderate κ reflects that exact-category agreement is harder than rank agreement, and is also
limited by the study currently using a single rater (see Chapter 7).

**Figure 6.1 — Score Distribution & Model Agreement.**

**[Add Figure: training-run plot — the evaluator's predicted-vs-reference scatter and the
blend's score-distribution histogram (export from the TensorBoard / MLflow run).]**

---

## 6.2 RAG & Grounding Results

The retrieval layer fuses BM25 (sparse) and dense (Pinecone, `all-mpnet-base-v2`) retrieval with
Reciprocal Rank Fusion (`k = 60`) and a cross-encoder reranker, evaluated with
`training/evaluate_rag.py`. Qualitatively, the most important result is the **grounding
guarantee**: because the agent retrieves CV/JD evidence *before* the LLM is prompted, generated
questions stay anchored to experience the candidate actually claimed, and the **question-to-answer
relevance gate** prevents a fluent but off-topic answer from earning the full neural score. The
gate uses the cosine similarity between the question and answer embeddings, scaled so that a
similarity of 0.5 or above counts as fully relevant — a ceiling chosen because interview answers
rarely exceed ~0.7 similarity even when excellent.

---

## 6.3 System & Backend Performance

The system meets its responsiveness objectives (NFR-5):

- **CV screening** turns a batch of uploaded CVs into a ranked shortlist in seconds. Parsing,
  skill extraction, neural skill matching, and rubric scoring run per file, and job statistics
  are updated in a single atomic Firestore transaction.
- **Analytics** are served from a pre-computed `CompanyStats` document with an in-memory
  time-to-live cache, avoiding an O(jobs × candidates) scan on every dashboard load.
- **Model loading** is lazy: the registry verifies checkpoints at startup but loads each model
  into memory only on first use, and the ~400 MB sentence-transformer embedder is initialized
  without blocking application import.
- **Graceful degradation** (NFR-6): a missing checkpoint, an unavailable MOD-1, or an absent
  MediaPipe wheel each fall back rather than crash — the scoring blend drops from 65/20/15 to
  65/35, and proctoring drops from iris tracking to head-pose.

Formal load and latency benchmarking of the interview WebSocket under concurrency was not
performed and is listed as future work (Chapter 7).

---

## 6.4 Enterprise Funnel Results

End-to-end, the platform delivers the complete hiring funnel described in the objectives: a
company can move from *requesting access* to a *ranked, interviewed shortlist* without a human
reading a single CV or conducting a single first-round interview. Each candidate's record ends
with three numbers — a CV `matchScore`, an `interviewScore`, and a combined `totalScore`
(**40% CV match + 60% interview**) — plus a synthesized `interviewReport`. Scores are computed
server-side only, so the funnel's output is defensible: a candidate cannot influence the number
that reaches the HR dashboard.

---

## 6.5 Strengths

- **Grounded by construction.** Every question is retrieved-then-generated, so the interviewer
  cannot interrogate experience the candidate never claimed.
- **Transparent, multi-signal scoring.** The 65/20/15 blend plus relevance gate is explainable
  and resists the most common gaming strategy (off-topic fluency).
- **Defensible and secure.** Server-side-only scoring, Firebase-verified ID tokens, invitation-only
  HR role, tenant isolation, PII redaction, and prompt-injection sanitization.
- **Rigorously trained models.** Held-out evaluation, consistent embedder, experiment tracking,
  and a human-rating study give the metrics credibility.
- **Clean architecture.** Three well-separated layers, 32 documented endpoints, 70 automated
  tests, and Docker packaging.
- **Robust candidate experience.** Voice-native interview with a usability-tuned, anti-cheat
  recording state machine.

## 6.6 Weaknesses

These are scoped for hardening rather than the graduation milestone, and are revisited in
Chapter 7:

- **Validation breadth.** Answer-quality labels and the primary judge both originate from an
  LLM, and the human study uses a single rater — strong agreement is shown, but broader,
  multi-rater validation would strengthen the claim.
- **Candidate-ranker data.** The neural candidate ranker is trained on synthetically generated
  comparative data, so it is used as a *tiebreaker* alongside the rubric and interview scores
  rather than an absolute measure (the code already treats it this way).
- **Storage & observability.** Media/reports use local disk and a MinIO/S3 configuration rather
  than a hardened cloud bucket, and observability is limited to a health endpoint, an in-process
  metrics endpoint, and structured logging.
- **No load testing.** Behaviour under concurrent interviews and large uploads has not been
  benchmarked.

**Table 6.2 — System Strengths and Weaknesses (Summary).**

| Aspect | Strength | Weakness / Limitation |
|--------|----------|----------------------|
| Grounding | Retrieve-then-generate; relevance gate | — |
| Scoring | Transparent 65/20/15 blend | LLM-origin labels; single-rater human study |
| Ranking | Neural + rubric + interview | Ranker on synthetic data (tiebreaker only) |
| Security | Server-side scoring, RBAC, PII redaction | Full pen-testing not performed |
| Storage | Works locally / MinIO | Not a hardened durable cloud bucket |
| Observability | Health + metrics + logs | No tracing/alerting/drift monitoring |
| Performance | Fast screening, cached analytics | No formal load/latency benchmarks |

## 6.7 Lessons Learned

- **Grounding beats raw model size.** The single highest-leverage design decision was forcing
  retrieval before generation; it did more for answer quality than any prompt tuning.
- **One embedder, everywhere.** Using the same `all-mpnet-base-v2` encoder at training and
  inference avoided a class of silent accuracy regressions; stamping checkpoints with the
  embedder identity made mismatches detectable.
- **Silence is ambiguous.** In a voice interview, "the candidate stopped talking" is not the
  same as "the candidate is finished," and conflating them produced the worst usability bug;
  separating the two states (with a cancellable submission countdown) fixed it.
- **Defensibility is an architecture property, not a feature.** Keeping all scoring server-side
  and all role grants invitation-based meant trust did not have to be retrofitted later.
