import os
from typing import TypedDict, List, Literal, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
import torch
from models.scoring_model import scorer
from models.registry import registry
from models.feature_extractor import extractor

# Import your custom modules
from retriever import retrieve_context
from prompts import (
    COT_QUESTION_PROMPT, 
    RUBRIC_PROMPT, 
    REWRITE_QUERY_PROMPT, 
    GRADE_CONTEXT_PROMPT,
    DRILL_DOWN_PROMPT  
)

# --- State Definitions (Unchanged) ---
class EvaluationResult(BaseModel):
    # We removed 'score: int' from here!
    feedback: str = Field(description="One sentence feedback")
    topic_status: Literal["continue", "switch", "drill_down"] = Field(description="Next move")

class GradeResult(BaseModel):
    is_relevant: bool = Field(description="Is the context useful?")

class AgentState(TypedDict):
    session_id: str
    conversation_history: List[str]
    current_topic: str
    initial_job_context: Dict
    current_search_query: str
    retrieved_context: str
    loop_count: int
    drill_down_count: int
    last_question: str
    last_answer: str
    multimodal_analysis: dict
    evaluations: List[dict]
    next_action: str


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
    return {"current_search_query": response.content, "loop_count": state.get("loop_count", 0)}

def retrieve_node(state: AgentState):
    """Uses the Advanced Hybrid Retriever."""
    session_id = state["session_id"]
    query = state.get("current_search_query", state["current_topic"])
    
    try:
        context = retrieve_context(session_id, query) 
    except Exception as e:
        print(f"⚠️ Retrieval Error: {e}")
        context = "No specific context found."
        
    return {"retrieved_context": context}

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
    
    # --- MOD-7: Adaptive Difficulty Integration ---
    diff_engine = registry.load_difficulty_engine()
    
    # Extract score history (just the 'overall' numbers)
    score_history = [e['score'] for e in state.get("evaluations", [])]
    current_diff = state.get("current_difficulty", 3)
    
    # Get the next optimal difficulty level (1-5)
    next_diff, _diff_probs = diff_engine.decide_next_difficulty(score_history, current_diff)

    # Inject difficulty into guidance
    difficulty_guidance = f" Set question difficulty to Level {next_diff}/5."
    
    # CASE 1: DRILL DOWN (Humanized)
    if state.get("next_action") == "drill_down":
        print(f"⚡ Mode: Generating Follow-Up (Diff: {next_diff})")
        chain = DRILL_DOWN_PROMPT | llm
        guidance = "The candidate's last answer was vague. Be supportive." + difficulty_guidance
        
        response = chain.invoke({
            "history": state["conversation_history"],
            "guidance": guidance
        })
        return {"last_question": response.content, "loop_count": 0, "current_difficulty": next_diff}

    # CASE 2: STANDARD QUESTION (Humanized CoT)
    else:
        chain = COT_QUESTION_PROMPT | llm
        guidance = "Ask a natural interview question." + difficulty_guidance
        if state.get("next_action") == "switch":
            guidance = "Transition to a new topic." + difficulty_guidance
        
        job_context = state.get("initial_job_context", {})
        global_context = f"Job Title: {job_context.get('job_title', 'N/A')}\nCandidate: {job_context.get('candidate_name', 'Candidate')}"
        
        response = chain.invoke({
            "global_context": global_context,
            "context": state["retrieved_context"],
            "history": state["conversation_history"],
            "topic": state["current_topic"],
            "guidance": guidance
        })
        
        content = response.content.split("</thinking>")[-1].strip()
        return {"last_question": content, "loop_count": 0, "current_difficulty": next_diff}

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

    # 3. 🧠 Neural Evaluation (MOD-4)
    # Returns: {'relevance': x, 'clarity': y, 'technical_depth': z, 'overall': total}
    neural_results = evaluator.evaluate_answer(features)
    
    # 4. 📈 Performance Prediction (MOD-6)
    # Returns a 1.0 - 10.0 forecast
    job_prediction = predictor.predict_performance(features)

    # 5. LLM generates feedback text
    structured_llm = llm.with_structured_output(EvaluationResult, method="json_mode")
    chain = RUBRIC_PROMPT | structured_llm

    res = chain.invoke({
        "question": state["last_question"],
        "answer": state["last_answer"],
        "tone_data": str(tone_data)
    })

    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": neural_results["overall"], 
        "detailed_scores": neural_results,
        "predicted_job_performance": job_prediction,
        "feedback": res.feedback
    }

    print(f"📊 Multi-Head Neural Score: {neural_results['overall']}/100")
    print(f"🔮 Predicted Job Performance: {job_prediction}/10.0")

    return {
        "evaluations": state.get("evaluations", []) + [report_entry],
        "next_action": res.topic_status,
        "predicted_performance": job_prediction # Store for final report
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

def decide_next_step(state):
    if len(state.get("evaluations", [])) >= 5:
        return END
    
    evaluations = state.get("evaluations", [])
    if evaluations:
        last_eval = evaluations[-1]
        topic_status = state.get("next_action", "continue")
        
        if topic_status == "drill_down":
            return "generate"
    
    return "rewrite"

workflow.add_conditional_edges("process_answer", decide_next_step)
app_graph = workflow.compile()