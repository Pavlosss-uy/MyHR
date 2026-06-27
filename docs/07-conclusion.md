<div align="center">

# Chapter Seven

# Conclusion and Future Work

</div>

<br/>

**Chapter Outline**

- 7.1 Conclusion
- 7.2 Known Limitations
- 7.3 Future Work

---

## 7.1 Conclusion

MyHR set out to automate the two most repetitive stages of hiring — CV screening and
first-round interviewing — without sacrificing trustworthiness, and it achieves that goal as a
working, end-to-end system.

The project delivers three cooperating subsystems that function together: a **hybrid RAG layer**
that grounds every interview question in the candidate's own CV and the job description using
BM25, dense Pinecone retrieval, Reciprocal Rank Fusion, and cross-encoder reranking; a
**LangGraph LLM agent** that conducts an adaptive, voice-or-text interview and evaluates answers
through a transparent blend of an LLM judgment and purpose-trained neural models (65% LLM /
20% evaluator / 15% deep scorer, with a relevance gate); and a **neural layer of eight PyTorch
models** trained with professional hygiene — fixed seeds, early stopping, experiment tracking,
and reporting on held-out test sets — that reach Spearman correlations around 0.93–0.95 against
their reference labels.

Around this AI core, the system provides a complete **multi-tenant enterprise platform**:
Firebase-backed authentication, role-based access control that cleanly separates candidates from
HR users, batch CV upload with neural skill matching and rubric scoring, email-delivered
token-based interview invitations, server-side-only scoring that candidates cannot tamper with,
and a pre-computed analytics dashboard. The frontend is a polished React single-page
application, the backend a well-structured FastAPI service, and the whole is covered by an
automated test suite (70 passing backend tests) and this documentation.

In short, MyHR demonstrates that a grounded, neural-cross-checked AI interviewer can be embedded
in a real, secure, multi-tenant hiring product — and that the result is both demonstrable and
maintainable.

**Principal achievements**

- A grounded, adaptive AI interview engine with transparent, defensible scoring.
- Automated CV screening with neural skill matching and a rubric with a knock-out rule.
- A secure, multi-tenant enterprise portal with RBAC and token-based invitations.
- Eight neural models trained and evaluated on held-out test sets with experiment tracking.
- A clean separation of enterprise, interview-AI, and training layers, with automated tests.

---

## 7.2 Known Limitations

The system is demo-ready and architecturally healthy. A few areas are deliberately scoped for
future hardening rather than the graduation milestone:

- **Validation breadth.** Answer-quality labels and the primary judge both originate from an
  LLM, so the reported metrics demonstrate strong agreement with that judge; the human-rating
  validation study, while positive (Spearman ≈ 0.95), currently uses a single rater and would
  benefit from several raters for inter-rater reliability.
- **Candidate ranker data.** The neural candidate ranker is trained on synthetically generated
  comparative data, so its scores are best used as a *tiebreaker* alongside the rubric and
  interview scores rather than an absolute measure. The code already treats it this way.
- **Object storage.** Media and reports are stored against local disk and a MinIO/S3
  configuration rather than a hardened, durable cloud bucket.
- **Observability.** The backend exposes a health endpoint, an in-process metrics endpoint, and
  structured logging, but does not yet include full production monitoring, alerting, or
  distributed tracing.

None of these affects the demonstrated functionality; each is a natural next step toward a
production deployment.

---

## 7.3 Future Work

The following improvements would extend MyHR from a strong graduation system toward a
production-grade product:

- **Multi-rater validation.** Extend the human-rating study to several independent raters and
  report inter-rater reliability alongside the system-vs-human correlation.
- **Real comparative labels for ranking.** Retrain the candidate ranker on real hiring outcomes
  (e.g. which candidates were advanced or hired) to make its scores absolute rather than
  relative.
- **Durable object storage.** Replace the local-disk path with a hardened cloud object store
  for CVs, audio, and reports, with lifecycle and access policies.
- **Production observability.** Add metrics dashboards, alerting, request tracing, and model
  drift monitoring so quality regressions are caught automatically.
- **Model registry and versioning.** Promote the file-based checkpoints to a versioned model
  registry with rollback, so model updates are auditable and reversible.
- **Scaling and load testing.** Benchmark the interview WebSocket and batch upload paths under
  load, and introduce horizontal scaling and a continuous-delivery rollback strategy.
- **Richer analytics and fairness reporting.** Surface the existing fairness-audit harness in
  the dashboard and expand analytics with funnel and time-to-hire metrics.

Pursued in this order, these items would close the gap between the current, defensible
demonstration and a system ready for open enterprise use.
