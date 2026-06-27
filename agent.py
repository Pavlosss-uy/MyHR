import logging
import os
import re
from typing import TypedDict, List, Literal, Dict
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
import torch
from models.registry import registry
from models.feature_extractor import extractor
from models.explainer import ModelExplainer
from models.scoring_model import EmbeddingExtractor
import numpy as np

logger = logging.getLogger(__name__)

# Lazy singleton — loaded once on first scored answer, not at import time
_embedding_extractor: EmbeddingExtractor | None = None

def _get_embedding_extractor() -> EmbeddingExtractor:
    global _embedding_extractor
    if _embedding_extractor is None:
        _embedding_extractor = EmbeddingExtractor()
    return _embedding_extractor

# Import your custom modules
from retriever import retrieve_context_split
from prompts import (
    FIRST_QUESTION_PROMPT,
    COT_QUESTION_PROMPT,
    RUBRIC_PROMPT,
    REWRITE_QUERY_PROMPT,
    GRADE_CONTEXT_PROMPT,
    DRILL_DOWN_PROMPT,
    REPORT_SYNTHESIS_PROMPT,
)

# --- State Definitions ---
class CriteriaBreakdown(BaseModel):
    relevance: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    technical_depth: int = Field(ge=0, le=100)
    star_method: int = Field(ge=0, le=100)

class EvaluationResult(BaseModel):
    score: int = Field(description="Score 0-100 reflecting overall answer quality. Off-topic=20-35, I_dont_know=16-42, weak=43-55, partial=56-68, good=69-80, strong=81-90, outstanding=91-100.", ge=0, le=100)
    answer_classification: Literal["STRONG", "PARTIAL", "WEAK", "I_DONT_KNOW", "OFF_TOPIC"] = Field(description="Classification of the answer type")
    feedback: str = Field(description="2 sentences: first states what was specifically right or wrong (concrete), second explains why it matters for this role")
    topic_status: Literal["continue", "switch", "drill_down"] = Field(description="Next move: I_DONT_KNOW→drill_down, OFF_TOPIC→switch, WEAK→drill_down, PARTIAL→continue/switch, STRONG→switch")
    suggested_improvement: str = Field(description="One concrete, actionable step the candidate can take to improve")
    criteria_breakdown: CriteriaBreakdown = Field(description="Per-criterion scores for relevance, clarity, technical_depth, and star_method")
    overall_confidence: float = Field(description="Judge's confidence in this evaluation (0.0-1.0)", ge=0.0, le=1.0)

class GradeResult(BaseModel):
    is_relevant: bool = Field(description="Is the context useful?")

class AgentState(TypedDict, total=False):
    session_id: str
    conversation_history: List[str]
    current_topic: str
    initial_job_context: Dict
    current_search_query: str
    retrieved_context: str
    cv_chunk: str
    jd_chunk: str
    loop_count: int
    drill_down_count: int
    last_question: str
    last_answer: str
    multimodal_analysis: dict
    facial_expression_data: dict
    proctoring_data: dict
    evaluations: List[dict]
    next_action: str
    question_number: int
    asked_questions: List[str]
    failed_topics: List[str]
    consecutive_fails: int
    current_difficulty: int
    skill_match_score: float
    predicted_performance: float
    interview_mode: str  # "first_question" | "normal" | "fallback" | "end"


# --- Interview bounds (shared with decide_next_step and generate_question_node) ---
MIN_QUESTIONS = 5   # Minimum before any early-stop evaluation runs
MAX_QUESTIONS = 7   # Hard ceiling on questions per session

# Task 1.8 — adaptive-difficulty policy selection. PPO is the deployed default
# (in-zone 78.8% vs REINFORCE 64.9%); set DIFFICULTY_POLICY=reinforce for ablation.
DIFFICULTY_POLICY = os.getenv("DIFFICULTY_POLICY", "ppo").strip().lower()
_USE_PPO_DIFFICULTY = DIFFICULTY_POLICY != "reinforce"

# Blend weights: LLM score / neural evaluator / MOD-1 scorer.
# When MOD-1 is available (scorer checkpoint loaded), use 3-way blend.
# When MOD-1 is unavailable, collapse to 2-way blend with matching LLM weight.
_BLEND_3WAY: dict[str, float] = {"llm": 0.65, "neural": 0.20, "mod1": 0.15}
_BLEND_2WAY: dict[str, float] = {"llm": 0.65, "neural": 0.35, "mod1": 0.0}

def _strip_thinking(content: str) -> str:
    if not content:
        return ""
    return content.split("</thinking>")[-1].strip()


def _is_valid_question(question: str) -> bool:
    """
    Reject questions that are too basic, malformed, or compound.
    Returns True if the question passes quality checks.
    """
    if not question or len(question.strip()) < 20:
        return False

    lower = question.lower().strip()

    # Reject trivially basic questions unsuitable for a professional interview
    beginner_patterns = [
        r'\bwhat is a variable\b',
        r'\bwhat is a loop\b',
        r'\bwhat is a function\b',
        r'\bwhat is a class\b',
        r'\bhow do you print\b',
        r'\bwhat does print\b',
        r'\bwhat is a string\b',
        r'\bwhat is an array\b',
        r'\bwhat is an integer\b',
        r'\bhow do you declare a variable\b',
    ]
    for pat in beginner_patterns:
        if re.search(pat, lower):
            return False

    # Reject compound questions (more than 2 question marks = multiple questions)
    if question.count('?') > 2:
        return False

    # Reject empty-ish output or just a reaction without a question
    if '?' not in question:
        return False

    return True


# --- Grounding guard (anti-hallucination) ---
# When CV retrieval fails, cv_chunk is a placeholder. Feeding that to the LLM lets
# it INVENT experience the candidate never wrote. These helpers detect that case so
# we fall back to CV-agnostic questions instead of hallucinating CV details.
_CV_PLACEHOLDERS = (
    "no cv context found",
    "no specific context found",
    "no relevant context found",
)

_GENERIC_QUESTIONS = [
    "Walk me through the most technically challenging project you've worked on — what made it hard and how did you approach it?",
    "Tell me about a time you had to debug a difficult production issue. What was the problem and how did you resolve it?",
    "Describe a technical decision you're proud of. What were the trade-offs you weighed?",
    "How do you go about learning a new technology or framework when a project requires it?",
    "Tell me about a time you disagreed with a teammate on a technical approach — how did you resolve it?",
]


def _has_grounded_cv(cv_chunk: str) -> bool:
    """True only when retrieval returned REAL CV content (not a placeholder)."""
    if not cv_chunk:
        return False
    text = cv_chunk.strip().lower()
    if len(text) < 20:
        return False
    return not any(p in text for p in _CV_PLACEHOLDERS)


def _generic_question(n: int) -> str:
    """A CV-agnostic question, rotated by question number to avoid repetition."""
    return _GENERIC_QUESTIONS[int(n) % len(_GENERIC_QUESTIONS)]


# --- LLM CONFIGURATION ---
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3
)

# --- Nodes ---

def rewrite_query_node(state: AgentState):
    """Transforms user intent into a specific search query."""
    history = state.get("conversation_history", [])
    last_answer = state.get("last_answer", "")

    chain = REWRITE_QUERY_PROMPT | llm
    response = chain.invoke({"history": str(history[-3:]), "last_answer": last_answer})

    logger.debug("Rewrote Query: %s", response.content)
    return {"current_search_query": response.content.strip(), "loop_count": state.get("loop_count", 0)}

def retrieve_node(state: AgentState):
    """Uses the Advanced Hybrid Retriever. Populates both unified and split context."""
    session_id = state["session_id"]
    query = state.get("current_search_query", state["current_topic"])

    try:
        cv_chunk, jd_chunk = retrieve_context_split(session_id, query)
        context = f"{cv_chunk}\n\n{jd_chunk}".strip()
    except Exception as e:
        logger.error("Retrieval Error: %s", e)
        context = "No specific context found."
        cv_chunk = "No CV context found."
        jd_chunk = "No JD context found."

    return {"retrieved_context": context, "cv_chunk": cv_chunk, "jd_chunk": jd_chunk}

def grade_context_node(state: AgentState):
    """Checks if the retrieved documents are relevant."""
    query = state["current_search_query"]
    context = state["retrieved_context"]

    structured_llm = llm.with_structured_output(GradeResult, method="json_mode")
    chain = GRADE_CONTEXT_PROMPT | structured_llm

    grade = chain.invoke({"query": query, "context": context})

    if state.get("loop_count", 0) > 2:
        return {"next_action": "generate"}

    if grade.is_relevant:
        return {"next_action": "generate"}
    else:
        return {"next_action": "rewrite_query", "loop_count": state["loop_count"] + 1}

def generate_question_node(state: AgentState):
    """Generates the question using Adaptive Difficulty + mode-specific prompt."""

    # --- Adaptive Difficulty Integration ---
    # Policy chosen by DIFFICULTY_POLICY env (default PPO). PPO loader auto-falls
    # back to REINFORCE if stable-baselines3 / the checkpoint is unavailable.
    diff_engine = registry.load_difficulty_engine(use_ppo=_USE_PPO_DIFFICULTY)

    score_history = [e['score'] for e in state.get("evaluations", [])]
    current_diff  = state.get("current_difficulty", 3)
    n_questions   = len(score_history)

    avg_score_norm = (sum(score_history) / len(score_history) / 100.0) if score_history else 0.5
    if len(score_history) >= 2:
        trend = float(np.clip(((score_history[-1] - score_history[-2]) / 100.0 + 1.0) / 2.0, 0.0, 1.0))
    else:
        trend = 0.5
    current_diff_norm        = current_diff / 5.0
    engagement               = 0.8
    topic_diversity          = min(1.0, n_questions / MAX_QUESTIONS)
    questions_remaining_norm = max(0.0, 1.0 - n_questions / MAX_QUESTIONS)
    obs = np.array([avg_score_norm, trend, current_diff_norm, engagement,
                    topic_diversity, questions_remaining_norm], dtype=np.float32)

    try:
        action, _ = diff_engine.predict(obs, deterministic=True)
        next_diff = int(action) + 1  # 0-4 → 1-5
    except AttributeError:
        diff_result = diff_engine.decide_next_difficulty(score_history, current_diff)
        next_diff = diff_result[0] if isinstance(diff_result, tuple) else diff_result

    difficulty_guidance = f" Set question difficulty to Level {next_diff}/5."

    asked_questions = state.get("asked_questions", [])
    failed_topics   = state.get("failed_topics", [])
    interview_mode  = state.get("interview_mode", "normal")

    job_context = state.get("initial_job_context", {})
    global_context = (
        f"Job Title: {job_context.get('job_title', 'N/A')}\n"
        f"Candidate: {job_context.get('candidate_name', 'Candidate')}"
    )
    # Use pre-extracted concise JD signals (not the raw verbose chunk)
    jd_signals = job_context.get("jd_signals", state.get("jd_chunk", "No JD signals available."))

    # ── MODE: first_question ────────────────────────────────────────────────
    if interview_mode == "first_question":
        logger.debug("Mode: FIRST_QUESTION (Diff: %s)", next_diff)

        # Anti-hallucination: if retrieval gave no real CV, ask a CV-agnostic
        # opener instead of inventing the candidate's experience.
        cv_chunk = state.get("cv_chunk", "No CV context found.")
        if not _has_grounded_cv(cv_chunk):
            logger.warning("No grounded CV context — using a CV-agnostic opener (avoids hallucination).")
            content = _generic_question(0)
            return {
                "last_question": content,
                "loop_count": 0,
                "current_difficulty": next_diff,
                "asked_questions": asked_questions + [content],
                "question_number": state.get("question_number", 1) + 1,
                "interview_mode": "normal",
            }

        chain = FIRST_QUESTION_PROMPT | llm

        max_attempts = 3
        content = ""
        for attempt in range(max_attempts):
            response = chain.invoke({
                "global_context": global_context,
                "cv_chunk": state.get("cv_chunk", "No CV context found."),
                "jd_signals": jd_signals,
            })
            content = _strip_thinking(response.content)
            if _is_valid_question(content):
                break
            logger.debug("  First-question attempt %d rejected: %s...", attempt + 1, content[:60])
        else:
            # Fallback to a safe generic opener
            job_title = job_context.get('job_title', 'this role')
            content = f"Walk me through the most technically challenging project you've worked on that's relevant to {job_title}."

        return {
            "last_question": content,
            "loop_count": 0,
            "current_difficulty": next_diff,
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
            "interview_mode": "normal",  # transition → normal after first question
        }

    # ── MODE: fallback (drill-down) ─────────────────────────────────────────
    if interview_mode == "fallback" or state.get("next_action") == "drill_down":
        logger.debug("Mode: FALLBACK (Diff: %s)", next_diff)
        chain = DRILL_DOWN_PROMPT | llm
        guidance = "The candidate struggled with the last question. Ask a concretely simpler version." + difficulty_guidance

        max_attempts = 3
        content = ""
        for attempt in range(max_attempts):
            response = chain.invoke({
                "history": state.get("conversation_history", []),
                "guidance": guidance,
                "jd_signals": jd_signals,
                "asked_questions": "\n".join(f"- {q}" for q in asked_questions) or "None yet.",
            })
            content = _strip_thinking(response.content)

            # Ensure the required prefix is present
            if not content.startswith("No problem"):
                content = "No problem, let's try a simpler one. " + content.lstrip()

            if _is_valid_question(content):
                break
            logger.debug("  Fallback attempt %d rejected: %s...", attempt + 1, content[:60])

        return {
            "last_question": content,
            "loop_count": 0,
            "current_difficulty": max(1, next_diff - 1),  # fallback = easier
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
            "interview_mode": "normal",  # return to normal after fallback
        }

    # ── MODE: normal (CoT) ───────────────────────────────────────────────────
    logger.debug("Mode: NORMAL (Diff: %s)", next_diff)

    # Anti-hallucination: no real CV → ask a CV-agnostic question rather than
    # letting the LLM invent the candidate's projects/skills.
    cv_chunk_norm = state.get("cv_chunk", "No CV context found.")
    if not _has_grounded_cv(cv_chunk_norm):
        logger.warning("No grounded CV context — asking a generic question (avoids hallucination).")
        content = _generic_question(state.get("question_number", 1))
        return {
            "last_question": content,
            "current_topic": state.get("current_topic", "General"),
            "loop_count": 0,
            "current_difficulty": next_diff,
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
            "interview_mode": "normal",
        }

    chain = COT_QUESTION_PROMPT | llm
    guidance = "Ask a natural interview question." + difficulty_guidance
    if state.get("next_action") == "switch":
        guidance = (
            "Transition to a COMPLETELY different technical topic — "
            "do NOT revisit any failed topics listed below." + difficulty_guidance
        )

    raw_query = state.get("current_search_query", "").strip()
    derived_topic = " ".join(raw_query.split()[:4]).title() if raw_query else state.get("current_topic", "General")

    last_answer = state.get("last_answer", "").strip()
    if not last_answer or last_answer == state.get("last_question", ""):
        last_answer = ""

    max_attempts = 3
    content = ""
    for attempt in range(max_attempts):
        response = chain.invoke({
            "global_context": global_context,
            "cv_chunk": state.get("cv_chunk", "No CV context found."),
            "jd_signals": jd_signals,
            "history": state.get("conversation_history", []),
            "topic": derived_topic,
            "guidance": guidance,
            "last_answer": last_answer or "(First question — no previous answer yet.)",
            "asked_questions": "\n".join(f"- {q}" for q in asked_questions) or "None yet.",
            "failed_topics": "\n".join(f"- {t}" for t in failed_topics) or "None.",
        })
        content = _strip_thinking(response.content)
        if _is_valid_question(content):
            break
        logger.debug("  Normal attempt %d rejected: %s...", attempt + 1, content[:60])
    else:
        # Generic safe fallback
        content = "Walk me through a time you had to debug a difficult production issue — what was the problem and how did you resolve it?"

    return {
        "last_question": content,
        "current_topic": derived_topic,
        "loop_count": 0,
        "current_difficulty": next_diff,
        "asked_questions": asked_questions + [content],
        "question_number": state.get("question_number", 1) + 1,
        "interview_mode": "normal",
    }

def evaluate_answer_node(state: AgentState):
    """Evaluates answer using Multi-Head Evaluator (MOD-4) + Performance Predictor (MOD-6)."""

    # 1. Load Models from Registry
    evaluator = registry.load_evaluator()
    predictor = registry.load_performance_predictor()  # may be None if checkpoint missing

    # 2. Extract the 8 real features for the neural networks
    tone_data = state.get("multimodal_analysis", {})
    features = extractor.extract(
        question=state.get("last_question", ""),
        answer=state.get("last_answer", ""),
        jd_text=state.get("initial_job_context", {}).get("jd_text", ""),
        cv_text=state.get("retrieved_context", ""),
        tone_data=tone_data,
        conversation_history=state.get("conversation_history", []),
        precomputed_skill_match=state.get("skill_match_score"),
    )

    if not isinstance(features, torch.Tensor):
        features = torch.tensor(features, dtype=torch.float32)
    if features.ndim == 1:
        features = features.unsqueeze(0)

    # 3. Neural Evaluation (MOD-4) — evaluator expects 768-D all-mpnet-base-v2 answer embedding
    answer_text = state.get("last_answer", "")
    if extractor.embedder is not None:
        # extractor.embedder is an EmbeddingExtractor; use its cached encode method
        answer_emb_tensor = extractor.embedder._encode_cached(answer_text).unsqueeze(0).float()
    else:
        # Fallback: zero vector so the call doesn't crash when the embedder failed to load
        answer_emb_tensor = torch.zeros(1, 768, dtype=torch.float32)
    answer_emb_tensor = answer_emb_tensor.to(next(evaluator.parameters()).device)
    neural_results = evaluator.evaluate_answer(answer_emb_tensor)

    # 4. Performance Prediction (MOD-6) — gracefully omitted if predictor unavailable
    if predictor is not None:
        predictor_device = next(predictor.parameters()).device
        job_prediction = predictor.predict_performance(features.to(predictor_device))
    else:
        job_prediction = None

    # 5. Explainability (SHAP) — requires a working predictor as the explained model
    feature_names = [
        "skill_match", "relevance", "clarity", "depth",
        "confidence", "consistency", "gaps_inverted", "experience"
    ]

    shap_values_list = []
    feature_values_list = features.detach().cpu().numpy().flatten().tolist()
    shap_summary = {}
    expected_value = None

    if predictor is not None:
        try:
            explainer = ModelExplainer(predictor, feature_names)

            center = features.detach().cpu().numpy()[0]
            noise = np.random.normal(loc=0.0, scale=0.05, size=(20, len(feature_names)))
            background_data = np.clip(center + noise, 0.0, 1.0).astype(np.float32)

            shap_values, expected_value = explainer.explain_prediction(features, background_data)

            shap_values_np = np.asarray(shap_values, dtype=np.float32)
            shap_values_list = shap_values_np.flatten().tolist()
            shap_summary = dict(zip(feature_names, shap_values_np.flatten().tolist()))

            os.makedirs("reports", exist_ok=True)
            explainer.plot_waterfall(
                shap_values=shap_values_np,
                features=features,
                expected_value=expected_value,
                save_path=f"reports/shap_{state['session_id']}.png"
            )

        except Exception as e:
            logger.warning("SHAP Error: %s", e)
    else:
        logger.debug("SHAP skipped — performance predictor unavailable.")

    # 6. LLM generates feedback text — guard against placeholder tone data
    if not tone_data or tone_data.get("primary_emotion") == "Processing...":
        tone_data = {"primary_emotion": "neutral", "full_analysis": {}, "confidence": 0.5}

    facial_expression_data = state.get("facial_expression_data", {})
    interview_mode = state.get("interview_mode", "normal")

    structured_llm = llm.with_structured_output(EvaluationResult, method="json_mode")
    chain = RUBRIC_PROMPT | structured_llm

    res = chain.invoke({
        "interview_mode": interview_mode,
        "question": state["last_question"],
        "answer": state["last_answer"],
        "tone_data": str(tone_data),
        "facial_expression_data": str(facial_expression_data) if facial_expression_data else "Not available",
    })

    llm_score = float(res.score)
    neural_score = float(neural_results["overall"])

    # --- MOD-1: CandidateScoringMLP + Q↔A Relevance Gate ---
    # The relevance gate computes cosine similarity between question and answer
    # embeddings. A fluent but off-topic or empty answer has low Q↔A similarity,
    # so its neural score is scaled down before blending — without any hardcoded
    # classification caps. The embeddings are cached so the extra encode is free.
    mod1_score = None
    adjusted_neural = neural_score  # fallback: no gate applied
    try:
        scorer_model = registry.load_scorer()
        emb_extractor = _get_embedding_extractor()
        with torch.no_grad():
            emb_features = emb_extractor.extract(
                question=state.get("last_question", ""),
                answer=state.get("last_answer", ""),
                tone_data=tone_data,
            )
            mod1_score = float(scorer_model(emb_features).item())
            mod1_score = max(0.0, min(mod1_score, 100.0))

            # Q↔A cosine similarity — hits cache, no extra encode cost
            q_emb = emb_extractor._encode_cached(state.get("last_question", ""))
            a_emb = emb_extractor._encode_cached(state.get("last_answer", ""))
            cosine_sim = float(
                torch.nn.functional.cosine_similarity(
                    q_emb.unsqueeze(0), a_emb.unsqueeze(0)
                ).item()
            )
            # Linear scale: sim=0 → factor=0, sim≥0.5 → factor=1.0
            # Interview answers rarely exceed 0.7 similarity even when excellent,
            # so 0.5 as the "full relevance" ceiling is well-calibrated.
            relevance_factor = min(1.0, max(0.0, cosine_sim) / 0.5)
            adjusted_neural = neural_score * relevance_factor
            logger.debug("MOD-1 Score: %.1f/100", mod1_score)
            logger.debug("Q↔A Cosine: %.3f | Relevance factor: %.2f | Neural: %.1f → %.1f", cosine_sim, relevance_factor, neural_score, adjusted_neural)
    except Exception as e:
        logger.warning("MOD-1/relevance gate skipped (%s)", e)

    # --- Final blend: 65% LLM / 35% neural ---
    # Both neural models now discriminate quality (MOD-4 retrained on mpnet, MOD-1
    # retrained without the leaky tone features), so we give them a real 35% say
    # instead of the old ~20%. The Q↔A relevance gate stays on the evaluator
    # (adjusted_neural) so off-topic answers can't ride a high neural score.
    # The old neural-flat / divergence special-cases are gone — clean & predictable.
    w = _BLEND_3WAY if mod1_score is not None else _BLEND_2WAY
    blended_score = round(
        w["llm"] * llm_score + w["neural"] * adjusted_neural + w["mod1"] * (mod1_score or 0.0), 1
    )
    if mod1_score is not None:
        logger.debug(
            "Blend 65/20/15 — LLM %.0f / Eval %.0f / MOD-1 %.0f → %.1f",
            llm_score, adjusted_neural, mod1_score, blended_score,
        )
    else:
        logger.debug("Blend 65/35 — LLM %.0f / Eval %.0f → %.1f", llm_score, adjusted_neural, blended_score)

    # --- Proctoring Score Penalty ---
    # Apply penalty for violations detected during this answer.
    integrity_data = state.get("proctoring_data", {})
    integrity_penalty = 0.0
    if integrity_data.get("multiple_faces_detected"):
        integrity_penalty = 8.0
    elif integrity_data.get("suspicious"):
        integrity_penalty = 5.0
        
    if integrity_penalty > 0:
        blended_score = max(0.0, round(blended_score - integrity_penalty, 1))
        logger.warning("[PROCTOR] Applying -%s penalty to answer due to violations. New score: %s", integrity_penalty, blended_score)

    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": blended_score,
        "llm_score": llm_score,
        "neural_score": neural_score,
        "mod1_score": mod1_score,
        "score_weights": w,
        "answer_classification": res.answer_classification,
        "detailed_scores": neural_results,
        "predicted_market_positioning": job_prediction,
        "feedback": res.feedback,
        "suggested_improvement": res.suggested_improvement,
        "criteria_breakdown": res.criteria_breakdown.model_dump(),
        "overall_confidence": res.overall_confidence,
        "tone_data": tone_data,
        "integrity": integrity_data,
        "integrity_penalty": integrity_penalty,
        "feature_values": feature_values_list,
        "shap_values": shap_values_list,
        "feature_importance": shap_summary,
        "shap_expected_value": float(np.ravel(expected_value)[0]) if expected_value is not None else None
    }

    mod1_str = f" | MOD-1: {mod1_score:.1f}/100" if mod1_score is not None else ""
    logger.info("LLM Score: %s/100 | Neural Score: %s/100%s | Blended: %s/100", llm_score, neural_score, mod1_str, blended_score)
    logger.debug("Predicted Market Positioning: %s/10.0", job_prediction)

    return {
        "evaluations": state.get("evaluations", []) + [report_entry],
        "next_action": res.topic_status,
        "predicted_performance": job_prediction
    }


def _build_question_scores(evaluations: list) -> list:
    """Build the question_scores list from raw evaluation entries."""
    result = []
    for i, e in enumerate(evaluations, 1):
        entry = {
            "index": i,
            "question": e.get("question", ""),
            "answer": e.get("answer", ""),
            "score": e.get("score", 0),
            "llm_score": e.get("llm_score"),
            "neural_score": e.get("neural_score"),
            "mod1_score": e.get("mod1_score"),
            "score_weights": e.get("score_weights"),
            "classification": e.get("answer_classification", ""),
            "feedback": e.get("feedback", ""),
            "suggested_improvement": e.get("suggested_improvement", ""),
            "criteria_breakdown": e.get("criteria_breakdown", {}),
        }
        result.append(entry)
    return result


def _build_communication_from_tone(evaluations: list) -> dict:
    """
    Derive a flat communication dict by aggregating per-evaluation tone data.
    Returns defaults when no tone data is available.
    """
    emotions = []
    confidences = []

    for e in evaluations:
        t = e.get("tone_data", {})
        if not t:
            continue
        em = t.get("primary_emotion", "")
        conf = t.get("confidence", None)
        if em and em not in ("Processing...", "error", ""):
            emotions.append(em)
        if conf is not None:
            try:
                confidences.append(float(conf))
            except (TypeError, ValueError):
                pass

    if not emotions:
        return {
            "tone": "neutral",
            "confidence": "medium",
            "clarity": "mostly clear",
            "feedback": "Tone analysis was not available for this session.",
        }

    # Most frequent dominant emotion
    from collections import Counter
    tone = Counter(emotions).most_common(1)[0][0]

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    if avg_conf >= 0.70:
        confidence_level = "high"
    elif avg_conf >= 0.45:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    # Derive clarity heuristic from confidence + tone
    nervous_tones = {"fear", "anxiety", "nervousness", "nervous", "sad", "sadness"}
    calm_tones = {"neutral", "calm", "confident", "happy", "joy"}
    if tone.lower() in nervous_tones or avg_conf < 0.40:
        clarity = "unclear"
    elif tone.lower() in calm_tones:
        clarity = "clear"
    else:
        clarity = "mostly clear"

    feedback_map = {
        "high": "Your tone was confident and composed throughout the interview — this projects credibility effectively.",
        "medium": "Your tone was generally steady, though some answers showed hesitation. Practising out loud will build consistency.",
        "low": "The voice analysis detected signs of nervousness or uncertainty in several answers. Structured practice and mock interviews can help project more confidence.",
    }

    return {
        "tone": tone,
        "confidence": confidence_level,
        "clarity": clarity,
        "feedback": feedback_map[confidence_level],
    }


def _normalize_report(raw: dict, evaluations: list, avg_score: float) -> dict:
    """
    Enforce the canonical report structure. Fills every required field so the
    object returned to the frontend and saved to disk are identical and complete.

    Supports both old key names (weaknesses, improvements, communication_analysis)
    and new canonical names (areas_to_improve, how_to_improve, tone_analysis).
    Both are always present so old cached reports and new ones render identically.
    """
    # --- question_scores ---
    raw.setdefault("question_scores", _build_question_scores(evaluations))

    # --- key-name aliases (old ↔ new, bidirectional) ---
    # areas_to_improve ↔ weaknesses
    if "areas_to_improve" in raw and "weaknesses" not in raw:
        raw["weaknesses"] = raw["areas_to_improve"]
    elif "weaknesses" in raw and "areas_to_improve" not in raw:
        raw["areas_to_improve"] = raw["weaknesses"]

    # how_to_improve ↔ improvements
    if "how_to_improve" in raw and "improvements" not in raw:
        raw["improvements"] = raw["how_to_improve"]
    elif "improvements" in raw and "how_to_improve" not in raw:
        raw["how_to_improve"] = raw["improvements"]

    # tone_analysis ↔ communication_analysis
    if "tone_analysis" in raw and "communication_analysis" not in raw:
        raw["communication_analysis"] = raw["tone_analysis"]
    elif "communication_analysis" in raw and "tone_analysis" not in raw:
        raw["tone_analysis"] = raw["communication_analysis"]

    # --- flat communication block ---
    # Prefer LLM-generated tone_analysis / communication_analysis if present
    ca = raw.get("tone_analysis") or raw.get("communication_analysis") or {}
    if ca and isinstance(ca, dict):
        comm = {
            "tone":       ca.get("overall_tone", "neutral"),
            "confidence": ca.get("confidence_level", "medium"),
            "clarity":    ca.get("clarity_of_speech", "mostly clear"),
            "feedback":   " ".join(ca.get("recommendations", [])) or
                          (ca.get("observations") or [""])[0] or
                          "No communication feedback available.",
        }
    else:
        comm = _build_communication_from_tone(evaluations)

    raw["communication"] = comm

    # --- required top-level fields with safe defaults ---
    raw.setdefault("overall_score", avg_score)
    raw.setdefault("strengths", [])
    raw.setdefault("weaknesses", [])
    raw.setdefault("areas_to_improve", raw["weaknesses"])
    raw.setdefault("improvements", [])
    raw.setdefault("how_to_improve", raw["improvements"])
    raw.setdefault("tips", [])
    raw.setdefault("recommended_topics", [])

    # Flatten simple string-list fields (tips, recommended_topics).
    # Structured object fields (strengths, areas_to_improve, how_to_improve)
    # must be preserved as lists of dicts — the frontend reads their nested keys.
    def _to_str_list(items):
        result = []
        for item in (items or []):
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("text") or item.get("description") or item.get("content") or str(item))
            elif item is not None:
                result.append(str(item))
        return result

    def _to_dict_list(items):
        return [item for item in (items or []) if isinstance(item, dict)]

    for _field in ("recommended_topics", "weaknesses", "improvements"):
        raw[_field] = _to_str_list(raw.get(_field, []))

    for _field in ("strengths", "areas_to_improve", "how_to_improve", "tips"):
        raw[_field] = _to_dict_list(raw.get(_field, []))
    raw.setdefault("performance_level", (
        "Excellent"        if avg_score >= 85 else
        "Good"             if avg_score >= 70 else
        "Needs Improvement" if avg_score >= 55 else
        "Below Average"    if avg_score >= 30 else "Poor"
    ))
    raw.setdefault("summary", "")

    # --- hiring_signal: canonical 3-level (Yes / Borderline / No) ---
    # Accept legacy 5-level values from old stored reports and map them.
    legacy_map = {
        "Strong Yes": "Yes",
        "Yes":        "Yes",
        "Maybe":      "Borderline",
        "No":         "No",
        "Strong No":  "No",
    }
    existing_signal = raw.get("hiring_signal", "")
    # Inject the computed hiring_signal and integrity back into the report
    raw["hiring_signal"] = raw.get("hiring_signal", "Borderline")
    raw["integrity"] = _aggregate_session_integrity(evaluations)

    if existing_signal in legacy_map:
        raw["hiring_signal"] = legacy_map[existing_signal]
    elif raw["hiring_signal"] not in ("Yes", "Borderline", "No"):
        # Generate from score if missing or unrecognised
        raw["hiring_signal"] = (
            "Yes"       if avg_score >= 85 else
            "Borderline" if avg_score >= 70 else
            "No"
        )

    # Ensure tone_analysis always present (alias may have been set above; fill defaults if not)
    raw.setdefault("tone_analysis", raw.get("communication_analysis", {}))

    return raw


def _aggregate_session_integrity(evaluations: list) -> dict:
    """Roll up per-answer integrity dicts into one session-level proctoring summary
    for the HR reviewer. Worst-case across answers drives the flags.
    """
    per_answer = [e.get("integrity", {}) for e in evaluations if e.get("integrity")]
    if not per_answer:
        return {
            "face_absent_pct": 0.0,
            "looking_away_pct": 0.0,
            "multiple_faces_detected": False,
            "answers_flagged": 0,
            "suspicious": False,
            "available": False,
        }

    n = len(per_answer)
    max_absent = max(float(p.get("face_absent_pct", 0.0)) for p in per_answer)
    mean_away = round(sum(float(p.get("looking_away_pct", 0.0)) for p in per_answer) / n, 3)
    multi = any(bool(p.get("multiple_faces_detected", False)) for p in per_answer)
    flagged = sum(1 for p in per_answer if p.get("suspicious", False))
    total_violations = sum(int(p.get("violation_count", 0)) for p in per_answer)
    max_suspicion_score = max((float(p.get("suspicion_score", 0)) for p in per_answer), default=0.0)

    # Calculate overall integrity grade
    is_suspicious = bool(multi or max_absent > 0.20 or mean_away > 0.30 or flagged > 0)
    
    if multi or flagged > 2 or max_suspicion_score > 60:
        grade = "Critical"
    elif is_suspicious or total_violations > 5:
        grade = "Flagged"
    elif total_violations > 1:
        grade = "Minor Concerns"
    else:
        grade = "Clean"

    return {
        "face_absent_pct": round(max_absent, 3),
        "looking_away_pct": mean_away,
        "multiple_faces_detected": multi,
        "answers_flagged": flagged,
        "total_violations": total_violations,
        "max_suspicion_score": max_suspicion_score,
        "suspicious": is_suspicious,
        "integrity_grade": grade,
        "available": True,
    }


def synthesize_report(session_state: dict, candidate_name: str, job_title: str) -> dict:
    """
    Generate the single authoritative report for an interview session.
    The returned dict is the exact object that is:
      - returned to the API caller
      - saved to storage via save_rich_report
      - served on any later retrieval
    No further transformation or re-generation occurs after this call.

    When evaluations are missing (e.g. due to a scoring crash), the function
    falls back to synthesising a qualitative report from conversation_history.
    """
    evaluations = session_state.get("evaluations", [])
    if not evaluations:
        # Fallback: build a minimal transcript from conversation_history so the
        # LLM can still produce a qualitative report (no ML-based score available).
        conversation_history = session_state.get("conversation_history", [])
        if not conversation_history:
            return {}

        # Build numbered Q&A pairs from alternating AI/Candidate lines
        qa_pairs = []
        pending_q = None
        for line in conversation_history:
            if line.startswith("AI:"):
                if pending_q:
                    qa_pairs.append({"question": pending_q, "answer": "(no answer recorded)", "score": 0})
                pending_q = line[3:].strip()
            elif line.startswith("Candidate:") and pending_q:
                qa_pairs.append({"question": pending_q, "answer": line[10:].strip(), "score": 0})
                pending_q = None
        if pending_q:
            qa_pairs.append({"question": pending_q, "answer": "(no answer recorded)", "score": 0})

        if not qa_pairs:
            return {}

        # Synthesize using the same prompt with a note that scoring was unavailable
        transcript_lines = []
        for i, e in enumerate(qa_pairs, 1):
            transcript_lines.append(
                f"Q{i}: {e['question']}\n"
                f"Answer: {e['answer']}\n"
                f"Score: N/A (scoring system was unavailable for this session)\n"
            )
        transcript = "\n---\n".join(transcript_lines)

        # Use 50 as a neutral placeholder score — LLM will determine real hiring signal
        fallback_avg = 50.0
        inputs = {
            "candidate_name": candidate_name,
            "job_title": job_title,
            "average_score": fallback_avg,
            "transcript": transcript,
            "tone_summary": "Tone analysis not available for this session.",
            "integrity_summary": "Integrity data not available.",
        }
        try:
            chain = REPORT_SYNTHESIS_PROMPT | llm
            response = chain.invoke(inputs)
            content = _strip_thinking(response.content)
            import json as _json_mod
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            raw = _json_mod.loads(json_match.group() if json_match else content)
            raw["overall_score"] = raw.get("overall_score") or fallback_avg
            raw["_scoring_note"] = "Numeric scores were unavailable for this session; qualitative report only."
            fake_evals = [{"score": 0, "question": e["question"], "answer": e["answer"]} for e in qa_pairs]
            return _normalize_report(raw, fake_evals, fallback_avg)
        except Exception as exc:
            logger.error("synthesize_report fallback (no evals) error: %s", exc)
            return {}

    avg_score = round(sum(e["score"] for e in evaluations) / len(evaluations), 1)

    # Apply proctoring penalty (capped at −10 points, never pushes below 0)
    # Critical = multiple faces or extreme absence → −10; Flagged → −5; Minor → −2
    _integrity = _aggregate_session_integrity(evaluations)
    _grade = _integrity.get("integrity_grade", "Clean")
    _proctor_penalty = {"Critical": 10.0, "Flagged": 5.0, "Minor Concerns": 2.0}.get(_grade, 0.0)
    if _proctor_penalty:
        avg_score = round(max(0.0, avg_score - _proctor_penalty), 1)
        logger.info(
            "synthesize_report: integrity grade=%s, applied -%s penalty → adjusted score=%.1f",
            _grade, _proctor_penalty, avg_score,
        )

    # Build a readable transcript including classification for the prompt
    transcript_lines = []
    for i, e in enumerate(evaluations, 1):
        classification = e.get("answer_classification", "")
        transcript_lines.append(
            f"Q{i}: {e.get('question', '')}\n"
            f"Answer: {e.get('answer', '')}\n"
            f"Classification: {classification or 'N/A'}\n"
            f"Score: {e.get('score', 0)}/100\n"
            f"AI Feedback: {e.get('feedback', '')}\n"
        )
    transcript = "\n---\n".join(transcript_lines)

    # Build tone summary from per-evaluation tone data
    tone_entries = []
    for i, e in enumerate(evaluations, 1):
        t = e.get("tone_data", {})
        if not t:
            continue
        emotion = t.get("primary_emotion", "")
        confidence = t.get("confidence", 0.0)
        full = t.get("full_analysis", {})
        if emotion and emotion not in ("Processing...", "neutral", "error"):
            detail = ""
            if full and isinstance(full, dict):
                # Show top 2 tones by percentage
                sorted_tones = sorted(
                    [(k, v) for k, v in full.items() if isinstance(v, str) and v.endswith("%")],
                    key=lambda x: float(x[1].rstrip("%")), reverse=True
                )[:2]
                detail = ", ".join(f"{k}: {v}" for k, v in sorted_tones)
            tone_entries.append(
                f"Q{i}: dominant={emotion}, confidence={confidence:.0%}"
                + (f" ({detail})" if detail else "")
            )
        elif emotion == "neutral" or not emotion:
            tone_entries.append(f"Q{i}: neutral tone detected")

    if tone_entries:
        tone_summary = "\n".join(tone_entries)
    else:
        tone_summary = "Tone analysis not available for this session."

    # Determine pass/fail signal
    avg_score = sum(e.get("score", 0) for e in evaluations) / len(evaluations)
    hiring_signal = "Yes" if avg_score >= 85 else "Borderline" if avg_score >= 70 else "No"
    
    # Prepare integrity summary for the LLM
    integrity_summary = _aggregate_session_integrity(evaluations)

    inputs = {
        "candidate_name": candidate_name,
        "job_title": job_title,
        "average_score": avg_score,
        "transcript": transcript,
        "integrity_summary": str(integrity_summary),
        "tone_summary": tone_summary,
    }

    try:
        chain = REPORT_SYNTHESIS_PROMPT | llm
        response = chain.invoke(inputs)

        content = _strip_thinking(response.content)

        # Parse JSON from the response
        import json
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group())
        else:
            raw = json.loads(content)

        # Normalize to canonical structure — fills question_scores, communication, and defaults
        return _normalize_report(raw, evaluations, avg_score)

    except Exception as e:
        logger.error("Report synthesis error: %s", e)
        # Build a complete fallback that still satisfies the full required schema
        fallback = {
            "overall_score": avg_score,
            "summary": f"{candidate_name} completed the interview for {job_title} with an average score of {avg_score}/100.",
            "strengths": [],
            "weaknesses": [],
            "improvements": [],
            "tips": [],
            "recommended_topics": [],
        }
        return _normalize_report(fallback, evaluations, avg_score)


# --- Graph Wiring ---
workflow = StateGraph(AgentState)

workflow.add_node("rewrite", rewrite_query_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_context_node)
workflow.add_node("generate", generate_question_node)

workflow.set_entry_point("rewrite")
workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("retrieve", "grade")

def check_grade(state):
    if state["next_action"] == "rewrite_query":
        return "rewrite"
    return "generate"

workflow.add_conditional_edges("grade", check_grade)
workflow.add_node("process_answer", evaluate_answer_node)

def decide_next_step(state: AgentState):
    evaluations = state.get("evaluations", [])
    n = len(evaluations)

    # Hard ceiling
    if n >= MAX_QUESTIONS:
        logger.info("Stopping: max questions reached (%s)", MAX_QUESTIONS)
        return END

    # Topic exhaustion: candidate struggled on 3+ distinct topics
    failed_topics = state.get("failed_topics", [])
    if len(failed_topics) >= 3:
        logger.info("Early stop: candidate struggled on %d topics", len(failed_topics))
        return END

    # Early-stop logic (only after MIN_QUESTIONS answered)
    if n >= MIN_QUESTIONS:
        scores = [e["score"] for e in evaluations]
        recent = scores[-3:]
        avg_recent = sum(recent) / len(recent)

        # Strong performance — stop only after at least 5 answers with high recent average
        if n >= 5 and avg_recent >= 78:
            logger.info("Early stop: strong performance after %d questions (avg recent=%.1f)", n, avg_recent)
            return END

        # Consistently very low — no value in continuing after 5+ questions
        if n >= 5 and len(recent) == 3 and avg_recent < 35:
            logger.info("Early stop: consistently low scores after %d questions (avg recent=%.1f)", n, avg_recent)
            return END

        # Stable signal — score variance is flat, little new information gained
        if n >= 6:
            score_range = max(scores) - min(scores)
            if score_range < 20:
                logger.info("Early stop: stable signal after %d questions (range=%.1f)", n, score_range)
                return END

    # Normal routing
    topic_status = state.get("next_action", "continue")
    if topic_status == "drill_down":
        return "generate"

    return "rewrite"

workflow.add_conditional_edges("process_answer", decide_next_step)

# Task 5.4 — LangGraph in-process checkpointing (per-session thread_id isolation).
# NOTE: MemorySaver is RAM-only — it does NOT survive a server restart. Durable
# session resume across restarts/WebSocket drops comes from Firestore
# (firestore_client.get_session / update_session_state), which the server reloads
# by session_id. For cross-restart graph checkpointing, swap MemorySaver for a
# persistent saver (e.g. langgraph-checkpoint-postgres).
from langgraph.checkpoint.memory import MemorySaver
_checkpointer = MemorySaver()
app_graph = workflow.compile(checkpointer=_checkpointer)
