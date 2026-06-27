<div align="center">

# Tools

</div>

**Table T.1 — Tools Used.**

| Category | Tool | Use in MyHR |
|----------|------|-------------|
| Language (backend) | Python 3.14 | Backend, AI engine, training |
| Language (frontend) | JavaScript (ES2022) | React SPA |
| Web framework | FastAPI + Uvicorn | REST + WebSocket API |
| Frontend build | Vite 5 | Dev server and production bundling |
| UI | React 18, Radix UI, Tailwind CSS | Component-based interface |
| Charts/UX | Recharts, Framer Motion | Analytics charts, animations |
| AI agent | LangGraph, LangChain | Interview state machine |
| LLM | Groq `llama-3.3-70b-versatile` | Question generation, answer judging |
| Vector DB | Pinecone (via LlamaIndex) | Dense retrieval |
| Sparse retrieval | `rank_bm25` | BM25 retrieval |
| Embeddings | `sentence-transformers` (`all-mpnet-base-v2`) | 768-D embeddings |
| Deep learning | PyTorch | Eight neural models |
| Speech | Deepgram SDK | STT / TTS |
| Computer vision | OpenCV (YuNet) | Silent proctoring |
| Privacy | Microsoft Presidio | PII redaction |
| Auth | Firebase Authentication | Identity, ID tokens |
| Database | Google Cloud Firestore | Persistence |
| Email | Resend API / Gmail SMTP | Invitations, notifications |
| Experiment tracking | MLflow, TensorBoard | Training metrics |
| Rate limiting | SlowAPI | Per-route throttling |
| Testing | pytest, Vitest, React Testing Library | Automated tests |
| Version control | Git / GitHub | Source management |
| IDE | Visual Studio Code | Development |

**Hardware.** Development and training used a CUDA-capable GPU workstation (the backend logs
`device_name: cuda` when loading sentence-transformer models); the system also runs on CPU.

---

<div align="center">

# References

</div>

> Books and papers first (ordered by date), then websites (with last-retrieved dates). Replace
> or extend with the exact sources cited in the final printed document.

1. A. Vaswani, N. Shazeer, N. Parmar, et al., "Attention Is All You Need," *Advances in Neural
   Information Processing Systems (NeurIPS)*, 2017.
2. S. Robertson and H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond,"
   *Foundations and Trends in Information Retrieval*, 2009.
3. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese
   BERT-Networks," *EMNLP*, 2019.
4. G. V. Cormack, C. L. A. Clarke, and S. Büttcher, "Reciprocal Rank Fusion Outperforms Condorcet
   and Individual Rank Learning Methods," *SIGIR*, 2009.
5. P. Lewis, E. Perez, A. Piktus, et al., "Retrieval-Augmented Generation for Knowledge-Intensive
   NLP Tasks," *NeurIPS*, 2020.
6. J. Schulman, F. Wolski, P. Dhariwal, A. Radford, and O. Klimov, "Proximal Policy Optimization
   Algorithms," *arXiv:1707.06347*, 2017.
7. K. Song, X. Tan, T. Qin, J. Lu, and T.-Y. Liu, "MPNet: Masked and Permuted Pre-training for
   Language Understanding," *NeurIPS*, 2020.
8. LangGraph Documentation, https://langchain-ai.github.io/langgraph/ , last retrieved
   27/06/2026.
9. FastAPI Documentation, https://fastapi.tiangolo.com/ , last retrieved 27/06/2026.
10. Pinecone Documentation, https://docs.pinecone.io/ , last retrieved 27/06/2026.
11. Groq Documentation, https://console.groq.com/docs , last retrieved 27/06/2026.
12. Firebase Documentation, https://firebase.google.com/docs , last retrieved 27/06/2026.
13. Deepgram Documentation, https://developers.deepgram.com/ , last retrieved 27/06/2026.

---

<div align="center">

# Glossary & Abbreviations

</div>

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface — the contract the backend exposes to the frontend. |
| **ATS** | Applicant Tracking System — traditional, keyword-based hiring software. |
| **BM25** | Sparse ranking function scoring documents by term overlap with the query. |
| **Bi-encoder** | Embeds query and document independently for fast similarity search. |
| **Cross-encoder** | Scores a (query, document) pair jointly for higher-precision reranking. |
| **CV** | Curriculum Vitae — a candidate's résumé. |
| **Dense retrieval** | Semantic search using vector embeddings and cosine similarity. |
| **Embedding** | A fixed-length numeric vector representing the meaning of text. |
| **JD** | Job Description. |
| **Knock-out rule** | A rubric cap that limits the score of a clearly unqualified CV. |
| **LLM** | Large Language Model. |
| **MLP** | Multi-Layer Perceptron — a feed-forward neural network. |
| **Multi-head** | A network with several output heads predicting different targets. |
| **NDCG** | Normalized Discounted Cumulative Gain — a ranking-quality metric. |
| **PII** | Personally Identifiable Information. |
| **PPO** | Proximal Policy Optimization — a reinforcement-learning algorithm. |
| **Proctoring** | Silent integrity monitoring (face presence, gaze, multiple faces). |
| **RAG** | Retrieval-Augmented Generation. |
| **RBAC** | Role-Based Access Control. |
| **Relevance gate** | A check that suppresses the neural score when an answer is off-topic. |
| **RL** | Reinforcement Learning. |
| **RRF** | Reciprocal Rank Fusion — merges several ranked lists into one. |
| **SPA** | Single-Page Application. |
| **Spearman's ρ** | Rank correlation measuring whether two orderings agree. |
| **STT / TTS** | Speech-to-Text / Text-to-Speech. |
| **WebSocket (WS)** | A persistent two-way connection used for the live interview. |

---

<div align="center">

# Appendices

</div>

## Appendix A — Environment Variable Template

```ini
# LLM & AI services
GROQ_API_KEY=
DEEPGRAM_API_KEY=
PINECONE_API_KEY=
OPENAI_API_KEY=

# Firebase (Admin SDK + web config)
FIREBASE_SERVICE_ACCOUNT_PATH=
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=

# Email transport (use one)
RESEND_API_KEY=
SMTP_USER=
SMTP_PASS=

# URLs & infrastructure
MYHR_BASE_URL=http://localhost:8080
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET_NAME=
MINIO_ENDPOINT=
REDIS_URL=
DATABASE_URL=

# Dev escape hatch (omit in production)
BYPASS_EMAIL_CHECK=
```

## Appendix B — Endpoint Index

See **Tables 4.3 and 4.4** for the complete REST/WebSocket surface (9 interview/system
endpoints in `server.py`, 20 enterprise endpoints in `hr_routes.py`).

## Appendix C — Repository Structure (selected)

```
MyHR/
├── server.py              FastAPI app, interview WebSocket, system endpoints
├── hr_routes.py           Enterprise router (jobs, CVs, invites, analytics)
├── agent.py               LangGraph interview agent + scoring blend
├── ingest.py              RAG indexing + lazy embedder
├── retriever.py           BM25 + dense + RRF + cross-encoder rerank
├── cv_parser.py           CV parsing, skill extraction, rubric scoring
├── email_service.py       Resend / Gmail SMTP transport + templates
├── firestore_client.py    Firestore helpers + role sync
├── prompts.py             LLM prompt templates
├── models/                8 neural models + registry + proctor
│   ├── registry.py
│   ├── multi_head_evaluator.py, scoring_model.py, candidate_ranker.py
│   ├── skill_matcher.py, difficulty_engine.py, emotion_model.py
│   ├── performance_predictor.py, cross_encoder_scorer.py, proctor.py
│   └── checkpoints/       Trained model weights
├── training/              Data generation, trainers, evaluation, human study
├── tests/                 pytest suite (70 tests)
├── src/                   React SPA (pages, components, contexts, hooks, lib)
└── docs/                  This documentation set
```

> **Note on auxiliary modules.** The repository also contains supporting modules not central to
> the core flow described above — for example `tone.py`, `services.py`, `s3_utils.py`,
> `feature_extractor.py`, `explainer.py`, and the `recommender/` package — as well as utility
> and demo scripts (`run_training.py`, `check_phase1.py`, `demo_phase1.py`,
> `cleanup_pinecone.py`). These are part of the codebase but are outside the primary
> request-lifecycle documented in Chapter 4.
