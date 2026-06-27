<!--
  FRONT MATTER — MyHR Graduation Documentation
  Fill the bracketed [ ] fields before submission (team members, supervisors, logos).
  Convert to PDF/Word with Times New Roman per the faculty template at export time.
-->

<div align="center">

# Ain Shams University
### Faculty of Computer & Information Sciences
#### Computer Science Department

<br/>

# MyHR — An Adaptive AI-Powered Hiring & Interview Platform

<br/>

*[Cover background image suitable for the project]*

<br/><br/>

**June 2026**

<br/>

*[Sponsor logo if exists]*  &nbsp;&nbsp;&nbsp;&nbsp; *[ITIDA logo if exists]*

</div>

---

<div align="center">

# Ain Shams University
### Faculty of Computer & Information Sciences
#### Computer Science Department

<br/>

# MyHR — An Adaptive AI-Powered Hiring & Interview Platform

This documentation is submitted in partial fulfillment of the requirements for the
**Bachelor's degree in Computer and Information Sciences**

<br/>

**By**

| Name | Department |
|------|------------|
| [Team Member 1] | [Department] |
| [Team Member 2] | [Department] |
| [Team Member 3] | [Department] |
| [Team Member 4] | [Department] |

<br/>

**Under Supervision of**

**[Supervisor 1]**
[Supervisor Title], [Department] Department,
Faculty of Computer and Information Sciences, Ain Shams University.

**[Supervisor 2]**
[Supervisor Title], [Department] Department,
Faculty of Computer and Information Sciences, Ain Shams University.

<br/>

**June 2026**

</div>

---

## Revision History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-06 | Project Team | Initial draft of all chapters |
| 1.0 | 2026-06 | Project Team | First complete release for review |

---

## Acknowledgements

All praise and thanks to ALLAH, who provided us the ability to complete this work.

We are grateful to our families, whose continuous support and encouragement carried us
through every year of study.

We offer our sincerest gratitude to our supervisors, **[Supervisor 1]** and
**[Supervisor 2]**, who guided this project with their patience, knowledge, and experience,
and whose feedback shaped both the engineering and the scientific rigor of MyHR.

Finally, we thank our friends and everyone who supported us throughout the development of
this project.

---

## Abstract

Recruitment at scale is bottlenecked by two manual, time-consuming, and inconsistency-prone
tasks: screening large volumes of résumés (CVs) against a job description (JD), and
conducting first-round interviews. **MyHR** is an adaptive, AI-powered hiring platform that
automates both. It pairs an **enterprise hiring portal** — where companies post jobs, upload
CVs in batches, and obtain neural rankings of candidates — with an **AI interview engine**
that conducts a grounded, adaptive, voice-or-text interview and produces a defensible,
server-computed score for every candidate.

The platform is built on three cooperating subsystems. A **Large Language Model (LLM) agent**,
orchestrated as a state machine with LangGraph and powered by Groq's `llama-3.3-70b-versatile`,
generates interview questions and evaluates answers. A **hybrid Retrieval-Augmented Generation
(RAG) layer** grounds every question in the candidate's own CV and the JD using sparse
retrieval (BM25), dense retrieval (Pinecone with `all-mpnet-base-v2` embeddings), Reciprocal
Rank Fusion, and a cross-encoder reranker. A **custom neural layer** of eight PyTorch models
contributes CV–JD skill matching, multi-dimensional answer evaluation, candidate ranking,
adaptive question difficulty (reinforcement learning), emotion analysis, and performance
prediction. Final answer scores are produced by a transparent blend that weights the LLM
judgment at 65%, the neural evaluator at 20%, and the deep scoring model at 15%, with a
relevance gate that suppresses the neural contribution on off-topic answers.

The system is delivered as a **React** single-page application and a **FastAPI** backend, with
**Firebase Authentication**, **Cloud Firestore** persistence, role-based access control
separating candidates from enterprise HR users, and token-based public interview links. This
document describes the problem, the relevant background, the proposed system architecture, the
detailed implementation of each component, the testing strategy, and the project's conclusions
and future work.

**Keywords:** AI interview, retrieval-augmented generation, LLM agent, candidate ranking,
neural scoring, FastAPI, React, Firestore, adaptive difficulty.

---

## Table of Contents

| Section | Page |
|---------|------|
| Acknowledgements | i |
| Abstract | ii |
| List of Figures | iii |
| List of Tables | iv |
| List of Abbreviations | v |
| **Chapter 1: Introduction** | 1 |
| &nbsp;&nbsp;1.1 Problem Definition | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;1.1.1 History | 1 |
| &nbsp;&nbsp;&nbsp;&nbsp;1.1.2 Applications | 2 |
| &nbsp;&nbsp;1.2 Motivation | 3 |
| &nbsp;&nbsp;1.3 Objectives | 3 |
| &nbsp;&nbsp;1.4 Scope | 4 |
| &nbsp;&nbsp;1.5 Time Plan | 4 |
| &nbsp;&nbsp;1.6 Documentation Outline | 5 |
| **Chapter 2: Background** | 6 |
| &nbsp;&nbsp;2.1 Retrieval-Augmented Generation | 6 |
| &nbsp;&nbsp;2.2 LLM Agent Orchestration | 7 |
| &nbsp;&nbsp;2.3 Transformer Embeddings & Reranking | 8 |
| &nbsp;&nbsp;2.4 Neural Answer Scoring | 8 |
| &nbsp;&nbsp;2.5 Reinforcement Learning for Adaptive Difficulty | 9 |
| &nbsp;&nbsp;2.6 Emotion Recognition & Proctoring | 9 |
| &nbsp;&nbsp;2.7 Platform Technologies | 10 |
| **Chapter 3: Proposed System** | 11 |
| &nbsp;&nbsp;3.1 System Architecture | 11 |
| &nbsp;&nbsp;3.2 Three-Layer Architecture | 12 |
| &nbsp;&nbsp;3.3 Component Diagram | 13 |
| &nbsp;&nbsp;3.4 Enterprise Hiring Workflow | 14 |
| &nbsp;&nbsp;3.5 Candidate Interview Workflow | 15 |
| **Chapter 4: System Implementation** | 16 |
| &nbsp;&nbsp;4.1 Hybrid RAG Pipeline | 16 |
| &nbsp;&nbsp;4.2 LangGraph Interview Agent | 18 |
| &nbsp;&nbsp;4.3 AI/ML Model Layer | 20 |
| &nbsp;&nbsp;4.4 Enterprise Layer | 23 |
| &nbsp;&nbsp;4.5 Training Layer | 25 |
| &nbsp;&nbsp;4.6 Database Design | 27 |
| &nbsp;&nbsp;4.7 API Reference | 29 |
| &nbsp;&nbsp;4.8 Authentication & Authorization | 31 |
| &nbsp;&nbsp;4.9 Configuration | 33 |
| **Chapter 5: System Testing** | 34 |
| &nbsp;&nbsp;5.1 Installation | 34 |
| &nbsp;&nbsp;5.2 Running the System | 35 |
| &nbsp;&nbsp;5.3 Automated Test Suite | 36 |
| &nbsp;&nbsp;5.4 End-to-End Walkthrough | 37 |
| **Chapter 6: Conclusion and Future Work** | 40 |
| &nbsp;&nbsp;6.1 Conclusion | 40 |
| &nbsp;&nbsp;6.2 Known Limitations | 40 |
| &nbsp;&nbsp;6.3 Future Work | 41 |
| Tools | 42 |
| References | 43 |
| Glossary & Abbreviations | 44 |
| Appendices | 45 |

> Page numbers are indicative and should be regenerated after exporting to PDF/Word.

---

## List of Figures

| Figure | Title | Page |
|--------|-------|------|
| Figure 1.1 | Project Time Plan (Gantt) | 4 |
| Figure 3.1 | System Architecture | 11 |
| Figure 3.2 | Three-Layer Architecture | 12 |
| Figure 3.3 | Component Diagram | 13 |
| Figure 3.4 | Enterprise Hiring Workflow (Sequence) | 14 |
| Figure 3.5 | Candidate Interview Workflow (Sequence) | 15 |
| Figure 4.1 | Hybrid RAG Pipeline | 16 |
| Figure 4.2 | LangGraph Agent State Graph | 18 |
| Figure 4.3 | Answer Scoring & Blend Flow | 19 |
| Figure 4.4 | Training Pipeline | 25 |
| Figure 4.5 | Database Relationships | 27 |
| Figure 4.6 | Authentication & RBAC Flow | 31 |
| Figure 5.1 | Deployment Architecture | 35 |

---

## List of Tables

| Table | Title | Page |
|-------|-------|------|
| Table 2.1 | Platform Technology Stack | 10 |
| Table 4.1 | Neural Model Layer (8 models) | 20 |
| Table 4.2 | Firestore Collections | 27 |
| Table 4.3 | API Reference — Interview Endpoints | 29 |
| Table 4.4 | API Reference — Enterprise Endpoints | 30 |
| Table 4.5 | Environment Variables | 33 |
| Table 5.1 | Automated Test Summary | 36 |
| Table T.1 | Tools Used | 42 |

---

## List of Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| API | Application Programming Interface |
| BM25 | Best Matching 25 (sparse ranking function) |
| CV | Curriculum Vitae (résumé) |
| HR | Human Resources |
| JD | Job Description |
| LLM | Large Language Model |
| MLP | Multi-Layer Perceptron |
| NDCG | Normalized Discounted Cumulative Gain |
| PII | Personally Identifiable Information |
| PPO | Proximal Policy Optimization |
| RAG | Retrieval-Augmented Generation |
| RBAC | Role-Based Access Control |
| RL | Reinforcement Learning |
| RRF | Reciprocal Rank Fusion |
| SPA | Single-Page Application |
| STT | Speech-to-Text |
| TTS | Text-to-Speech |
| WS | WebSocket |
