<div align="center">

# Chapter Three

# Proposed System

</div>

<br/>

**Chapter Outline**

- 3.1 System Architecture
- 3.2 Three-Layer Architecture
- 3.3 Component Diagram
- 3.4 Enterprise Hiring Workflow
- 3.5 Candidate Interview Workflow

This chapter presents the architecture of MyHR: how the major components are organized, how
they communicate, and how data flows through the two principal end-to-end workflows.

---

## 3.1 System Architecture

MyHR follows a classic **client–server** architecture. A React single-page application runs in
the browser and communicates with a FastAPI backend over HTTP (REST) and, during a live
interview, over a WebSocket. The backend orchestrates four external/internal services: the
LLM (Groq), the vector database (Pinecone), the neural model layer (PyTorch, in-process), and
the persistence and identity services (Firestore and Firebase Authentication). Speech
conversion is handled by Deepgram, and transactional email by Resend or Gmail SMTP.

**Figure 3.1 — System Architecture.**

```mermaid
flowchart TB
    subgraph Client["Browser — React SPA (port 8080)"]
        UI["HR Dashboard · Job Management · Analytics<br/>Candidate Interview Portal · Auth"]
    end

    subgraph Server["FastAPI Backend (port 8000)"]
        REST["REST API<br/>(server.py + hr_routes.py)"]
        WSV["WebSocket<br/>/ws/interview/:id"]
        AGENT["LangGraph Interview Agent<br/>(agent.py)"]
        RAG["Hybrid RAG<br/>(ingest.py + retriever.py)"]
        NEURAL["Neural Layer — 8 PyTorch models<br/>(models/registry.py)"]
    end

    subgraph External["External & Managed Services"]
        GROQ["Groq LLM<br/>llama-3.3-70b-versatile"]
        PINE["Pinecone<br/>vector index"]
        FS["Cloud Firestore"]
        FBAUTH["Firebase Auth"]
        DG["Deepgram STT/TTS"]
        MAIL["Resend / Gmail SMTP"]
    end

    UI -->|"/api proxy"| REST
    UI <-->|live audio/video| WSV
    REST --> AGENT
    WSV --> AGENT
    AGENT --> RAG
    AGENT --> NEURAL
    AGENT --> GROQ
    RAG --> PINE
    REST --> FS
    UI --> FBAUTH
    REST --> FBAUTH
    WSV --> DG
    REST --> MAIL
```

The frontend never talks to Groq, Pinecone, or the neural models directly; all AI work is
mediated by the backend, which is also the only place candidate scores are computed.

---

## 3.2 Three-Layer Architecture

Conceptually, the system decomposes into three layers with distinct responsibilities,
lifecycles, and audiences.

**Figure 3.2 — Three-Layer Architecture.**

```mermaid
flowchart LR
    subgraph L1["Enterprise Layer"]
        direction TB
        E1["Accounts & RBAC"]
        E2["Jobs & CV upload"]
        E3["Neural ranking"]
        E4["Invitations & analytics"]
    end

    subgraph L2["Interview-AI Layer"]
        direction TB
        I1["RAG grounding"]
        I2["LangGraph agent"]
        I3["Answer scoring & blend"]
        I4["Proctoring & report"]
    end

    subgraph L3["Training Layer"]
        direction TB
        T1["Data generation"]
        T2["Model training (8)"]
        T3["Held-out evaluation"]
        T4["Human-rating study"]
    end

    L1 -->|invites candidates into| L2
    L3 -->|produces checkpoints for| L2
    L3 -->|skill matcher & ranker for| L1
```

- The **Enterprise Layer** (`hr_routes.py`, frontend HR pages) is multi-tenant, authenticated,
  and persisted in Firestore. It owns the hiring funnel.
- The **Interview-AI Layer** (`server.py`, `agent.py`, `ingest.py`, `retriever.py`,
  `models/`) is stateful and real-time. It conducts interviews and scores answers.
- The **Training Layer** (`training/`) is offline. It generates data, trains the eight neural
  models, evaluates them on held-out test sets, and runs the human-rating validation study. Its
  outputs are the model checkpoints consumed by the other two layers.

---

## 3.3 Component Diagram

**Figure 3.3 — Component Diagram.** The following diagram shows the principal backend modules
and their dependencies.

```mermaid
flowchart TB
    server["server.py<br/>app + interview WS + REST"]
    hr["hr_routes.py<br/>enterprise router"]
    agent["agent.py<br/>LangGraph agent"]
    ingest["ingest.py<br/>index + embedder"]
    retr["retriever.py<br/>BM25+dense+RRF+rerank"]
    cv["cv_parser.py<br/>parse + rubric score"]
    reg["models/registry.py<br/>lazy model loader"]
    fc["firestore_client.py<br/>Firestore helpers"]
    email["email_service.py<br/>Resend / SMTP"]
    prompts["prompts.py<br/>LLM prompt templates"]

    server --> agent
    server --> hr
    server --> reg
    hr --> cv
    hr --> reg
    hr --> fc
    hr --> email
    agent --> retr
    agent --> reg
    agent --> prompts
    retr --> ingest
    ingest --> reg
    server --> fc
```

---

## 3.4 Enterprise Hiring Workflow

The enterprise workflow is the hiring funnel, from a company requesting access through to
reviewing completed interviews.

**Figure 3.4 — Enterprise Hiring Workflow (Sequence).**

```mermaid
sequenceDiagram
    actor HR as HR User
    actor Admin as Platform Admin
    participant FE as React SPA
    participant API as FastAPI (hr_routes)
    participant FS as Firestore
    participant Mail as Email Service
    actor Cand as Candidate

    HR->>FE: Request enterprise access
    FE->>API: POST /request-access
    API->>FS: Create PendingRequest
    API->>Mail: Notify admin
    Admin->>API: POST /admin/accept-request/{id}
    API->>FS: Create Company + InvitationToken
    API->>Mail: Send invite link to HR
    HR->>API: POST /invite/{token}/accept
    API->>FS: Add HR uid to Company.adminUIDs
    HR->>API: POST /jobs  (create job)
    HR->>API: POST /jobs/{id}/upload-cvs
    API->>API: Parse CVs, skill-match, rubric score
    API->>FS: Persist Candidates + job stats
    HR->>API: POST /jobs/{id}/invite-interview/{cand}
    API->>Mail: Email interview link to candidate
    Cand-->>API: Completes AI interview (see 3.5)
    HR->>API: GET /analytics
    API->>FS: Read pre-computed CompanyStats
```

---

## 3.5 Candidate Interview Workflow

When a candidate opens their interview link, they enter a stateful, real-time session driven
by the LangGraph agent.

**Figure 3.5 — Candidate Interview Workflow (Sequence).**

```mermaid
sequenceDiagram
    actor Cand as Candidate
    participant FE as Interview Portal
    participant API as FastAPI (server.py)
    participant Agent as LangGraph Agent
    participant RAG as Hybrid RAG
    participant LLM as Groq LLM
    participant Neural as Neural Layer

    Cand->>API: GET /candidate-interview/{token}/validate
    API-->>FE: Job, company, candidate info
    Cand->>API: POST /candidate-interview/{token}/start
    API->>RAG: Index CV + JD (Pinecone + BM25)
    API->>Agent: Generate first question (grounded)
    Agent->>RAG: Retrieve CV/JD evidence
    Agent->>LLM: Generate question
    API-->>FE: First question (text + TTS audio)
    loop Each answer
        Cand->>API: Submit answer (voice/text)
        API->>Agent: process_answer
        Agent->>LLM: Evaluate answer
        Agent->>Neural: Evaluator + scorer
        Agent->>Agent: Blend 65/20/15 + relevance gate
        Agent->>Agent: Adapt difficulty, decide next step
        API-->>FE: Next question or completion
    end
    API->>API: Synthesize server-side report + score
    API-->>FE: Thank-you screen (no score shown)
```

Two design properties are visible here. First, the question is **grounded** before the LLM is
ever called — the agent retrieves CV/JD evidence first. Second, the final score is
**synthesized on the server** from the accumulated evaluations; the candidate is shown only a
thank-you screen, never their score, and cannot influence the number that reaches the HR
dashboard.

The next chapter details how each of these components is implemented.
