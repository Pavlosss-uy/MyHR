<div align="center">

# Chapter Two

# Background

</div>

<br/>

**Chapter Outline**

- 2.1 Retrieval-Augmented Generation
- 2.2 LLM Agent Orchestration
- 2.3 Transformer Embeddings & Reranking
- 2.4 Neural Answer Scoring
- 2.5 Reinforcement Learning for Adaptive Difficulty
- 2.6 Emotion Recognition & Proctoring
- 2.7 Platform Technologies

This chapter introduces the concepts, algorithms, and technologies that MyHR is built upon. It
is intended to give the reader the background necessary to follow the system design in
Chapter 3 and the implementation in Chapter 4.

---

## 2.1 Retrieval-Augmented Generation

A **Large Language Model (LLM)** generates text by predicting the most likely continuation of
a prompt. While powerful, an LLM only "knows" what was in its training data and what is placed
in its prompt; asked about a specific candidate, it will confidently *hallucinate* details. To
ground an LLM in trustworthy, up-to-date facts, **Retrieval-Augmented Generation (RAG)** first
*retrieves* the most relevant passages from a source corpus and then *augments* the LLM's
prompt with them, so the model reasons over real evidence rather than guesses.

A retrieval system can be **sparse** or **dense**:

- **Sparse retrieval** matches exact terms. **BM25** (Best Matching 25) is the classical sparse
  ranking function; it scores a document by the frequency of the query's terms within it,
  discounted by how common those terms are across the corpus. BM25 excels at exact keyword
  overlap (e.g. a specific framework name) but misses paraphrases.
- **Dense retrieval** matches *meaning*. Each passage is encoded into a high-dimensional vector
  (an *embedding*) by a transformer model, and relevance is measured by vector similarity
  (cosine distance). Dense retrieval captures semantic similarity even when no words overlap,
  but can miss rare exact terms.

Because the two approaches have complementary strengths, modern systems **fuse** them.
**Reciprocal Rank Fusion (RRF)** combines several ranked lists into one by summing, for each
document, a score of `1 / (k + rank)` across the lists, where `k` is a smoothing constant
(commonly 60). RRF is robust because it depends only on a document's *rank* in each list, not
on incomparable raw scores. Finally, a **cross-encoder reranker** re-scores the fused
shortlist by reading the query and each candidate passage *together*, yielding the most precise
ordering at the cost of more computation — which is why it is applied only to the top fused
candidates rather than the whole corpus.

MyHR uses exactly this stack: BM25 + dense (Pinecone) retrieval, RRF with `k = 60`, and a
cross-encoder reranker, to ground each interview question in the candidate's CV and the JD.

---

## 2.2 LLM Agent Orchestration

A single LLM call is stateless. A realistic interview, however, is a *process*: rewrite the
context, retrieve evidence, check that the evidence is good enough, generate a question, accept
an answer, evaluate it, decide whether to continue, and adapt. Coordinating these steps
requires an **agent** — a controller that maintains state and routes execution between
specialized steps.

**LangGraph** models such an agent as a **state graph**: a set of *nodes* (each a function that
reads and writes a shared state object) connected by *edges*. Some edges are **conditional** —
the next node is chosen at runtime based on the current state (for example, "if the retrieved
context is insufficient, re-retrieve; otherwise generate the question"). A **checkpointer**
persists the state between turns so a long-running, multi-question interview can resume exactly
where it left off.

This graph-based formulation makes the interview logic explicit and inspectable, which is
important for a system whose outputs must be defensible. MyHR's interview agent is a LangGraph
state machine whose nodes are `rewrite`, `retrieve`, `grade`, `generate`, and `process_answer`.

---

## 2.3 Transformer Embeddings & Reranking

The quality of dense retrieval depends entirely on the embedding model. MyHR uses
**`all-mpnet-base-v2`**, a sentence-transformer that maps text to a **768-dimensional** vector.
It is a strong general-purpose semantic encoder and is used consistently at both indexing time
and query time — a deliberate choice, because using one embedder to *train* a model and a
*different* one at inference silently degrades accuracy. The same embedder is therefore used
for indexing CV/JD chunks, for the relevance gate in the scoring blend, and for re-encoding
training answers so that the trained models see the same representation they will see in
production.

A **cross-encoder** differs from the bi-encoder used for retrieval. A bi-encoder embeds the
query and the document *independently* and compares the two vectors — fast, because document
vectors can be precomputed. A cross-encoder feeds the query and document *together* through the
transformer and outputs a single relevance score — slower, but far more accurate. MyHR applies
a cross-encoder only as a final reranking step over the small fused candidate set.

---

## 2.4 Neural Answer Scoring

Relying on an LLM as the *sole* judge of an answer has a weakness: the score is an opaque
opinion of one model. MyHR therefore complements the LLM with purpose-trained neural networks:

- A **Multi-Layer Perceptron (MLP)** is a feed-forward neural network of fully connected layers
  with non-linear activations. Given a fixed-length feature vector (here, embeddings of the
  question and answer), an MLP can be trained to regress a quality score.
- A **multi-head** network shares a common representation but ends in several independent output
  "heads," each predicting a different target. MyHR's evaluator uses three heads to score an
  answer's **relevance**, **clarity**, and **depth** separately.

These models are trained with standard supervised learning and evaluated with **rank-aware
metrics** — most importantly **Spearman's rank correlation**, which measures whether the model
orders answers the same way the ground truth does (rather than matching exact values), and
**NDCG** (Normalized Discounted Cumulative Gain) for ranking quality. The final answer score is
a transparent weighted blend of the LLM judgment and these neural evaluators.

---

## 2.5 Reinforcement Learning for Adaptive Difficulty

A good interviewer adapts: if a candidate answers easily, the questions get harder; if they
struggle, the questions get easier. This is naturally framed as a **reinforcement learning
(RL)** problem, where an *agent* observes a *state* (the candidate's recent performance), takes
an *action* (choose the next question's difficulty), and receives a *reward* (a more
informative interview).

**Proximal Policy Optimization (PPO)** is a widely used, stable policy-gradient RL algorithm
that improves the policy in small, clipped steps to avoid destructive updates; **REINFORCE** is
the simpler policy-gradient baseline. MyHR's adaptive-difficulty module is trained in a
simulated interview environment to map a compact performance state to a difficulty action.

---

## 2.6 Emotion Recognition & Proctoring

Two auxiliary signals enrich the interview:

- **Emotion recognition** analyzes the candidate's facial expression and/or vocal tone to
  estimate affective state during the interview, providing context for the report.
- **Proctoring** runs silently to detect integrity issues — whether a face is present, whether
  the candidate is looking away, and whether multiple faces appear. MyHR uses **OpenCV** with
  the lightweight **YuNet** face detector for this, deliberately avoiding heavyweight
  dependencies. Proctoring observations are aggregated per answer and never shown to the
  candidate.

---

## 2.7 Platform Technologies

MyHR is assembled from established, production-grade components.

**Table 2.1 — Platform Technology Stack.**

| Layer | Technology | Role in MyHR |
|-------|-----------|--------------|
| Frontend | React 18 + Vite 5 | Single-page application (SPA) for candidates and HR |
| Frontend | Radix UI + Tailwind CSS | Accessible component library and styling |
| Frontend | React Router, TanStack Query | Routing and server-state management |
| Frontend | Recharts, Framer Motion | Analytics charts and animations |
| Backend | FastAPI (Python) | REST + WebSocket API server |
| Backend | Uvicorn | ASGI server runtime |
| AI Agent | LangGraph + LangChain | Interview agent state machine |
| LLM | Groq `llama-3.3-70b-versatile` | Question generation and answer evaluation |
| RAG | LlamaIndex + Pinecone | Dense vector index and retrieval |
| RAG | `rank_bm25` | Sparse BM25 retrieval |
| Embeddings | `sentence-transformers` (`all-mpnet-base-v2`) | 768-D text embeddings |
| Neural layer | PyTorch | Eight custom models (scoring, ranking, etc.) |
| Speech | Deepgram SDK | Speech-to-text and text-to-speech |
| Proctoring | OpenCV (YuNet) | Silent face/attention detection |
| Privacy | Microsoft Presidio | PII detection and redaction before indexing |
| Auth | Firebase Authentication | Identity and ID-token verification |
| Database | Google Cloud Firestore | Multi-tenant document persistence |
| Email | Resend API / Gmail SMTP | Invitation and notification delivery |
| Training | MLflow + TensorBoard | Experiment tracking and metrics |
| Rate limiting | SlowAPI | Per-route request throttling |

The next chapter shows how these technologies are composed into the MyHR architecture.
