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

<div style="page-break-after: always;"></div>

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

<div style="page-break-after: always;"></div>

## Revision History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-06 | Project Team | Initial draft of all chapters |
| 1.0 | 2026-06 | Project Team | First complete release for review |

<div style="page-break-after: always;"></div>

<div align="center">

# Acknowledgements

</div>

All praise and thanks to ALLAH, who provided us the ability to complete this work.

We are grateful to our families, whose continuous support and encouragement carried us
through every year of study.

We offer our sincerest gratitude to our supervisors, **[Supervisor 1]** and
**[Supervisor 2]**, who guided this project with their patience, knowledge, and experience,
and whose feedback shaped both the engineering and the scientific rigor of MyHR.

Finally, we thank our friends and everyone who supported us throughout the development of
this project.

<div style="page-break-after: always;"></div>

<div align="center">

# Abstract

</div>

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

<div style="page-break-after: always;"></div>

<div align="center">

# Table of Contents

</div>

<div class="toc">
<p class="front"><a href="#acknowledgements">Acknowledgements</a><span class="lead"></span><span class="pg">i</span></p>
<p class="front"><a href="#abstract">Abstract</a><span class="lead"></span><span class="pg">ii</span></p>
<p class="front"><a href="#list-of-figures">List of Figures</a><span class="lead"></span><span class="pg">iv</span></p>
<p class="front"><a href="#list-of-tables">List of Tables</a><span class="lead"></span><span class="pg">v</span></p>
<p class="front"><a href="#list-of-abbreviations">List of Abbreviations</a><span class="lead"></span><span class="pg">vi</span></p>

<p class="ch"><a href="#ch1">Chapter 1 — Introduction</a><span class="lead"></span><span class="pg">1</span></p>
<p class="s1">1.1 Problem Definition<span class="lead"></span><span class="pg">1</span></p>
<p class="s2">1.1.1 History<span class="lead"></span><span class="pg">1</span></p>
<p class="s2">1.1.2 Applications<span class="lead"></span><span class="pg">2</span></p>
<p class="s1">1.2 Motivation<span class="lead"></span><span class="pg">3</span></p>
<p class="s1">1.3 Objectives<span class="lead"></span><span class="pg">3</span></p>
<p class="s1">1.4 Scope<span class="lead"></span><span class="pg">5</span></p>
<p class="s1">1.5 Functional Requirements<span class="lead"></span><span class="pg">6</span></p>
<p class="s1">1.6 Non-Functional Requirements<span class="lead"></span><span class="pg">7</span></p>
<p class="s1">1.7 Project Timeline<span class="lead"></span><span class="pg">8</span></p>
<p class="s1">1.8 Documentation Outline<span class="lead"></span><span class="pg">9</span></p>

<p class="ch"><a href="#ch2">Chapter 2 — Background</a><span class="lead"></span><span class="pg">10</span></p>
<p class="s1">2.1 Retrieval-Augmented Generation<span class="lead"></span><span class="pg">10</span></p>
<p class="s1">2.2 LLM Agent Orchestration<span class="lead"></span><span class="pg">11</span></p>
<p class="s1">2.3 Transformer Embeddings & Reranking<span class="lead"></span><span class="pg">12</span></p>
<p class="s1">2.4 Neural Answer Scoring<span class="lead"></span><span class="pg">12</span></p>
<p class="s1">2.5 Reinforcement Learning for Adaptive Difficulty<span class="lead"></span><span class="pg">13</span></p>
<p class="s1">2.6 Emotion Recognition & Proctoring<span class="lead"></span><span class="pg">13</span></p>
<p class="s1">2.7 Platform Technologies<span class="lead"></span><span class="pg">14</span></p>

<p class="ch"><a href="#ch3">Chapter 3 — System Analysis & Design</a><span class="lead"></span><span class="pg">15</span></p>
<p class="s1">3.1 System Architecture<span class="lead"></span><span class="pg">15</span></p>
<p class="s1">3.2 Three-Layer Architecture<span class="lead"></span><span class="pg">16</span></p>
<p class="s1">3.3 Component Diagram<span class="lead"></span><span class="pg">17</span></p>
<p class="s1">3.4 Enterprise Hiring Workflow<span class="lead"></span><span class="pg">18</span></p>
<p class="s1">3.5 Candidate Interview Workflow<span class="lead"></span><span class="pg">19</span></p>
<p class="s1">3.6 Authentication & Authorization Design<span class="lead"></span><span class="pg">20</span></p>
<p class="s1">3.7 Database Design (ER Model)<span class="lead"></span><span class="pg">21</span></p>
<p class="s1">3.8 Deployment Design<span class="lead"></span><span class="pg">22</span></p>
<p class="s1">3.9 Interview Activity Diagram<span class="lead"></span><span class="pg">23</span></p>

<p class="ch"><a href="#ch4">Chapter 4 — System Implementation</a><span class="lead"></span><span class="pg">24</span></p>
<p class="s1">4.1 Hybrid RAG Pipeline<span class="lead"></span><span class="pg">24</span></p>
<p class="s1">4.2 LangGraph Interview Agent<span class="lead"></span><span class="pg">26</span></p>
<p class="s1">4.3 AI/ML Model Layer<span class="lead"></span><span class="pg">28</span></p>
<p class="s1">4.4 Enterprise Layer<span class="lead"></span><span class="pg">31</span></p>
<p class="s1">4.5 Training Layer<span class="lead"></span><span class="pg">33</span></p>
<p class="s1">4.6 Database Design<span class="lead"></span><span class="pg">35</span></p>
<p class="s1">4.7 API Reference<span class="lead"></span><span class="pg">37</span></p>
<p class="s1">4.8 Authentication & Authorization<span class="lead"></span><span class="pg">39</span></p>
<p class="s1">4.9 Configuration<span class="lead"></span><span class="pg">41</span></p>
<p class="s1">4.10 Proctoring, Speech & Anti-Cheating<span class="lead"></span><span class="pg">42</span></p>
<p class="s1">4.11 Cross-Cutting Concerns<span class="lead"></span><span class="pg">44</span></p>

<p class="ch"><a href="#ch5">Chapter 5 — System Testing</a><span class="lead"></span><span class="pg">45</span></p>
<p class="s1">5.1 Testing Strategy<span class="lead"></span><span class="pg">45</span></p>
<p class="s1">5.2 Installation<span class="lead"></span><span class="pg">46</span></p>
<p class="s1">5.3 Running the System<span class="lead"></span><span class="pg">47</span></p>
<p class="s1">5.4 Automated Test Suite<span class="lead"></span><span class="pg">48</span></p>
<p class="s1">5.5 End-to-End Walkthrough<span class="lead"></span><span class="pg">49</span></p>

<p class="ch"><a href="#ch6">Chapter 6 — Results & Discussion</a><span class="lead"></span><span class="pg">52</span></p>
<p class="s1">6.1 Model Results<span class="lead"></span><span class="pg">52</span></p>
<p class="s1">6.2 RAG & Grounding Results<span class="lead"></span><span class="pg">53</span></p>
<p class="s1">6.3 System & Backend Performance<span class="lead"></span><span class="pg">54</span></p>
<p class="s1">6.4 Enterprise Funnel Results<span class="lead"></span><span class="pg">55</span></p>
<p class="s1">6.5 Strengths · 6.6 Weaknesses · 6.7 Lessons Learned<span class="lead"></span><span class="pg">55</span></p>

<p class="ch"><a href="#ch7">Chapter 7 — Conclusion and Future Work</a><span class="lead"></span><span class="pg">58</span></p>
<p class="s1">7.1 Conclusion<span class="lead"></span><span class="pg">58</span></p>
<p class="s1">7.2 Known Limitations<span class="lead"></span><span class="pg">59</span></p>
<p class="s1">7.3 Future Work<span class="lead"></span><span class="pg">60</span></p>

<p class="ch"><a href="#tools">Tools</a><span class="lead"></span><span class="pg">61</span></p>
<p class="ch"><a href="#references">References</a><span class="lead"></span><span class="pg">62</span></p>
<p class="ch"><a href="#appendices">Appendices</a><span class="lead"></span><span class="pg">63</span></p>
</div>

> Page numbers are indicative; the live page numbers are printed in the footer of the exported
> document.

<div style="page-break-after: always;"></div>

<div align="center">

# List of Figures

</div>

<div class="toc">
<p><a href="#ch1">Figure 1.1 — Project Time Plan (Gantt)</a><span class="lead"></span><span class="pg">8</span></p>
<p><a href="#ch3">Figure 3.1 — System Architecture</a><span class="lead"></span><span class="pg">15</span></p>
<p><a href="#ch3">Figure 3.2 — Three-Layer Architecture</a><span class="lead"></span><span class="pg">16</span></p>
<p><a href="#ch3">Figure 3.3 — Component Diagram</a><span class="lead"></span><span class="pg">17</span></p>
<p><a href="#ch3">Figure 3.4 — Enterprise Hiring Workflow (Sequence)</a><span class="lead"></span><span class="pg">18</span></p>
<p><a href="#ch3">Figure 3.5 — Candidate Interview Workflow (Sequence)</a><span class="lead"></span><span class="pg">19</span></p>
<p><a href="#ch3">Figure 3.6 — Authentication & Authorization Flow</a><span class="lead"></span><span class="pg">20</span></p>
<p><a href="#ch3">Figure 3.7 — Database Entity-Relationship Diagram</a><span class="lead"></span><span class="pg">21</span></p>
<p><a href="#ch3">Figure 3.8 — Deployment Diagram</a><span class="lead"></span><span class="pg">22</span></p>
<p><a href="#ch3">Figure 3.9 — Interview Turn (Activity Diagram)</a><span class="lead"></span><span class="pg">23</span></p>
<p><a href="#ch4">Figure 4.1 — Hybrid RAG Pipeline</a><span class="lead"></span><span class="pg">24</span></p>
<p><a href="#ch4">Figure 4.2 — LangGraph Agent State Graph</a><span class="lead"></span><span class="pg">26</span></p>
<p><a href="#ch4">Figure 4.3 — Answer Scoring and Blend</a><span class="lead"></span><span class="pg">27</span></p>
<p><a href="#ch4">Figure 4.4 — Training Pipeline</a><span class="lead"></span><span class="pg">33</span></p>
<p><a href="#ch4">Figure 4.5 — Proctoring Detection Pipeline</a><span class="lead"></span><span class="pg">42</span></p>
<p><a href="#ch6">Figure 6.1 — Score Distribution & Model Agreement</a><span class="lead"></span><span class="pg">52</span></p>
</div>

<div style="page-break-after: always;"></div>

<div align="center">

# List of Tables

</div>

<div class="toc">
<p><a href="#ch1">Table 1.1 — Comparison with Existing Solutions</a><span class="lead"></span><span class="pg">2</span></p>
<p><a href="#ch1">Table 1.2 — Functional Requirements</a><span class="lead"></span><span class="pg">6</span></p>
<p><a href="#ch1">Table 1.3 — Non-Functional Requirements</a><span class="lead"></span><span class="pg">7</span></p>
<p><a href="#ch2">Table 2.1 — Platform Technology Stack</a><span class="lead"></span><span class="pg">14</span></p>
<p><a href="#ch4">Table 4.1 — Neural Model Layer</a><span class="lead"></span><span class="pg">28</span></p>
<p><a href="#ch4">Table 4.2 — Firestore Collections</a><span class="lead"></span><span class="pg">35</span></p>
<p><a href="#ch4">Table 4.3 — API Reference: Interview & System Endpoints</a><span class="lead"></span><span class="pg">37</span></p>
<p><a href="#ch4">Table 4.4 — API Reference: Enterprise Endpoints</a><span class="lead"></span><span class="pg">38</span></p>
<p><a href="#ch4">Table 4.5 — Environment Variables</a><span class="lead"></span><span class="pg">41</span></p>
<p><a href="#ch5">Table 5.1 — Automated Test Summary</a><span class="lead"></span><span class="pg">48</span></p>
<p><a href="#ch6">Table 6.1 — Model Test-Set Metrics</a><span class="lead"></span><span class="pg">52</span></p>
<p><a href="#ch6">Table 6.2 — System Strengths and Weaknesses</a><span class="lead"></span><span class="pg">56</span></p>
<p><a href="#tools">Table T.1 — Tools Used</a><span class="lead"></span><span class="pg">61</span></p>
</div>

<div style="page-break-after: always;"></div>

<div align="center">

# List of Abbreviations

</div>

| Abbreviation | Meaning |
|--------------|---------|
| API | Application Programming Interface |
| ATS | Applicant Tracking System |
| BM25 | Best Matching 25 (sparse ranking function) |
| CV | Curriculum Vitae (résumé) |
| EAR | Eye Aspect Ratio |
| HR | Human Resources |
| IPR | Iris Position Ratio |
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
| VAD | Voice Activity Detection |
| WS | WebSocket |
