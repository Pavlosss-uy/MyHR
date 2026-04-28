# MyHR: AI-Powered Interview System

An intelligent, multi-tier interview platform that simulates a senior technical recruiter using agentic AI. MyHR conducts adaptive technical interviews, analyzes candidate responses through multimodal signals, and generates structured executive evaluation reports.

> **Status:** In active development

---

## The Problem

Before building MyHR, we conducted a **user research survey** to validate the need for an AI-powered interview tool. Key findings from our data:

- **Over 200%** of respondents identified "answering questions effectively" as the hardest part of interviews
- **56.58%** of interviews last 30–45 minutes — our system targets this window
- Average **nervousness score: 3.66/5** — candidates want a low-pressure way to practice
- **~36%** of respondents have never used an AI tool for interview prep but are interested
- **ChatGPT dominates** current AI tool usage, but lacks structured interview simulation, scoring, and behavioral feedback
- **90%+** interest in AI-generated questions, scoring, and feedback features

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)               │
│              Tailwind CSS · shadcn/ui components         │
├─────────────────────────────────────────────────────────┤
│                  FastAPI Backend (server.py)              │
│         REST endpoints · WebSocket · Celery workers      │
├──────────┬──────────┬──────────┬────────────────────────┤
│  Agentic │  Hybrid  │  Multi-  │    Evaluation          │
│   Core   │   RAG    │  modal   │    Engine              │
│(LangGraph│(Vector + │(Deepgram │ (Structured rubrics    │
│  Agent)  │  BM25 +  │+ DeepFace│  + executive report    │
│          │Cross-Enc)│   )      │  generation)           │
├──────────┴──────────┴──────────┴────────────────────────┤
│          Data Layer: Firestore · AWS S3                  │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### Agentic Interview Core
- **LangGraph state machine** orchestrates the full interview lifecycle — from CV ingestion to report generation
- **ReAct framework** enables the agent to reason about candidate responses and dynamically adjust question difficulty and topic focus

### Hybrid RAG Pipeline
- **Vector search + BM25** retrieval with **cross-encoder reranking** for maximum relevance
- Ingests candidate CVs and job descriptions to generate tailored, context-aware technical questions
- Built with LangChain + LlamaIndex

### Multimodal Analysis
- **Deepgram SDK** for real-time speech-to-text processing during interviews
- **DeepFace** (computer vision) for facial emotion analysis — surfaces behavioral and communication insights beyond text

### Automated Evaluation
- Structured rubrics assess candidate performance across multiple dimensions
- Generates professional **executive-level interview reports** with standardized scoring

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React, Vite, Tailwind CSS, shadcn/ui |
| **Backend** | Python, FastAPI, Celery (async tasks) |
| **AI/ML** | LangGraph, LangChain, LlamaIndex |
| **RAG** | Vector DB, BM25, Cross-Encoder Reranking |
| **Speech** | Deepgram SDK |
| **Vision** | DeepFace |
| **Storage** | Google Firestore, AWS S3 |
| **Testing** | Vitest (frontend), pytest (backend) |
| **Code Quality** | ESLint |

---

## Project Structure

```
MyHR/
├── src/                    # React frontend components
├── agent.py                # LangGraph agentic core
├── server.py               # FastAPI backend server
├── hr_routes.py            # Interview API endpoints
├── retriever.py            # Hybrid RAG retriever (Vector + BM25)
├── ingest.py               # Document ingestion pipeline
├── cv_parser.py            # CV parsing and extraction
├── prompts.py              # Prompt templates for the agent
├── services.py             # Business logic layer
├── database.py             # Firestore data access
├── firestore_client.py     # Firestore connection client
├── s3_utils.py             # AWS S3 file operations
├── celery_worker.py        # Async task processing
├── tone.py                 # Tone analysis module
├── models/                 # ML model artifacts
├── training/               # Training scripts and configs
├── test_phase1_divergence.py  # Phase 1 tests
├── test_phase3.py          # Phase 3 tests
└── requirements.txt        # Python dependencies
```

---

## Research & Validation

The project began with a **data-driven research phase**:

1. **Survey Design** — Created a structured questionnaire targeting job seekers and interview candidates
2. **Data Collection** — Gathered responses on interview pain points, AI tool usage, and feature interest
3. **Dashboard & Analysis** — Built Power BI dashboards to visualize findings and validate the product hypothesis
4. **Key Decision** — Survey data confirmed strong demand for AI-powered interview simulation with scoring — proceeding with development

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Cloud credentials (Firestore)
- AWS credentials (S3)
- Deepgram API key

### Installation

```bash
# Clone the repository
git clone https://github.com/Pavlosss-uy/MyHR.git
cd MyHR

# Backend
pip install -r requirements.txt

# Frontend
npm install
npm run dev

# Start the backend server
python server.py
```

---

## License

This project is part of ongoing academic and personal development work.
