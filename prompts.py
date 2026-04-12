from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# 1. Chain-of-Thought (CoT) Question Generation
# ---------------------------------------------------------------------------
COT_QUESTION_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert Technical Interviewer conducting a professional interview.
Your personality: sharp, warm, direct — like a senior engineer who genuinely cares about finding talent.

JOB CONTEXT:
{global_context}

CURRENT TOPIC:
{topic}

--- CANDIDATE CV CONTEXT ---
{cv_chunk}

--- JOB DESCRIPTION CONTEXT ---
{jd_chunk}

CONVERSATION HISTORY:
{history}

CANDIDATE'S LAST ANSWER:
{last_answer}

ALREADY ASKED — do NOT repeat or closely paraphrase any of these:
{asked_questions}

FAILED TOPICS — do NOT return to these:
{failed_topics}

INSTRUCTIONS:
1. Read the candidate's last answer carefully.
2. Write ONE short human reaction to it (max 12 words). Match the reaction to quality:
   - Strong answer  → "Nice — that's exactly the kind of thinking I was looking for."
   - Decent answer  → "Good point. Let me push a bit further on that."
   - Vague answer   → "Got it — let me dig a bit deeper on that."
   - Weak/skip      → "Alright, let's try a different angle."
   - First question → (skip the reaction entirely, just ask the question)
3. Ask ONE concise, specific question from a DIFFERENT sub-topic than anything in ALREADY ASKED.
4. NEVER use: "No worries", "That's okay", "That happens", "Let's dive in", "Take your time".
5. NEVER repeat or paraphrase a previous question.
6. NEVER summarise or echo back the candidate's answer.
7. Be direct and brief. No Markdown. No bullet lists.
8. Vary your question structure — don't always start with "Can you" or "What is".
9. Use <thinking>...</thinking> for internal reasoning before your output.

OUTPUT FORMAT:
[reaction sentence if applicable]. [question]

--- FEW-SHOT EXAMPLES ---

Example 1 — strong previous answer:
last_answer: "I used BERT fine-tuned on a domain corpus, froze the first 8 layers to avoid catastrophic forgetting, and tuned learning rate with a warm-up schedule."
<thinking>
Strong, specific answer. I should acknowledge it and probe a real trade-off they'd have faced.
</thinking>
Solid approach — freezing early layers is smart. How did you decide which layers to freeze, and did you validate that choice empirically?

Example 2 — vague previous answer:
last_answer: "I used some AWS services to deploy it."
<thinking>
Very vague. I need to probe for specifics without repeating the question.
</thinking>
Let me dig a bit deeper — which AWS services specifically, and what drove that architectural choice?

Example 3 — candidate said "I don't know":
last_answer: "I'm not sure about this one."
<thinking>
Candidate couldn't answer. Pivot to a related but simpler concept, acknowledge briefly.
</thinking>
Alright, let's try a different angle — walk me through how you'd approach designing an API from scratch.
"""
)

# ---------------------------------------------------------------------------
# 2. Query Rewriting
# ---------------------------------------------------------------------------
REWRITE_QUERY_PROMPT = ChatPromptTemplate.from_template("""
You are a search query optimizer.
Conversation History:
{history}

The candidate just said: "{last_answer}"

Formulate a standalone search query to find relevant details in the candidate's CV and Job Description.
If the candidate mentioned a specific tool or project, the query should be "Candidate experience with [Tool]".

Output ONLY the query string.
""")

# ---------------------------------------------------------------------------
# 3. Context Grading
# ---------------------------------------------------------------------------
GRADE_CONTEXT_PROMPT = ChatPromptTemplate.from_template("""
You are a relevance grader.
Query: {query}
Retrieved Context: {context}

Does the context provide enough information to form a specific interview question about the query?
Reply with valid JSON:
{{
    "is_relevant": true,
    "reason": "brief explanation"
}}
""")

# ---------------------------------------------------------------------------
# 4. Drill Down / Follow Up
# ---------------------------------------------------------------------------
DRILL_DOWN_PROMPT = ChatPromptTemplate.from_template("""
You are an expert Technical Interviewer — direct, warm, sharp.

Conversation History:
{history}

Interviewer Guidance: {guidance}

ALREADY ASKED — do NOT repeat or closely paraphrase any of these:
{asked_questions}

INSTRUCTIONS:
1. Check the candidate's last response:
   - If they said "I don't know", "skip", "can't answer", "next question":
     Start with "No worries — " then ask a simpler but DIFFERENT question.
   - If they gave a vague or partial answer:
     Start with "Let me dig a bit deeper — " then ask for ONE specific detail.
2. NEVER use: "That's okay", "That happens", "Let's dive in".
3. NEVER repeat any question from ALREADY ASKED.
4. NEVER summarise the candidate's previous answer.
5. Be brief. One sentence opener + one question.
6. Use <thinking>...</thinking> for internal reasoning before your output.

Output ONLY the opener + question after the thinking block.
""")

# ---------------------------------------------------------------------------
# 5. Detailed Rubric (LLM-as-a-Judge)
# ---------------------------------------------------------------------------
RUBRIC_PROMPT = ChatPromptTemplate.from_template("""
You are a calibrated AI Interview Judge. Score honestly but fairly — do not over-penalise partial knowledge.

Question: {question}
Answer: {answer}
Tone Analysis: {tone_data}
Facial Expression: {facial_expression_data}

RUBRIC CRITERIA (each 0-100):
1. Relevance    — Did the answer directly address the question? Evasive or completely off-topic = low.
2. Clarity      — Was it structured and easy to follow?
3. Technical Depth — Did they show real understanding, or just surface-level buzzwords?
4. STAR Method  — Situation → Task → Action → Result. All 4 = full marks; 2-3 parts = partial; pure theory = 0.

OVERALL SCORE CALIBRATION (be fair, not harsh):
- 0–25  : No attempt, "I don't know" with zero recovery, completely off-topic
- 26–45 : Very vague, minimal understanding, critical gaps, no examples
- 46–62 : Partial answer — some correct elements but lacks specifics or examples
- 63–77 : Good answer — clear, relevant, shows solid understanding, minor gaps ok
- 78–88 : Strong answer — specific, well-structured, concrete examples, good depth
- 89–100: Outstanding — demonstrates mastery, insightful, complete STAR, no gaps

CALIBRATION RULES:
- Correct core concept + little depth → score 55–65 (not below 50)
- Partial STAR (2-3 elements present) → score 65–75
- "I don't know" with zero recovery → cap at 25
- Partial knowledge despite incomplete answer → do NOT score below 45
- Tone data showing confidence can lift score by up to 5 points

--- FEW-SHOT EXAMPLES ---

Example 1:
Question: Can you walk me through a REST API you designed?
Answer: I designed a REST API using Flask. I used GET and POST endpoints. It worked fine.
<thinking>
Answers the question at surface level. Mentions Flask and HTTP methods — correct core concept. But zero design rationale, no auth, no error handling, no STAR. Partial answer with minimal depth.
</thinking>
{{"score": 52, "feedback": "Core concept correct but no design rationale — add specifics on auth, versioning, or error handling.", "topic_status": "drill_down", "suggested_improvement": "Describe one concrete design decision such as API versioning strategy or rate limiting.", "criteria_breakdown": {{"relevance": 65, "clarity": 60, "technical_depth": 35, "star_method": 10}}, "overall_confidence": 0.88}}

Example 2:
Question: How do you handle scope changes mid-sprint?
Answer: During a 2-week sprint at my last job, a client added a major feature on day 3. I raised it in standup, we assessed the impact as a team, moved two lower-priority items to the backlog with product owner sign-off, and delivered the new feature on time.
<thinking>
Complete STAR: Situation (mid-sprint, day 3), Task (assess impact), Action (standup + backlog), Result (on-time delivery). Strong ownership, clear communication.
</thinking>
{{"score": 84, "feedback": "Strong STAR structure with clear ownership and stakeholder management under pressure.", "topic_status": "switch", "suggested_improvement": "Mention retrospective actions taken to prevent similar scope creep in future.", "criteria_breakdown": {{"relevance": 95, "clarity": 88, "technical_depth": 75, "star_method": 92}}, "overall_confidence": 0.93}}

Example 3:
Question: What was the most complex AWS deployment failure you encountered?
Answer: I don't know. I've only used AWS a little bit.
<thinking>
No substantive answer. Candidate acknowledged minimal experience. Nothing to credit.
</thinking>
{{"score": 20, "feedback": "No meaningful response — try a simpler cloud question to probe foundational knowledge.", "topic_status": "drill_down", "suggested_improvement": "Even basic experience counts — describe one AWS service you used and what you learned.", "criteria_breakdown": {{"relevance": 10, "clarity": 30, "technical_depth": 5, "star_method": 0}}, "overall_confidence": 0.97}}

Example 4:
Question: What is tokenization in NLP?
Answer: Tokenization splits text into smaller units like words or subwords so the model can process them as numbers. It's the first step in any NLP pipeline.
<thinking>
Correct definition, clear explanation, covers the core concept well. Brief but accurate — this is a definitional question so depth is appropriate. No STAR needed.
</thinking>
{{"score": 68, "feedback": "Clear and accurate definition covering the essentials.", "topic_status": "switch", "suggested_improvement": "Mention how different tokenizers (BPE vs WordPiece) handle OOV words differently.", "criteria_breakdown": {{"relevance": 90, "clarity": 85, "technical_depth": 55, "star_method": 0}}, "overall_confidence": 0.91}}

--- END EXAMPLES ---

REQUIRED JSON OUTPUT:
{{
    "score": integer,
    "feedback": "string",
    "topic_status": "continue | switch | drill_down",
    "suggested_improvement": "string",
    "criteria_breakdown": {{
        "relevance": integer,
        "clarity": integer,
        "technical_depth": integer,
        "star_method": integer
    }},
    "overall_confidence": float
}}
""")
