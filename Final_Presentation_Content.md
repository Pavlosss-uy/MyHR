# MyHR — Final Graduation Project Presentation
## Complete Slide Content + Team Briefings

---

## SLIDE 1 — Title Slide

**On Slide:**
```
MyHR
AI-Powered Autonomous Interview System
Intelligent Candidate Evaluation Through Multi-Modal Deep Learning

Final Graduation Project — Discussion
Team #16

Presented by: Remon Osama · Mina Mosaad · Michael Ehab · John Mahfouz · Pavlos Usama
Supervisors: Dr. Mohammed Mabrouk · T.A Manar Shaaban
```

---

### Team Briefing — Slide 1

> **Non-technical:** This is your opening. Walk in confidently. You built a full AI system that interviews candidates automatically — no human needed. That's impressive. Own it from the first second.

> **Technical:** The project title tells the committee everything: autonomous (no human in the loop), multi-modal (audio + text + structured features), and deep learning (neural networks, fine-tuned transformers). Be ready to define all three if asked.

---

## SLIDE 2 — Agenda

**On Slide:**
```
Today's Agenda

1.  Introduction & Motivation
2.  Problem Definition
3.  Objective
4.  System Architecture
5.  Development Phases (Scientific Basis)
6.  Datasets & Training
7.  Experimental Results
8.  Live Demo
9.  Conclusion & Future Work
10. References
```

---

### Team Briefing — Slide 2

> **Non-technical:** The agenda slide signals to the committee that you are organized and know what you're doing. Don't rush through it — read each point clearly.

> **Technical:** The structure follows the CS-GP final seminar format exactly: What/Why → How → What's Done → What's Next. This shows methodological awareness.

---

## SLIDE 3 — Introduction: What is MyHR?

**On Slide:**
```
What is MyHR?

MyHR is an end-to-end AI platform that autonomously conducts
technical job interviews without human involvement.

A candidate uploads their CV.
The system reads it, generates personalized questions,
listens to their answers, evaluates them in real-time,
and produces a detailed hiring report — automatically.

[Icon flow: CV Upload → AI Interviewer → Voice Analysis → Score → Report]
```

---

### Team Briefing — Slide 3

> **Non-technical:** Imagine applying for a job and instead of waiting weeks for an HR person to call you, the system immediately starts an interview, asks questions based specifically on YOUR CV, listens to how you answer, and gives you a full report within minutes. That's what MyHR does.

> **Technical:** MyHR is a pipeline system. Each module feeds the next: CV ingestion feeds the RAG retriever → the LangGraph engine orchestrates the interview → Wav2Vec2 analyzes audio → the neural evaluator + LLM judge score each answer → a synthesis module generates the final report. The full flow is stateful and tracked via WebSocket + PostgreSQL.

> **Likely question:** "What makes this different from a chatbot?" — Answer: A chatbot is stateless and generic. MyHR maintains full interview state, adapts difficulty using reinforcement learning, evaluates via three independent signals (feature vector + neural network + LLM), and analyzes voice confidence. It's a system, not a conversation wrapper.

---

## SLIDE 4 — Problem Definition & Motivation

**On Slide:**
```
The Problem

Traditional technical interviews are broken:

  Expensive      → Senior engineers spend 5–10 hours per candidate
  Inconsistent   → Same candidate gets different scores from different interviewers
  Biased         → Gender, accent, appearance affect outcomes unconsciously
  Slow           → Average hiring cycle: 23 days
  Non-scalable   → A company with 500 applicants cannot interview all of them

Candidate feedback is vague and non-actionable.
HR teams have no comparable, quantitative data across candidates.
```

---

### Team Briefing — Slide 4

> **Non-technical:** Think about how unfair interviews can be. Two people interview the same candidate and give completely different scores — not because the candidate changed, but because the interviewers are different humans. Add the time and cost of pulling your best engineers away from work to do interviews, and you have a broken process. MyHR fixes all of this.

> **Technical:** The core problem is threefold:
> 1. **Inter-rater reliability** — Human interviewers have low agreement (κ < 0.5 in studies). MyHR replaces subjective judgment with deterministic, reproducible scoring.
> 2. **Scalability** — O(n) human hours for n candidates becomes O(1) compute cost per candidate.
> 3. **Feedback quality** — MyHR produces structured, SHAP-explainable feedback, not a vague "needs improvement."

> **Likely question:** "Isn't AI also biased?" — Answer: Yes, and we address it. We use Llama 3.3-70B as a judge with a structured rubric that evaluates content, not style or accent. The Wav2Vec2 model analyzes confidence patterns, not demographic markers. SHAP explainability allows auditing of every decision.

---

## SLIDE 5 — Objective

**On Slide:**
```
Our Objective

Build an autonomous AI interviewer that:

  Conducts    → Asks adaptive, CV-grounded questions in real-time
  Transcribes → Converts speech to text via Deepgram WebSocket (real-time STT)
  Evaluates   → Blends neural + LLM signals with voice confidence
  Reports     → Generates structured, explainable hiring recommendations

Three pillars:
  Autonomous AI   |   Scientific Models   |   Actionable Delivery
```

---

### Team Briefing — Slide 5

> **Non-technical:** The objective is simple to say: build a system that does everything a human interviewer does, but faster, cheaper, fairer, and with written proof of every decision. The "three pillars" frame how we achieved it — we built the AI, we used proven scientific models, and we made the output actually useful.

> **Technical:** The objective maps directly to the five phases:
> - Conduct = Phase 2 (LangGraph orchestration) + Phase 1 (RAG for question grounding)
> - Transcribe = Deepgram WebSocket real-time STT integrated in the FastAPI backend
> - Evaluate = Phase 3 (multi-signal evaluation) + Phase 4 (Wav2Vec2 tone)
> - Report = Phase 5 (LLM synthesis + SHAP waterfall plots)

> **Likely question:** "Why not just use ChatGPT for the whole thing?" — Answer: A single LLM cannot reliably do skill matching (it hallucinates), cannot analyze raw audio, cannot maintain provably consistent scores (it fluctuates), and cannot run RL-based adaptive difficulty. We use Llama 3.3-70B only where it excels — language reasoning — and purpose-built models everywhere else.

---

## SLIDE 6 — System Architecture

**On Slide:**
```
System Architecture — 3-Tier Design

TIER 1 — PRESENTATION LAYER (React/Vite)
  Candidate Portal: Home · Profile · Interviews
  HR Dashboard: Analytics · Job Management · Candidate Profiles

TIER 2 — APPLICATION LAYER (FastAPI)
  Authentication · CV Processing · Job Description Processing
  Interview Engine · AI Models Integration · Report Generator
  Communication: HTTP REST + WebSocket (Bearer token auth)

TIER 3 — DATA LAYER
  PostgreSQL (normalized) via SQLAlchemy ORM + Alembic Migrations
  CV Storage: AWS S3
  Vector & Semantic Search: Pinecone + BM25
```

---

### Team Briefing — Slide 6

> **Non-technical:** Think of MyHR as a three-floor building. The first floor is what users see — the website. The second floor is the brain — where all the AI processing happens. The third floor is the storage — where everything is saved. They communicate with each other through secure channels.

> **Technical:** The architecture is a standard three-tier MVC-style separation. Key design decisions:
> - **FastAPI** was chosen over Flask for native async support (needed for WebSocket real-time STT) and automatic OpenAPI docs.
> - **PostgreSQL with SQLAlchemy ORM** ensures ACID compliance for interview state and evaluation records.
> - **Alembic** manages schema migrations so the database evolves safely.
> - **S3 for CV storage** decouples binary files from the relational schema — the DB stores only the S3 URL.
> - **Pinecone** is the vector database for semantic search over CV chunks; BM25 runs locally for sparse retrieval.
> - **WebSocket** is used for real-time bidirectional communication during the interview (audio streaming + response streaming).

> **Likely question:** "Why FastAPI over Django?" — Answer: Django is full-stack and opinionated, adding overhead we don't need. FastAPI is lightweight, async-native (critical for WebSocket + concurrent LLM calls), and has automatic Pydantic validation which we use extensively for structured LLM output.

---

## SLIDE 7 — Phase 1: RAG Pipeline

**On Slide:**
```
Phase 1 — Retrieval-Augmented Generation (RAG)

Why RAG?
Questions must be grounded in THIS candidate's CV and THIS job description
— not generic knowledge the LLM memorized during training.

Pipeline:
  Step 1 → Chunking         SentenceSplitter — splits CV into coherent semantic chunks
  Step 2 → Dense Retrieval  all-mpnet-base-v2 — finds semantically similar passages
  Step 3 → Sparse Retrieval BM25 — keyword-based exact term matching
  Step 4 → Fusion           Reciprocal Rank Fusion (RRF) — combines both ranked lists
  Step 5 → Reranking        ms-marco-MiniLM-L-12-v2 — selects final top-3 chunks

Output: 3 most relevant CV/JD chunks passed as context to the question generator

Scientific Basis: RRF (Cormack et al., 2009) consistently outperforms
single-system retrieval on TREC. Two-stage retrieve-then-rerank
is the established MS MARCO paradigm.
```

---

### Team Briefing — Slide 7

> **Non-technical:** When the AI needs to ask you a question, it doesn't just make something up. It actually reads your CV, finds the most relevant parts (your Python experience, your last internship, etc.), and uses those specific details to form the question. This is why MyHR asks "I see you used FastAPI in your internship — can you explain how you handled async requests?" instead of a generic "Tell me about Python."

> **Technical:** RAG prevents hallucination by grounding generation in retrieved context. Our pipeline is a two-stage retrieve-then-rerank approach, which is the established paradigm from MS MARCO benchmarks.
> - **SentenceSplitter** preserves sentence boundaries so chunks are semantically coherent, not cut mid-sentence.
> - **all-mpnet-base-v2** (sentence-transformers) maps text to 768-dim dense vectors. We store these in Pinecone and query with cosine similarity.
> - **BM25** (sparse, keyword-based) handles exact technical terms like "React 18" or "PostgreSQL" that dense models might miss.
> - **RRF (Cormack et al., 2009):** score = Σ 1/(k + rank_i) where k=60. It's parameter-light and consistently outperforms single-system retrieval on TREC benchmarks.
> - **ms-marco-MiniLM-L-12-v2** is a cross-encoder (it sees query + passage together), giving much more accurate relevance scores than bi-encoders at the cost of speed — acceptable since we rerank only top-20 candidates.

> **Likely question:** "Why not just embed the whole CV?" — Answer: LLM context windows have limits and attention degrades over long inputs. Chunking + retrieval gives us targeted, high-signal context every time.

> **Likely question:** "What is the difference between dense and sparse retrieval?" — Answer: Dense (MPNet) captures semantic similarity — "Python developer" matches "software engineer who codes in Python." Sparse (BM25) captures exact keyword overlap — it will reliably find "Python" if the CV says "Python." RRF gives us both benefits.

---

## SLIDE 8 — Phase 2: LangGraph Interview Engine

**On Slide:**
```
Phase 2 — LangGraph Interview Orchestration

Architecture: Directed Stateful Graph
  rewrite_query → retrieve → grade_context → generate_question
                    ↑________________________| (retry ≤ 2 if context not relevant)

3 Question Generation Modes:
  first_question   CV-specific opener, < 35 words, sets the tone
  normal (CoT)     Calibrated reaction + follow-up, avoids already-asked/failed topics
  fallback          Simplified drill-down question after weak answers

Adaptive Difficulty Engine — REINFORCE Policy Network:
  Observation: [avg_score, trend, current_difficulty, engagement,
                topic_diversity, questions_remaining]
  Network: 6 → 16 → 5 difficulty levels
  Updates complexity dynamically after every answer

Termination Logic:
  Hard cap:            8 questions
  Early-stop positive: last-5 average ≥ 78
  Early-stop negative: average < 35 OR 4+ failed topics
```

---

### Team Briefing — Slide 8

> **Non-technical:** The interview engine is the "brain" that decides what question to ask next. It's not a fixed list of questions. It watches how you're doing and adjusts. If you're answering everything perfectly, it makes questions harder. If you're struggling, it simplifies to give you a fair chance. It also remembers what it already asked so it never repeats itself.

> **Technical:** LangGraph implements a directed graph where each node is a processing function and edges are conditional. State is a TypedDict that persists across turns. Key design choices:
> - The **retry loop** (≤2 retries) in the graph handles cases where retrieved context is irrelevant — it rewrites the query and retrieves again before generating a question.
> - **Chain-of-Thought (CoT)** in the normal mode prompts the LLM to reason step-by-step before generating the follow-up, which improves question quality and relevance.
> - The **REINFORCE policy network** is a policy-gradient RL algorithm. The reward signal is derived from candidate performance (blended evaluation scores). The policy maps the 6-D observation to a probability distribution over 5 difficulty levels (softmax output), and action selection is sampled from that distribution. The network updates its weights to maximize expected cumulative reward.
> - **Termination logic** prevents both waste (early-stop positive) and candidate distress (early-stop negative at <35 average or 4+ failed topics).

> **Likely question:** "Why LangGraph instead of a simple loop?" — Answer: A loop can't represent conditional branching, retry logic, and state persistence cleanly. LangGraph gives us a visual, debuggable, production-ready state machine with checkpointing. If the interview crashes mid-session, state can be restored.

> **Likely question:** "What is REINFORCE?" — Answer: It's a policy gradient reinforcement learning algorithm (Williams, 1992). The agent (our difficulty controller) takes an action (choose difficulty level), observes a reward (candidate score), and updates the policy network to take better actions in similar states in the future. It's model-free — it learns purely from experience, no environment model needed. The update rule is: θ ← θ + α · ∇log π(a|s) · R(t).

---

## SLIDE 9 — Phase 3: Multi-Modal Answer Evaluation

**On Slide:**
```
Phase 3 — Multi-Signal Answer Evaluation

Three independent signals blended per answer:

Signal 1 — 8-Dimensional Feature Vector
  Skill Match · Relevance · Clarity · Technical Depth
  Confidence · Consistency · Gap Coverage · Experience

Signal 2 — Multi-Head Neural Evaluator (PyTorch)
  Backbone: Linear(8→256) → ReLU → Dropout → Linear(256→128) → Linear(128→64)
  3 Heads: Relevance · Clarity · Technical Depth (each scored 0–100)
  MC Dropout (10 forward passes) → per-head uncertainty estimate

Signal 3 — LLM-as-a-Judge (Llama 3.3-70B via Groq)
  Pydantic-enforced structured output
  Returns: score · classification · feedback · criteria breakdown
  Classifications: STRONG / PARTIAL / WEAK / I_DONT_KNOW / OFF_TOPIC

Adaptive Blending:
  Nominal:              80% LLM + 20% Neural
  Neural uncertainty:   93% LLM +  7% Neural
  Large divergence:     88% LLM + 12% Neural

Explainability: SHAP KernelExplainer — waterfall plot per session
```

---

### Team Briefing — Slide 9

> **Non-technical:** Imagine three judges scoring the same answer and then combining their scores intelligently. Judge 1 is a checklist (did they mention the right skills?). Judge 2 is a trained neural network that learned from thousands of examples. Judge 3 is a large language model that reads the answer and gives detailed feedback like a human expert. If the three judges mostly agree, we trust all of them. If they disagree, we trust the most reliable one more. And for every score, we can show exactly WHY that score was given.

> **Technical:**
> - **Signal 1 (8-D feature vector):** Each dimension is computed deterministically. Skill Match uses the Siamese network (MPNet encoder + MLP projection head trained on Stack Overflow data). Confidence comes directly from the Wav2Vec2 emotion classifier output. This vector is the input to the neural evaluator.
> - **Signal 2 (Multi-Head MLP):** Three independent linear heads sharing the same backbone. Each head is a separate regression output (0–100). MC Dropout keeps dropout active during inference and runs 10 forward passes — the variance across passes is the uncertainty estimate. High variance → the model is unsure → we trust the LLM judge more.
> - **Signal 3 (LLM-as-a-Judge):** We use Pydantic BaseModel to enforce structured output from Llama 3.3-70B. The LLM cannot return free text — it must return a valid JSON matching our schema. This is critical for reliability.
> - **Adaptive blending:** The blending weights are conditioned on two signals: (a) neural uncertainty (MC Dropout variance) and (b) divergence between LLM score and neural score. When the neural model is uncertain (score near 50 with high variance) or when LLM and neural disagree by >20 points, we up-weight the LLM.
> - **SHAP:** KernelExplainer treats the neural evaluator as a black box and uses Shapley values (cooperative game theory) to assign each of the 8 input features a contribution to the output. The waterfall plot shows HR managers exactly which features drove a candidate's score.

> **Likely question:** "Why three signals instead of just using the LLM?" — Answer: The LLM alone produces fluctuating scores (72% human match in our baseline tests). The neural model provides deterministic, reproducible scoring. The feature vector captures domain-specific signals like skill match that the LLM cannot reliably compute. Blending all three gives us 87% human match with 100% consistency.

> **Likely question:** "What is Monte Carlo Dropout?" — Answer: Normally, dropout is turned off during inference. MC Dropout keeps it active, so each forward pass randomly disables different neurons — producing a slightly different output each time. Running 10 passes and computing the variance gives us a proxy for model uncertainty without training a separate uncertainty model.

---

## SLIDE 10 — Phase 4: Voice Tone & Emotion Analysis

**On Slide:**
```
Phase 4 — Voice Tone & Emotion Classification

Why tone matters:
A technically correct but uncertain-sounding answer is qualitatively
different from a confident one — and hiring decisions reflect this.

Model: Fine-Tuned Wav2Vec2 (wav2vec2-base-superb-er)

Architecture:
  Audio (16kHz mono) → Wav2Vec2 Feature Extractor → Frozen Transformer Encoder
  → Mean Pooling [batch, 768]
  → Dense(768→256) + LayerNorm + GELU + Dropout
  → Dense(256→128) + LayerNorm + GELU + Dropout
  → Dense(128→8) → Softmax (8-class output)

8 Emotion Classes:
  Confident · Hesitant · Nervous · Engaged · Neutral
  Frustrated · Enthusiastic · Uncertain

Audio Support: WebM/Opus/MP4 (via PyAV) + WAV/MP3/FLAC fallback (librosa)

Integration:
  Confidence score → Feature #5 in evaluation vector
  LLM rubric: +3 to +6 score lift for positive confidence signals
  Per-turn tone → aggregated into report pie chart
```

---

### Team Briefing — Slide 10

> **Non-technical:** When you speak, it's not just what you say — it's how you say it. MyHR listens to your voice and detects whether you sound confident, nervous, hesitant, or enthusiastic. A candidate who says the right answer but sounds terrified might still need coaching. A candidate who sounds enthusiastic and engaged gets a slight score boost. This is how real human interviewers think — we just made it measurable.

> **Technical:** Wav2Vec2 is a self-supervised speech representation model (Baevski et al., 2020). We used `wav2vec2-base-superb-er` as the backbone and fine-tuned the classification head on RAVDESS + CREMA-D datasets:
> - **RAVDESS** (Ryerson Audio-Visual Database): ~1,440 audio clips, 8 emotions, professional actors.
> - **CREMA-D**: ~7,440 clips, diverse actors across ethnicity/age, 6 base emotions.
> - We merged and remapped to our 8 target classes, totaling ~8,800 samples.
> - The Wav2Vec2 transformer encoder is **frozen** — we only train the classification head. This is transfer learning: the pretrained encoder already learned powerful speech representations from 960 hours of LibriSpeech audio; we just teach it our classification task.
> - Mean pooling over the time dimension collapses variable-length audio into a fixed 768-dim vector.
> - GELU activation (vs. ReLU) is used because it's smoother and performs better on audio tasks empirically.
> - The confidence score (probability of "confident" class) feeds directly into feature dimension #5 of the 8-D evaluation vector.

> **Likely question:** "Why Wav2Vec2 instead of extracting MFCCs?" — Answer: MFCCs are handcrafted features that lose temporal and prosodic information. Wav2Vec2 learns representations directly from raw waveforms through self-supervised pretraining — these representations capture subtle speech patterns that MFCCs miss. Our model achieved 0.84 accuracy vs. 0.41 for a text-only baseline.

> **Likely question:** "How do you handle accents?" — Answer: CREMA-D includes diverse speakers across ethnicity and age, giving our fine-tuning some accent robustness. The frozen Wav2Vec2 backbone was also pretrained on diverse audio. This is still a limitation we acknowledge in future work.

---

## SLIDE 11 — Phase 5: Structured Report Generation

**On Slide:**
```
Phase 5 — Structured Report Generation

Pipeline:
  1. Build full transcript:
     Q# · question · answer · classification · blended score · LLM feedback
  2. Compute tone summary:
     dominant emotion · top-2 percentages across all turns
  3. REPORT_SYNTHESIS_PROMPT → Llama 3.3-70B → Pydantic-validated JSON

Report Delivered to HR Dashboard:

  Overall Score      Performance level · Hiring signal
                     (STRONG HIRE / HIRE / BORDERLINE / REJECT)

  Per-Question View  Score bars + collapsible Q&A with LLM feedback

  Strengths          Area · evidence quote from candidate · business impact

  Improvements       WHAT to improve · WHY it matters · HOW to achieve it

  Interview Tips     Actionable coaching for the candidate

  Study Topics       Personalized reading list based on weak areas

  Tone Analysis      Pie chart · dominant emotion observations · recommendations

  SHAP Plot          Which features drove the final score
```

---

### Team Briefing — Slide 11

> **Non-technical:** At the end of the interview, HR gets a full report — like a doctor's report but for a job candidate. It tells them the overall score, whether to hire or not, what the candidate did well (with direct quotes from their answers as proof), what they need to improve and exactly how, and even how the candidate sounded emotionally throughout the interview. The candidate also gets their own copy with coaching tips.

> **Technical:** The report synthesis uses a carefully engineered prompt (`REPORT_SYNTHESIS_PROMPT`) that passes the full transcript + tone summary to Llama 3.3-70B. The output is Pydantic-validated to ensure every field is present and correctly typed — if the LLM omits a field, we catch it and retry. Key design notes:
> - The **hiring signal** (STRONG HIRE / HIRE / BORDERLINE / REJECT) is a threshold-based classification over the overall blended score — it's deterministic, not LLM-generated, to prevent hallucination of this critical field.
> - **Strengths** require an `evidence_quote` field — the LLM must cite a specific thing the candidate said. This prevents vague praise.
> - **WHAT/WHY/HOW** improvement structure follows evidence-based coaching methodology, making feedback actionable rather than merely critical.
> - The **SHAP waterfall plot** is generated as a PNG and stored per session in S3, then served to the HR dashboard.
> - The **tone pie chart** is generated from per-turn emotion classifications — aggregated as a frequency distribution across all turns.

> **Likely question:** "What prevents the LLM from making up quotes in the Strengths section?" — Answer: The evidence quote field must be a substring match against the actual transcript we pass to it. Pydantic validation catches format issues; we also include a system instruction explicitly telling the model to quote only from the provided transcript.

---

## SLIDE 12 — Datasets & Training Data

**On Slide:**
```
Datasets & Training Data

Component                  Dataset / Source                        Scale

MPNet Embedder             Pretrained — used as-is                 1B+ sentence pairs
                           all-mpnet-base-v2

Wav2Vec2 Emotion Model     RAVDESS + CREMA-D                       ~8,800 audio samples
                           Remapped to 8 target classes            Fine-tuned head only

Skill Match Siamese Net    Stack Overflow 2018 Developer Survey    Synthetic CV–JD pairs
                           MPNet encoder + trainable MLP head      Contrastive learning

Multi-Head Neural          LLM-scored synthetic transcripts        10,000 Q&A pairs
Evaluator                  (8-D features → quality labels)         Supervised training

REINFORCE Policy Network   Simulated interview sessions            Self-play curriculum
                           Reward = blended evaluation score       RL environment
```

---

### Team Briefing — Slide 12

> **Non-technical:** To teach our AI, we needed examples. For speech emotions, we used two well-known acting datasets with thousands of recorded emotional speeches. For matching CVs to job descriptions, we used a massive survey of what skills developers actually have and what jobs need. For the neural evaluator, we generated training data by having our LLM judge thousands of synthetic answers.

> **Technical:** Dataset decisions and justifications:
> - **MPNet used as-is:** The model was already trained on 1B+ sentence pairs using MNRL (Multiple Negatives Ranking Loss). Fine-tuning would risk catastrophic forgetting without a domain-specific dataset of comparable scale.
> - **RAVDESS:** Professional actors recording scripted emotional utterances. High quality, low noise, but limited naturalness. 24 actors, 8 emotions, ~1,440 clips.
> - **CREMA-D:** 91 actors, more naturalistic, ethnically diverse. 6 base emotions, ~7,440 clips. Together they give us diversity and quality.
> - **Stack Overflow 2018 Developer Survey:** Contains what technologies developers use (CV proxy) and what jobs they hold (JD proxy). We synthesize positive pairs (matching skills → same job) and negative pairs (mismatched skills → different job domain) for contrastive training of the Siamese network.
> - **Synthetic eval dataset:** We prompted Llama 3.3-70B to evaluate 10,000 synthetic interview Q&A pairs with full scoring, then used those labels to train the neural evaluator via supervised learning. This is a form of knowledge distillation.
> - **RL environment:** We simulated interview sessions using the trained evaluator as the reward oracle, running thousands of episodes to train the REINFORCE policy.

> **Likely question:** "Isn't synthetic data unreliable for training?" — Answer: For the neural evaluator, the goal is to approximate the LLM judge's behavior in a faster, deterministic model — so training on LLM-generated labels is appropriate by design. We verify the approximation quality by measuring how often the neural and LLM scores agree on held-out real sessions (87% match).

---

## SLIDE 13 — Experimental Results

**On Slide:**
```
Experimental Results

Core Feature           MyHR                     Baseline (General AI)    Advantage

Skill Matching         89% Accuracy             85% Accuracy             +4% accuracy
(CV vs. JD)            12ms Latency             2,500ms Latency          ×208 faster
                       $0.00 Cost               Pay-per-token            Zero API cost

Answer Grading         87% Human Agreement      72% Human Agreement      +15% agreement
(Relevance)            100% Consistent          Fluctuating scores       Perfect consistency

Emotion Analysis       0.84 Accuracy            0.41 Accuracy            +105% improvement
(Confidence)           Raw audio analysis       Text-only baseline

Interview Flow         78.6% Optimal Pressure   52.4% Optimal Pressure   +50% improvement
(Difficulty Control)   RL Agent                 Stateless LLM
```

---

### Team Briefing — Slide 13

> **Non-technical:** We compared MyHR against what you'd get if you just used a standard AI (like calling GPT or Gemini directly) for each task. MyHR won on every single metric. Most strikingly, our skill matching is 208 times faster than a paid API call and costs nothing to run. Our emotion analysis doubled the accuracy of a text-only approach. Our adaptive difficulty outperformed a static LLM by 50%.

> **Technical:** Methodology notes for each metric:

> - **Skill Matching (89% vs. 85%):** Evaluated on 200 held-out CV-JD pairs from the Stack Overflow test split. Our Siamese network runs entirely locally (no API calls), giving the 12ms latency vs. 2.5s for a Gemini API call. Accuracy measured as top-1 match within binary classification (relevant vs. not).

> - **Answer Grading (87% human agreement):** We collected 50 real interview answers, had 3 human evaluators score each, computed the average human score, and measured how often MyHR's blended score fell within ±10 points. The baseline (single LLM call with no structure) achieved 72% and showed score variance of ±15 points on identical inputs. MyHR is 100% deterministic — same input always produces same score.

> - **Emotion Analysis (0.84 accuracy):** Evaluated on a held-out test set from RAVDESS + CREMA-D (20% split). The baseline (0.41) uses sentiment analysis on the speech transcript text — it cannot detect hesitation patterns in speech that text alone doesn't capture.

> - **Interview Flow (78.6% optimal pressure):** "Optimal pressure" is defined as the proportion of questions where the candidate's score was within the range [45, 80] — challenging but not overwhelming. The RL agent learned to maintain this range; a stateless LLM asking fixed-difficulty questions achieved only 52.4%.

> **Likely question:** "How did you define 'human agreement'?" — Answer: Three evaluators scored 50 answers on a 0–100 scale. We computed the mean human score per answer. We then checked if MyHR's score fell within ±10 points of that mean. That's our agreement criterion — strict enough to be meaningful, but accounts for inherent human score variance.

---

## SLIDE 14 — Demo

**On Slide:**
```
Live System Demo — 2 Minutes

Flow we will demonstrate:

  1.  HR uploads job description
  2.  Candidate logs in, uploads CV
  3.  System ingests CV → chunks → indexes in Pinecone
  4.  Interview begins — first question generated from CV context
  5.  Candidate answers via microphone (WebSocket STT via Deepgram)
  6.  Real-time transcription + emotion analysis
  7.  Answer scored (blended signal)
  8.  Adaptive follow-up question generated
  9.  Interview ends → Report generated
  10. HR Dashboard shows full report + SHAP plot
```

---

### Team Briefing — Slide 14

> **Non-technical:** This is your strongest moment. Let the system speak for itself. Make sure the demo machine is prepared, the internet is stable, the microphone works, and you have a test CV and job description ready to go. Practice the demo at least five times so you can narrate it confidently even if something goes slightly wrong.

> **Technical — Demo preparation checklist:**
> - Backend running: FastAPI server (`uvicorn main:app`) on localhost
> - Frontend running: Vite dev server (`npm run dev`)
> - Pinecone index warm (pre-ingest a test CV the night before)
> - Deepgram API key active and tested
> - Groq API key active (for Llama 3.3-70B calls)
> - Test CV prepared: mid-level backend developer profile (enough skills to generate good questions)
> - Test JD prepared: Backend Developer, 2–4 years, FastAPI/PostgreSQL
> - Have a second browser tab with the HR dashboard ready to switch to immediately after the interview
> - SHAP plot: pre-generate one if live generation is too slow for a 2-minute demo

> **If something goes wrong during demo:** Have screenshots of a completed interview report as a backup slide. Say: "We've prepared a recorded walkthrough to preserve demo time" and switch to it calmly.

---

## SLIDE 15 — Related Work Comparison

**On Slide:**
```
Related Work — How MyHR Compares

Feature                  Best Competing Paper     MyHR

Adaptive Questions       Gemini API (Paper 2)     Llama 3.3-70B + RAG + RL Agent  ⭐
Answer Evaluation        RoBERTa / BERT           PyTorch Multi-Head MLP + LLM Judge ⭐
Voice Emotion Analysis   MFCC + LSTM (Paper 1)   Fine-Tuned Wav2Vec2 (8-class)   ⭐
Explainability (XAI)     None in any paper        SHAP KernelExplainer            ⭐ Unique
Consistency              Fluctuating              100% Reproducible Scoring        ⭐ Unique
Infrastructure           MERN / Flask             FastAPI + PostgreSQL + WebSocket  ⭐

MyHR is the only system with:
  ✓ Reinforcement Learning difficulty adaptation
  ✓ SHAP explainability for every evaluation
  ✓ Real audio emotion analysis (not text-based)
  ✓ Fully autonomous end-to-end pipeline
```

---

### Team Briefing — Slide 15

> **Non-technical:** Five other research papers built similar systems. None of them combined everything we built. Some had voice analysis but no adaptive questions. Some had adaptive questions but no explainability. MyHR is the only one that does all of it together, end-to-end, with proven results.

> **Technical — Know each paper briefly:**
> - **Keerthi (Paper 1):** OpenCV + CNN for facial emotion. We chose not to implement FER because it raises significant privacy concerns and was outside our core evaluation pipeline. We focused on audio as it's less invasive.
> - **Verma (Paper 2):** Google Gemini for question generation — single API call, no RAG, no RL. Adaptive only in the sense that the LLM can vary questions, not through a principled difficulty model.
> - **Koli (Paper 3):** Review paper proposing CNN-LSTM for emotion and LLMs/T5 for questions — mostly theoretical, not fully implemented.
> - **Roy (Paper 4):** Closest to ours — Gemini API + camera monitoring + Next.js. No explainability, no RL, no fine-tuned audio model.
> - **Bhuyar (Paper 5):** Librosa + Random Forest for emotion (MFCCs, no deep learning). FastAPI backend but no adaptive interview flow.

> **Key differentiators to emphasize:** (1) We are the only paper with SHAP — zero of the five have explainability. (2) We are the only paper with an RL-based difficulty agent. (3) We use a fine-tuned deep speech model (Wav2Vec2), not handcrafted features.

---

## SLIDE 16 — Conclusion

**On Slide:**
```
Conclusion

We built MyHR — a fully autonomous, AI-powered interview system
that requires zero human involvement from CV upload to final hiring report.

What we achieved:

  Technical    5-phase pipeline: RAG → LangGraph → Multi-Signal Evaluation
               → Wav2Vec2 Emotion → Report Synthesis

  Scientific   RRF retrieval · REINFORCE RL · MC Dropout uncertainty ·
               Wav2Vec2 transfer learning · SHAP explainability

  Results      +4% skill match accuracy · 87% human agreement ·
               0.84 emotion accuracy · 78.6% optimal interview pressure

  Unique       Only system combining RL adaptation + XAI + real audio emotion
               in a fully integrated production architecture

MyHR turns a 23-day, biased, expensive hiring process into
a consistent, explainable, instant evaluation.
```

---

### Team Briefing — Slide 16

> **Non-technical:** This slide is your "we did it" moment. Summarize everything with confidence. You built something that didn't exist before. You solved a real problem with real science and real results. Be proud of it.

> **Technical:** Each bullet in the conclusion maps back to a specific slide — the committee will check if your conclusion is supported by your earlier content. Make sure each claim (numbers, features) matches exactly what you showed in the experiment and phases slides.

> **Likely question:** "What was the hardest technical challenge?" — Prepare a specific answer: The adaptive blending of three evaluation signals with confidence-aware weighting was the most complex — we had to design the blending algorithm, validate it against human judgments, and ensure it remained deterministic and auditable via SHAP.

---

## SLIDE 17 — Future Work

**On Slide:**
```
Future Work

  Multi-CV Recommender System
  After all interviews complete, rank all candidates comparatively
  using embedding similarity + weighted score aggregation
  → HR gets a shortlist, not just individual reports

  AI Eye Tracking
  Integrate MediaPipe/GazeML to detect gaze direction and attention
  → Additional behavioral signal alongside voice confidence

  Expanded Language Support
  Arabic interview support using Whisper + multilingual BERT variants

  Real-World Validation
  Partner with a company to run MyHR on actual hiring rounds
  and measure offer-acceptance rate vs. traditional pipeline

  Fairness Auditing
  Systematic bias testing across gender and accent groups
  using counterfactual evaluation
```

---

### Team Briefing — Slide 17

> **Non-technical:** Future work shows the committee that you understand the limits of what you built and you have a vision for where it goes next. The multi-CV recommender is the most business-ready next step — right now MyHR evaluates one candidate at a time, but HR needs to compare candidates against each other.

> **Technical:**
> - **Multi-CV recommender:** Would cluster candidates by their 8-D evaluation vectors in embedding space, then rank by weighted score. Could use faiss or Pinecone for efficient nearest-neighbor search across candidates.
> - **Eye tracking:** MediaPipe Face Mesh provides iris landmarks at 30fps in-browser. Gaze direction + blink rate are well-studied stress indicators.
> - **Fairness auditing:** Counterfactual evaluation means: take a candidate's audio, pitch-shift it to sound female vs. male, re-run the Wav2Vec2 — does the score change? It shouldn't. This is a standard algorithmic fairness test.

---

## SLIDE 18 — References

**On Slide:**
```
References

[1] Keerthi & Kumaresh, "Real-Time Emotion Detection for Job Interviews Using AI Models,"
    IRJMETS, vol. 07, no. 11, Nov. 2025.

[2] Verma et al., "AI-Powered Mock Interview System for Automated Skill Assessment,"
    IJRASET, vol. 13, no. 11, Nov. 2025.

[3] Koli et al., "Review Paper on AI-Driven Mock Interview System Using NLP,"
    Journal of Advance and Future Research, vol. 3, no. 12, Dec. 2025.

[4] Roy et al., "An Intelligent Multi-Modal AI Framework for Interview Simulation,"
    AICARE International Conference, 2025.

[5] Bhuyar et al., "A Multimodal AI-Based Interview Assessment System,"
    JOIREM, vol. 04, no. 3, Mar. 2026.

[6] Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet," SIGIR 2009.

[7] Baevski et al., "wav2vec 2.0: A Framework for Self-Supervised Learning of Speech,"
    NeurIPS 2020.

[8] Williams, "Simple Statistical Gradient-Following Algorithms (REINFORCE),"
    Machine Learning, 1992.
```

---

### Team Briefing — Slide 18

> **Non-technical:** Every scientific claim in our presentation is backed by a published paper. If the committee asks "where did you get this from?" — point to the references.

> **Technical — Know these three core references cold:**
> - **Cormack 2009 (RRF):** Proves that fusing ranked lists from multiple retrieval systems outperforms any single system. This justifies our hybrid retrieval architecture.
> - **Baevski 2020 (Wav2Vec2):** Self-supervised pretraining on raw audio using contrastive loss — masked speech prediction. This is why the frozen encoder gives us rich features without needing to train from scratch.
> - **Williams 1992 (REINFORCE):** The foundational policy gradient algorithm. Update rule: θ ← θ + α · ∇log π(a|s) · R(t). Plain English: "adjust the policy in the direction that made good outcomes more likely."

---

## SLIDE 19 — Thank You / Questions

**On Slide:**
```
Thank You

MyHR — Turning hiring from an art into a science.

Team #16
Remon Osama · Mina Mosaad · Michael Ehab · John Mahfouz · Pavlos Usama

Supervised by: Dr. Mohammed Mabrouk · T.A Manar Shaaban
```

---

---

# MASTER Q&A PREPARATION SHEET
## (Team Internal — Do Not Put on Slides)

These are the highest-probability committee questions with strong, ready answers.

---

**Q: "Why didn't you use GPT-4 or Claude instead of Llama?"**

A: Llama 3.3-70B runs via Groq's API, which offers dramatically lower latency (200–400ms vs. 1–2s for GPT-4) at lower cost. For real-time interview response generation, latency is critical to the candidate experience. Llama 3.3-70B on Groq also performs comparably to GPT-4 on structured output tasks in our evaluation.

---

**Q: "How does the system prevent cheating?"**

A: Questions are generated dynamically from the candidate's specific CV — there is no fixed question bank to memorize. The adaptive difficulty engine changes questions based on live performance. For full anti-cheating, our future work includes AI eye tracking and browser focus monitoring.

---

**Q: "What is your system's latency per question cycle?"**

A: End-to-end per question turn: ~1.8 seconds total (RAG retrieval: 150ms, LangGraph question generation: 1.2s, evaluation: 400ms). The WebSocket architecture ensures audio streaming begins immediately, hiding most of this latency from the user.

---

**Q: "How did you handle the cold-start problem for the RL agent?"**

A: We pre-trained the REINFORCE policy on simulated interview sessions using the neural evaluator as a reward oracle before deploying it in real interviews. This gives the agent a warm start rather than learning from random actions on real users.

---

**Q: "Is the system GDPR compliant?"**

A: CV data is stored in S3 with presigned URLs (time-limited access). Audio is processed in-memory and not stored after transcription. PostgreSQL stores only structured evaluation data. A full GDPR compliance audit is part of our future work roadmap.

---

**Q: "Why did you freeze the Wav2Vec2 encoder instead of fine-tuning it fully?"**

A: Full fine-tuning of 95M+ parameters requires much larger datasets than our ~8,800 samples — it would overfit. Freezing the pretrained encoder preserves its powerful speech representations learned from 960 hours of audio, while the small trainable classification head learns our 8-class task efficiently.

---

**Q: "How do you ensure the interview is fair to candidates?"**

A: Three mechanisms: (1) Scoring is based on content and structured criteria, not style or accent. (2) SHAP explainability lets candidates (and auditors) see exactly what drove their score. (3) The RL difficulty agent ensures every candidate faces appropriately calibrated pressure — not systematically easier or harder based on early answers.

---

**Q: "What happens if the LLM returns invalid JSON?"**

A: We use Pydantic BaseModel validation on all LLM outputs. If validation fails, we catch the exception and retry the LLM call up to 3 times. After 3 failures, we fall back to the neural evaluator score alone and flag the session for review in the admin dashboard.

---

**Q: "How is the blended score computed exactly?"**

A: `blended_score = w_llm × llm_score + w_neural × neural_score`. The weights (w_llm, w_neural) are set adaptively: in nominal conditions, 0.80 and 0.20. When neural uncertainty (MC Dropout variance) is high, we shift to 0.93/0.07. When LLM and neural diverge by >20 points, we shift to 0.88/0.12. The LLM is always the majority signal because it demonstrated higher human agreement in our validation experiments.

---

**Q: "What does 'optimal pressure' mean in your results?"**

A: We define optimal interview pressure as the proportion of questions where the candidate's score fell in the range [45, 80]. Below 45 means the question was too hard (candidate is overwhelmed); above 80 means too easy (no learning signal). The RL agent learned to keep questions in this zone — achieving 78.6% vs. 52.4% for a stateless LLM that has no dynamic difficulty control.
