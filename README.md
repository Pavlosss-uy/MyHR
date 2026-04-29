<div align="center">

# MyHR

**AI-powered technical interview platform — for candidates who want to level up, and teams who want to hire right.**

[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.10+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Core-FF6B35?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Firebase](https://img.shields.io/badge/Firebase-Firestore-FFCA28?style=flat-square&logo=firebase&logoColor=black)](https://firebase.google.com)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)


</div>

---

## What is MyHR?

MyHR is a full-stack, AI-powered interview platform that simulates a senior technical recruiter. It conducts adaptive technical interviews, analyzes candidate responses through multimodal signals (voice, facial expression, and text), and produces structured executive evaluation reports.

It serves two audiences:
- **Candidates** — practice realistic technical interviews with adaptive difficulty and instant AI feedback
- **HR teams** — screen and rank applicants at scale, then send targeted interview invitations

---

## Features

### For Candidates

| Feature | Description |
|---|---|
| Adaptive Interviews | Questions adjust in difficulty and topic focus based on your answers in real time |
| Multimodal Analysis | Speech transcription + facial emotion detection surface communication insights beyond just what you say |
| Structured Feedback | Scored across relevance, clarity, technical depth, and STAR method |
| Executive Reports | Detailed post-interview report with per-answer evaluations, improvement suggestions, and a predicted performance rating |
| Interview History | Track progress across sessions |
| OAuth Login | Sign in with email, Google, or LinkedIn |

### For HR Teams

| Feature | Description |
|---|---|
| Job Management | Create postings and define technical requirements |
| Batch CV Upload | Drop multiple CVs and let the AI extract skills and match them to your job description |
| AI Candidate Ranking | Candidates are ranked by relevance score — no manual sifting |
| Interview Invitations | Send token-based interview links via email (no candidate account required) |
| Candidate Dashboard | Track every candidate's profile, interview status, and evaluation results |
| Analytics | Hiring funnel metrics, pass/fail rates, and performance breakdowns |

### AI/ML Core

- **LangGraph state machine** — orchestrates the full interview lifecycle as a graph of nodes (query rewriting → hybrid retrieval → question generation → answer evaluation → report synthesis)
- **Hybrid RAG pipeline** — combines vector search + BM25 full-text search with cross-encoder reranking for context-aware, high-relevance question generation
- **RL-based difficulty engine** — uses a PPO policy (Stable-Baselines3) to adapt question difficulty based on live candidate performance
- **Deepgram STT** — real-time speech-to-text during interviews
- **DeepFace** — computer vision for facial emotion analysis
- **SHAP explainability** — model interpretability for evaluation scores

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                      │
│         Tailwind CSS · shadcn/ui · Framer Motion             │
│         React Query · React Hook Form · React Router          │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼──────────────────────────────────┐
│               FastAPI Backend + Celery Workers                │
└────┬──────────┬──────────────┬─────────────────┬────────────┘
     │          │              │                 │
┌────▼────┐ ┌──▼──────┐ ┌─────▼──────┐ ┌───────▼──────┐
│LangGraph│ │ Hybrid  │ │ Multimodal │ │  Evaluation  │
│  Agent  │ │   RAG   │ │  Analysis  │ │   Engine     │
│         │ │Vector + │ │  Deepgram  │ │  Structured  │
│(Groq LLM│ │BM25 +   │ │  DeepFace  │ │  Rubrics +   │
│LangChain│ │Reranker)│ │            │ │  SHAP scores │
└────┬────┘ └──┬──────┘ └────────────┘ └──────────────┘
     │         │
┌────▼─────────▼───────────────────────────────────────────────┐
│           Data & Storage Layer                                │
│   Firebase Firestore (B2B)  ·  AWS S3  ·  Pinecone (vectors) │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite 5, Tailwind CSS, shadcn/ui, Radix UI, Framer Motion, Recharts |
| **State** | TanStack React Query, React Context, React Hook Form + Zod |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Celery |
| **Agentic AI** | LangGraph, LangChain, LangChain-OpenAI, LlamaIndex |
| **LLM Inference** | Groq API |
| **RAG** | Pinecone (vector DB), BM25, cross-encoder reranking, HuggingFace embeddings |
| **Speech** | Deepgram SDK (real-time STT), Librosa (audio processing) |
| **Vision** | DeepFace (facial emotion), PyTorch, Transformers |
| **RL** | Stable-Baselines3 (PPO), Gymnasium |
| **Explainability** | SHAP |
| **Database** | Firebase Firestore |
| **Storage** | AWS S3 |
| **Email** | Resend |
| **Auth** | Firebase Auth (email/password, Google OAuth, LinkedIn OAuth) |
| **Testing** | Vitest + Testing Library (frontend), pytest (backend) |

---




---

## Project Structure

```
MyHR/
├── src/                     # React frontend
│   ├── pages/               # 22 page components (Landing, Auth, InterviewRoom, HRDashboard, ...)
│   ├── components/          # Shared UI components + shadcn/ui
│   ├── contexts/            # Auth context
│   └── hooks/               # Audio recorder, media devices, etc.
│
├── agent.py                 # LangGraph interview agent (state machine)
├── server.py                # FastAPI server + WebSocket endpoints
├── hr_routes.py             # B2B HR API endpoints
├── retriever.py             # Hybrid RAG (Vector + BM25 + reranker)
├── ingest.py                # Document ingestion pipeline
├── cv_parser.py             # CV parsing, skill extraction, match scoring
├── prompts.py               # All LLM prompt templates
├── services.py              # Deepgram STT, TTS, voice tone analysis
├── firestore_client.py      # Firebase Firestore helpers
├── s3_utils.py              # AWS S3 utilities
├── celery_worker.py         # Async background tasks
├── tone.py                  # Voice tone analysis
├── models/                  # Trained ML model artifacts + registry
└── training/                # Training scripts (emotion, evaluator, ranker, RL, ...)
```

---

## License

This project is part of ongoing academic and personal development work.
