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
import numpy as np

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

    print(f"Rewrote Query: {response.content}")
    return {"current_search_query": response.content.strip(), "loop_count": state.get("loop_count", 0)}

def retrieve_node(state: AgentState):
    """Uses the Advanced Hybrid Retriever. Populates both unified and split context."""
    session_id = state["session_id"]
    query = state.get("current_search_query", state["current_topic"])

    try:
        cv_chunk, jd_chunk = retrieve_context_split(session_id, query)
        context = f"{cv_chunk}\n\n{jd_chunk}".strip()
    except Exception as e:
        print(f"Retrieval Error: {e}")
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

    # --- Adaptive Difficulty Integration (REINFORCE — PPO skipped, not installed) ---
    diff_engine = registry.load_difficulty_engine()

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
        print(f"Mode: FIRST_QUESTION (Diff: {next_diff})")
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
            print(f"  First-question attempt {attempt + 1} rejected: {content[:60]}...")
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
        print(f"Mode: FALLBACK (Diff: {next_diff})")
        chain = DRILL_DOWN_PROMPT | llm
        guidance = "The candidate struggled with the last question. Ask a concretely simpler version." + difficulty_guidance

        max_attempts = 3
        content = ""
        for attempt in range(max_attempts):
            response = chain.invoke({
                "history": state.get("conversation_history", []),
                "guidance": guidance,
                "asked_questions": "\n".join(f"- {q}" for q in asked_questions) or "None yet.",
            })
            content = _strip_thinking(response.content)

            # Ensure the required prefix is present
            if not content.startswith("No problem"):
                content = "No problem, let's try a simpler one. " + content.lstrip()

            if _is_valid_question(content):
                break
            print(f"  Fallback attempt {attempt + 1} rejected: {content[:60]}...")

        return {
            "last_question": content,
            "loop_count": 0,
            "current_difficulty": max(1, next_diff - 1),  # fallback = easier
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
            "interview_mode": "normal",  # return to normal after fallback
        }

    # ── MODE: normal (CoT) ───────────────────────────────────────────────────
    print(f"Mode: NORMAL (Diff: {next_diff})")
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
        print(f"  Normal attempt {attempt + 1} rejected: {content[:60]}...")
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
    predictor = registry.load_performance_predictor()

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

    # 3. Neural Evaluation (MOD-4)
    neural_results = evaluator.evaluate_answer(features)

    # 4. Performance Prediction (MOD-6)
    job_prediction = predictor.predict_performance(features)

    # 5. Explainability (SHAP)
    feature_names = [
        "skill_match", "relevance", "clarity", "depth",
        "confidence", "consistency", "gaps_inverted", "experience"
    ]

    shap_values_list = []
    feature_values_list = features.detach().cpu().numpy().flatten().tolist()
    shap_summary = {}
    expected_value = None

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
        print(f"SHAP Error: {e}")

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

    # Detect flat / undertrained neural model — use wide threshold (±15 of center)
    neural_is_flat = abs(neural_score - 50.0) < 15.0
    score_divergence = abs(llm_score - neural_score)

    if neural_is_flat:
        # Neural model outputting near-constant values — trust LLM almost exclusively
        blended_score = round(0.93 * llm_score + 0.07 * neural_score, 1)
        print(f"Neural flat ({neural_score:.1f}) — LLM-dominant blend (93/7)")
    elif score_divergence > 20:
        # Significant disagreement — LLM is calibrated, neural is likely undertrained
        blended_score = round(0.88 * llm_score + 0.12 * neural_score, 1)
        print(f"Score divergence {score_divergence:.1f} — LLM-weighted blend (88/12)")
    else:
        blended_score = round(0.80 * llm_score + 0.20 * neural_score, 1)

    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": blended_score,
        "llm_score": llm_score,
        "neural_score": neural_score,
        "answer_classification": res.answer_classification,
        "detailed_scores": neural_results,
        "predicted_job_performance": job_prediction,
        "feedback": res.feedback,
        "suggested_improvement": res.suggested_improvement,
        "criteria_breakdown": res.criteria_breakdown.model_dump(),
        "overall_confidence": res.overall_confidence,
        "tone_data": tone_data,
        "feature_values": feature_values_list,
        "shap_values": shap_values_list,
        "feature_importance": shap_summary,
        "shap_expected_value": float(np.ravel(expected_value)[0]) if expected_value is not None else None
    }

    print(f"LLM Score: {llm_score}/100 | Neural Score: {neural_score}/100 | Blended: {blended_score}/100")
    print(f"Predicted Job Performance: {job_prediction}/10.0")

    return {
        "evaluations": state.get("evaluations", []) + [report_entry],
        "next_action": res.topic_status,
        "predicted_performance": job_prediction
    }


def _build_question_scores(evaluations: list) -> list:
    """Build the question_scores list from raw evaluation entries."""
    result = []
    for i, e in enumerate(evaluations, 1):
        result.append({
            "index": i,
            "question": e.get("question", ""),
            "answer": e.get("answer", ""),
            "score": e.get("score", 0),
            "classification": e.get("answer_classification", ""),
            "feedback": e.get("feedback", ""),
            "suggested_improvement": e.get("suggested_improvement", ""),
            "criteria_breakdown": e.get("criteria_breakdown", {}),
        })
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

    # Ensure list fields contain only strings (LLM may return dicts)
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

    for _field in ("strengths", "weaknesses", "areas_to_improve", "improvements", "how_to_improve", "tips", "recommended_topics"):
        raw[_field] = _to_str_list(raw.get(_field, []))
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
    if existing_signal in legacy_map:
        raw["hiring_signal"] = legacy_map[existing_signal]
    elif existing_signal not in ("Yes", "Borderline", "No"):
        # Generate from score if missing or unrecognised
        raw["hiring_signal"] = (
            "Yes"       if avg_score >= 85 else
            "Borderline" if avg_score >= 70 else
            "No"
        )

    # Ensure tone_analysis always present (alias may have been set above; fill defaults if not)
    raw.setdefault("tone_analysis", raw.get("communication_analysis", {}))

    return raw


def synthesize_report(session_state: dict, candidate_name: str, job_title: str) -> dict:
    """
    Generate the single authoritative report for an interview session.
    The returned dict is the exact object that is:
      - returned to the API caller
      - saved to storage via save_rich_report
      - served on any later retrieval
    No further transformation or re-generation occurs after this call.
    """
    evaluations = session_state.get("evaluations", [])
    if not evaluations:
        return {}

    avg_score = round(sum(e["score"] for e in evaluations) / len(evaluations), 1)

    # Build a readable transcript including classification for the prompt
    transcript_lines = []
    for i, e in enumerate(evaluations, 1):
        classification = e.get("answer_classification", "")
        classification_str = f" [{classification}]" if classification else ""
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

    try:
        chain = REPORT_SYNTHESIS_PROMPT | llm
        response = chain.invoke({
            "candidate_name": candidate_name,
            "job_title": job_title,
            "average_score": avg_score,
            "transcript": transcript,
            "tone_summary": tone_summary,
        })

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
        print(f"Report synthesis error: {e}")
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
        print(f"Stopping: max questions reached ({MAX_QUESTIONS})")
        return END

    # Topic exhaustion: candidate struggled on 3+ distinct topics
    failed_topics = state.get("failed_topics", [])
    if len(failed_topics) >= 3:
        print(f"Early stop: candidate struggled on {len(failed_topics)} topics")
        return END

    # Early-stop logic (only after MIN_QUESTIONS answered)
    if n >= MIN_QUESTIONS:
        scores = [e["score"] for e in evaluations]
        recent = scores[-3:]
        avg_recent = sum(recent) / len(recent)

        # Strong performance — stop only after at least 5 answers with high recent average
        if n >= 5 and avg_recent >= 78:
            print(f"Early stop: strong performance after {n} questions (avg recent={avg_recent:.1f})")
            return END

        # Consistently very low — no value in continuing after 5+ questions
        if n >= 5 and len(recent) == 3 and avg_recent < 35:
            print(f"Early stop: consistently low scores after {n} questions (avg recent={avg_recent:.1f})")
            return END

        # Stable signal — score variance is flat, little new information gained
        if n >= 6:
            score_range = max(scores) - min(scores)
            if score_range < 20:
                print(f"Early stop: stable signal after {n} questions (range={score_range:.1f})")
                return END

    # Normal routing
    topic_status = state.get("next_action", "continue")
    if topic_status == "drill_down":
        return "generate"

    return "rewrite"

workflow.add_conditional_edges("process_answer", decide_next_step)
app_graph = workflow.compile()
