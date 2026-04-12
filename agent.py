import os
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
    COT_QUESTION_PROMPT, 
    RUBRIC_PROMPT, 
    REWRITE_QUERY_PROMPT, 
    GRADE_CONTEXT_PROMPT,
    DRILL_DOWN_PROMPT  
)

# --- State Definitions ---
class CriteriaBreakdown(BaseModel):
    relevance: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    technical_depth: int = Field(ge=0, le=100)
    star_method: int = Field(ge=0, le=100)

class EvaluationResult(BaseModel):
    score: int = Field(description="Score 0-100 reflecting overall answer quality. Be strict: off-topic or irrelevant answers should score below 40, mediocre answers 40-65, good answers 65-80, excellent answers 80-100.", ge=0, le=100)
    feedback: str = Field(description="One sentence feedback")
    topic_status: Literal["continue", "switch", "drill_down"] = Field(description="Next move")
    suggested_improvement: str = Field(description="One concrete, actionable suggestion for the candidate to improve their answer")
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


# --- Interview bounds (shared with decide_next_step and generate_question_node) ---
MIN_QUESTIONS = 3
MAX_QUESTIONS = 8

def _strip_thinking(content: str) -> str:
    if not content:
        return ""
    return content.split("</thinking>")[-1].strip()


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
    
    print(f"🔄 Rewrote Query: {response.content}")
    return {"current_search_query": response.content.strip(), "loop_count": state.get("loop_count", 0)}

def retrieve_node(state: AgentState):
    """Uses the Advanced Hybrid Retriever. Populates both unified and split context."""
    session_id = state["session_id"]
    query = state.get("current_search_query", state["current_topic"])

    try:
        cv_chunk, jd_chunk = retrieve_context_split(session_id, query)
        context = f"{cv_chunk}\n\n{jd_chunk}".strip()
    except Exception as e:
        print(f"⚠️ Retrieval Error: {e}")
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
    """Generates the question using Adaptive Difficulty + CoT/Drill Down."""
    
    # --- MOD-7: Adaptive Difficulty Integration (PPO default) ---
    diff_engine = registry.load_difficulty_engine()

    # Extract score history
    score_history = [e['score'] for e in state.get("evaluations", [])]
    current_diff  = state.get("current_difficulty", 3)
    n_questions   = len(score_history)

    # Build 6-D observation for PPO (mirrors InterviewEnv._get_obs())
    avg_score_norm = (sum(score_history) / len(score_history) / 100.0) if score_history else 0.5
    if len(score_history) >= 2:
        trend = float(np.clip(((score_history[-1] - score_history[-2]) / 100.0 + 1.0) / 2.0, 0.0, 1.0))
    else:
        trend = 0.5
    current_diff_norm        = current_diff / 5.0
    engagement               = 0.8  # default; not tracked in agent state
    topic_diversity          = min(1.0, n_questions / MAX_QUESTIONS)
    questions_remaining_norm = max(0.0, 1.0 - n_questions / MAX_QUESTIONS)
    obs = np.array([avg_score_norm, trend, current_diff_norm, engagement,
                    topic_diversity, questions_remaining_norm], dtype=np.float32)

    # PPO returns (action, _state); REINFORCE fallback uses decide_next_difficulty
    try:
        action, _ = diff_engine.predict(obs, deterministic=True)
        next_diff = int(action) + 1  # 0-4 → 1-5
    except AttributeError:
        # Fallback: REINFORCE AdaptiveDifficultyEngine
        diff_result = diff_engine.decide_next_difficulty(score_history, current_diff)
        next_diff = diff_result[0] if isinstance(diff_result, tuple) else diff_result

    # Inject difficulty into guidance
    difficulty_guidance = f" Set question difficulty to Level {next_diff}/5."
    
    asked_questions = state.get("asked_questions", [])
    failed_topics   = state.get("failed_topics", [])

    # CASE 1: DRILL DOWN
    if state.get("next_action") == "drill_down":
        print(f"⚡ Mode: Generating Follow-Up (Diff: {next_diff})")
        chain = DRILL_DOWN_PROMPT | llm
        guidance = "The candidate's last answer was vague. Probe for one concrete detail only." + difficulty_guidance

        response = chain.invoke({
            "history": state.get("conversation_history", []),
            "guidance": guidance,
            "asked_questions": "\n".join(f"- {q}" for q in asked_questions) or "None yet.",
        })
        content = _strip_thinking(response.content)
        return {
            "last_question": content,
            "loop_count": 0,
            "current_difficulty": next_diff,
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
        }

    # CASE 2: STANDARD QUESTION (CoT)
    else:
        chain = COT_QUESTION_PROMPT | llm
        guidance = "Ask a natural interview question." + difficulty_guidance
        if state.get("next_action") == "switch":
            guidance = (
                "Transition to a COMPLETELY different technical topic — "
                "do NOT revisit any failed topics listed below." + difficulty_guidance
            )

        job_context = state.get("initial_job_context", {})
        global_context = (
            f"Job Title: {job_context.get('job_title', 'N/A')}\n"
            f"Candidate: {job_context.get('candidate_name', 'Candidate')}"
        )

        # Derive current_topic dynamically from search query (first 4 words)
        raw_query = state.get("current_search_query", "").strip()
        derived_topic = " ".join(raw_query.split()[:4]).title() if raw_query else state.get("current_topic", "General")

        response = chain.invoke({
            "global_context": global_context,
            "cv_chunk": state.get("cv_chunk", "No CV context found."),
            "jd_chunk": state.get("jd_chunk", "No JD context found."),
            "history": state.get("conversation_history", []),
            "topic": derived_topic,
            "guidance": guidance,
            "asked_questions": "\n".join(f"- {q}" for q in asked_questions) or "None yet.",
            "failed_topics": "\n".join(f"- {t}" for t in failed_topics) or "None.",
        })

        content = _strip_thinking(response.content)
        return {
            "last_question": content,
            "current_topic": derived_topic,
            "loop_count": 0,
            "current_difficulty": next_diff,
            "asked_questions": asked_questions + [content],
            "question_number": state.get("question_number", 1) + 1,
        }

def evaluate_answer_node(state: AgentState):
    """Evaluates answer using Multi-Head Evaluator (MOD-4) + Performance Predictor (MOD-6)."""

    # 1. Load Models from Registry
    evaluator = registry.load_evaluator()
    predictor = registry.load_performance_predictor()

    # 2. Extract the 8 real features for the neural networks
    # [skill_match, relevance, clarity, depth, confidence, consistency, gaps_inverted, experience]
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

    # Make sure features are a torch tensor with shape [1, 8]
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
    feature_values_list = features.detach().cpu().numpy().tolist()
    shap_summary = {}
    expected_value = None

    try:
        explainer = ModelExplainer(predictor, feature_names)

        # Better than a totally random background:
        # small perturbations around the candidate's actual feature vector
        center = features.detach().cpu().numpy()[0]
        noise = np.random.normal(loc=0.0, scale=0.05, size=(20, len(feature_names)))
        background_data = np.clip(center + noise, 0.0, 1.0).astype(np.float32)

        shap_values, expected_value = explainer.explain_prediction(features, background_data)

        shap_values_np = np.asarray(shap_values, dtype=np.float32)
        if shap_values_np.ndim == 1:
            shap_values_np = shap_values_np.reshape(1, -1)

        shap_values_list = shap_values_np.tolist()
        shap_summary = dict(zip(feature_names, shap_values_np[0].tolist()))

        os.makedirs("reports", exist_ok=True)
        explainer.plot_waterfall(
            shap_values=shap_values_np,
            features=features,
            expected_value=expected_value,
            save_path=f"reports/shap_{state['session_id']}.png"
        )

    except Exception as e:
        print(f"⚠️ SHAP Error: {e}")

    # 6. LLM generates feedback text
    # Ensure tone_data is real before calling judge — guard against "Processing..." placeholder
    if not tone_data or tone_data.get("primary_emotion") == "Processing...":
        tone_data = {"primary_emotion": "neutral", "full_analysis": {}, "confidence": 0.5}

    facial_expression_data = state.get("facial_expression_data", {})

    structured_llm = llm.with_structured_output(EvaluationResult, method="json_mode")
    chain = RUBRIC_PROMPT | structured_llm

    res = chain.invoke({
        "question": state["last_question"],
        "answer": state["last_answer"],
        "tone_data": str(tone_data),
        "facial_expression_data": str(facial_expression_data) if facial_expression_data else "Not available",
    })

    # Blend LLM score (primary quality signal) with neural score (structural features)
    llm_score = float(res.score)
    neural_score = float(neural_results["overall"])
    blended_score = round(0.6 * llm_score + 0.4 * neural_score, 1)

    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": blended_score,
        "llm_score": llm_score,
        "neural_score": neural_score,
        "detailed_scores": neural_results,
        "predicted_job_performance": job_prediction,
        "feedback": res.feedback,
        "suggested_improvement": res.suggested_improvement,
        "criteria_breakdown": res.criteria_breakdown.model_dump(),
        "overall_confidence": res.overall_confidence,

        # Step 5.2 fields
        "feature_values": feature_values_list,
        "shap_values": shap_values_list,

        # optional extras
        "feature_importance": shap_summary,
        "shap_expected_value": float(np.ravel(expected_value)[0]) if expected_value is not None else None
    }

    print(f"📊 LLM Score: {llm_score}/100 | Neural Score: {neural_score}/100 | Blended: {blended_score}/100")
    print(f"🔮 Predicted Job Performance: {job_prediction}/10.0")
    print(f"\n📊 DYNAMIC FEATURES EXTRACTED for {state['last_answer'][:20]}...")
    print(features)

    return {
        "evaluations": state.get("evaluations", []) + [report_entry],
        "next_action": res.topic_status,
        "predicted_performance": job_prediction
    }

# --- Graph Wiring ---
workflow = StateGraph(AgentState)

workflow.add_node("rewrite", rewrite_query_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_context_node)
workflow.add_node("generate", generate_question_node)
# Note: evaluation is handled by the "process_answer" node below

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

    # ── Hard ceiling ──────────────────────────────────────────────────────────
    if n >= MAX_QUESTIONS:
        print(f"🛑 Stopping: reached max questions ({MAX_QUESTIONS})")
        return END

    # ── Below minimum: never stop early ──────────────────────────────────────
    if n >= MIN_QUESTIONS:
        scores  = [e["score"] for e in evaluations]
        recent  = scores[-3:]
        avg_recent = sum(recent) / len(recent)

        # Strong performer — enough signal, end with positive note
        if avg_recent >= 80:
            print(f"✅ Early stop: strong performance (avg recent={avg_recent:.1f})")
            return END

        # Clearly disengaged / trolling: 3 consecutive scores below 30
        if len(recent) == 3 and all(s < 30 for s in recent):
            print(f"⚠️ Early stop: consistently low scores (avg recent={avg_recent:.1f})")
            return END

        # Stable signal after 5+ questions: score range < 20 → we've learned enough
        if n >= 5:
            score_range = max(scores) - min(scores)
            if score_range < 20:
                print(f"📊 Early stop: stable signal after {n} questions (range={score_range:.1f})")
                return END

    # ── Normal routing ────────────────────────────────────────────────────────
    topic_status = state.get("next_action", "continue")
    if topic_status == "drill_down":
        return "generate"

    return "rewrite"

workflow.add_conditional_edges("process_answer", decide_next_step)
app_graph = workflow.compile()