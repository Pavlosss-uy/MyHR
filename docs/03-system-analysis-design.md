<div align="center" id="ch3">

# Chapter Three

# System Analysis & Design

</div>

<br/>

**Chapter Outline**

- 3.1 System Architecture
- 3.2 Three-Layer Architecture
- 3.3 Component Diagram
- 3.4 Enterprise Hiring Workflow
- 3.5 Candidate Interview Workflow
- 3.6 Authentication & Authorization Design
- 3.7 Database Design (Entity-Relationship Model)
- 3.8 Deployment Design
- 3.9 Interview Activity Diagram

This chapter presents the analysis and design of MyHR: how the major components are organized,
how they communicate, how users and data flow through the system, and how the persistence,
security, and deployment concerns are structured. Design decisions and trade-offs are noted
throughout; the detailed implementation of each component follows in Chapter 4.

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

The following diagram shows the principal backend modules and their dependencies.

**Figure 3.3 — Component Diagram.**

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

---

## 3.6 Authentication & Authorization Design

Identity is delegated to **Firebase Authentication**. The browser authenticates the user and
receives a signed **ID token** (a JSON Web Token); every protected backend request carries this
token in an `Authorization: Bearer …` header, and the backend verifies it with the Firebase
Admin SDK before acting. This keeps password handling and token signing entirely within a
managed identity provider.

Authorization is **role-based**. Three roles exist and are resolved on the server:

- **Candidate** — self-registerable; may run practice interviews.
- **HR (enterprise)** — *not* self-assignable; granted only by accepting a company invitation,
  which adds the user's UID to that company's `adminUIDs` array.
- **Platform administrator** — a fixed allowlist (an `ADMIN_EMAIL` plus optional `ADMIN_UIDS`);
  may approve or reject enterprise access requests.

**Figure 3.6 — Authentication & Authorization Flow.**

```mermaid
sequenceDiagram
    actor U as User
    participant FE as React SPA
    participant FB as Firebase Auth
    participant API as FastAPI
    participant FS as Firestore

    U->>FE: Sign in / sign up
    FE->>FB: Authenticate (email/password or OAuth)
    FB-->>FE: Signed ID token (JWT)
    FE->>API: Request + Bearer ID token
    API->>FB: verify_id_token() → uid, email
    API->>FS: Resolve role (adminUIDs membership / Users)
    FS-->>API: role (candidate | hr | admin)
    API-->>FE: Role-gated response (or 401/403)
```

*Design rationale.* Making the HR role grantable only through an invitation — rather than a
self-service toggle — means a malicious user cannot escalate themselves into another company's
data. Tenant isolation is then enforced on every job-scoped route by checking that the job's
`companyId` matches the caller's company.

---

## 3.7 Database Design (Entity-Relationship Model)

MyHR persists all enterprise state in **Cloud Firestore**, a NoSQL document database. The
logical entities and their relationships are shown in Figure 3.7; the physical collection
layout and field-level detail appear in Section 4.6.

**Figure 3.7 — Database Entity-Relationship Diagram.**

```mermaid
erDiagram
    COMPANIES ||--o{ JOBS : "owns"
    JOBS ||--o{ CANDIDATES : "contains"
    COMPANIES ||--|| COMPANYSTATS : "has analytics"
    PENDINGREQUESTS ||--|| COMPANIES : "approval creates"
    INVITATIONTOKENS }o--|| COMPANIES : "scoped to"
    USERS }o--o{ COMPANIES : "adminUIDs"
```

The field-level contents of each collection are listed in Table 4.2 (Section 4.6).

*Design rationale.* Candidates are stored as a **subcollection** under each job
(`Jobs/{jobId}/Candidates`) rather than in a top-level collection, so that listing a job's
candidates is a single scoped query and tenant isolation falls out of the document path. The
denormalized `stats` object on each job and the separate `CompanyStats` document trade a small
amount of write-time bookkeeping for fast, scan-free dashboard reads.

---

## 3.8 Deployment Design

In development the system runs as two processes — the Vite dev server (port 8080) proxying
`/api` to the FastAPI backend (port 8000). The project is also containerized (a `Dockerfile`
and `docker-compose.yml` are provided) so the backend and its dependencies can be brought up
reproducibly.

**Figure 3.8 — Deployment Diagram.**

```mermaid
flowchart LR
    Browser["Browser"] --> FE["React SPA<br/>Vite :8080 (dev) / static build (prod)"]
    FE -->|/api proxy| BE["FastAPI :8000<br/>Uvicorn ASGI"]
    Browser --> FBAUTH["Firebase Auth"]
    BE --> GROQ["Groq LLM"]
    BE --> PINE["Pinecone vector index"]
    BE --> FS["Cloud Firestore"]
    BE --> DG["Deepgram STT/TTS"]
    BE --> MAIL["Resend / Gmail SMTP"]
    BE -.optional.-> STORE["Object storage<br/>(MinIO / S3)"]
    BE -.optional.-> REDIS["Redis cache"]
```

The frontend never contacts Groq, Pinecone, Deepgram, or the neural models directly; all AI
work is mediated by the backend, which is the single place candidate scores are computed.

The container configuration reflects two deliberate decisions. First, the backend image is
based on `python:3.12-slim` and installs only the system libraries the runtime actually needs
(`libglib2.0-0` for OpenCV, `libsndfile1` for audio, and `ffmpeg` for decoding); the heavy
TensorFlow/DeepFace stack is intentionally excluded in favour of the lighter MediaPipe/YuNet
proctor. Second, the multi-hundred-megabyte trained checkpoints are **not** baked into the
image — they are excluded through `.dockerignore` and mounted read-only at runtime, which keeps
the image small and lets models be updated without rebuilding. Secrets are supplied through an
env-file rather than image layers, and generated reports and audio are persisted to host
volumes. A single `docker compose up --build` brings up the backend (8000) and the frontend
(8080) together.

---

## 3.9 Interview Activity Diagram

Figure 3.9 shows the control flow of a single interview turn from the candidate's perspective,
including the proctoring and anti-cheating timing introduced in the portal.

**Figure 3.9 — Interview Turn (Activity Diagram).**

```mermaid
flowchart LR
    START(["Question<br/>ends"]) --> CD["3-2-1<br/>countdown"]
    CD --> REC["Record<br/>(VAD on)"]
    REC --> SPOKE{"Spoke in<br/>45 s?"}
    SPOKE -->|No| EMPTY["Submit empty<br/>(anti-cheat)"]
    SPOKE -->|Yes| SILENCE{"Silent after<br/>speech?"}
    SILENCE -->|Still talking| REC
    SILENCE -->|Yes| SUBCD["3 s submit<br/>countdown"]
    SUBCD -->|Resumes| REC
    SUBCD -->|Submit| SUBMIT["STT +<br/>evaluate"]
    EMPTY --> SUBMIT
    SUBMIT --> NEXT{"More<br/>questions?"}
    NEXT -->|Yes| START
    NEXT -->|No| DONE(["Report +<br/>thank-you"])
```

The next chapter details how each of these components is implemented.
