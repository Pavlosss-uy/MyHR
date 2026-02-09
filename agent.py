import os
from typing import TypedDict, List, Literal, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from prompts import FINAL_REPORT_PROMPT
from config import llm

# Import your custom modules
from ingest import get_session_retriever
from retriever import retrieve_context
from prompts import (
    COT_QUESTION_PROMPT, 
    RUBRIC_PROMPT, 
    REWRITE_QUERY_PROMPT, 
    GRADE_CONTEXT_PROMPT,
    DRILL_DOWN_PROMPT  # <--- Ensure this is imported
)

# --- State Definitions (Unchanged) ---
class EvaluationResult(BaseModel):
    score: int = Field(description="Score between 0-100")
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
    last_question: str
    last_answer: str
    multimodal_analysis: dict
    evaluations: List[dict]
    next_action: str

# --- LLM CONFIGURATION ---
# llm = ChatOpenAI(
#     model="llama-3.3-70b-versatile", 
#     openai_api_key=os.getenv("GROQ_API_KEY"),
#     openai_api_base="https://api.groq.com/openai/v1",
#     temperature=0.3
# )

# --- Nodes ---

def rewrite_query_node(state: AgentState):
    """Transforms user intent into a specific search query."""
    history = state.get("conversation_history", [])
    last_answer = state.get("last_answer", "")
    
    chain = REWRITE_QUERY_PROMPT | llm
    response = chain.invoke({"history": str(history[-3:]), "last_answer": last_answer})
    
    print(f"Rewrote Query: {response.content}")
    return {"current_search_query": response.content, "loop_count": state.get("loop_count", 0)}

def retrieve_node(state: AgentState):
    """Uses the Advanced Hybrid Retriever."""
    session_id = state["session_id"]
    query = state.get("current_search_query", state["current_topic"])
    
    try:
        context = retrieve_context(session_id, query) 
    except Exception as e:
        print(f"Retrieval Error: {e}")
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
    """Generates the question using Chain of Thought OR Drill Down."""
    
    # CASE 1: DRILL DOWN (Humanized)
    if state.get("next_action") == "drill_down":
        print("Mode: Generating Humanized Follow-Up")
        chain = DRILL_DOWN_PROMPT | llm
        
        # Softened guidance
        guidance = "The candidate's last answer was vague or they didn't know. Be supportive. If they are stuck, pivot gently."
        
        response = chain.invoke({
            "history": state["conversation_history"],
            "guidance": guidance
        })
        
        return {"last_question": response.content, "loop_count": 0}

    # CASE 2: STANDARD QUESTION (Humanized CoT)
    else:
        chain = COT_QUESTION_PROMPT | llm
        
        # Softened guidance
        guidance = "Ask a natural, friendly interview question."
        if state.get("next_action") == "switch":
            guidance = "Smoothly transition to a new topic from the Job Description. Use a bridge phrase."
        
        job_context = state.get("initial_job_context", {})
        global_context = f"Job Title: {job_context.get('job_title', 'N/A')}\nJob Description Summary: {job_context.get('jd_text', 'N/A')[:500]}...\nCandidate: {job_context.get('candidate_name', 'Candidate')}"
        
        response = chain.invoke({
            "global_context": global_context,
            "context": state["retrieved_context"],
            "history": state["conversation_history"],
            "topic": state["current_topic"],
            "guidance": guidance
        })
        
        content = response.content.split("</thinking>")[-1].strip()
        return {"last_question": content, "loop_count": 0}

def evaluate_answer_node(state: AgentState):
    """Evaluates answer using the Rubric."""
    structured_llm = llm.with_structured_output(EvaluationResult, method="json_mode")
    chain = RUBRIC_PROMPT | structured_llm
    
    # Get tone analysis data
    tone_data = state.get("multimodal_analysis", {})
    
    res = chain.invoke({
        "question": state["last_question"],
        "answer": state["last_answer"],
        "tone_data": str(tone_data)
    })
    
    # Include tone data in report entry
    report_entry = {
        "question": state["last_question"],
        "answer": state["last_answer"],
        "score": res.score,
        "feedback": res.feedback,
        "tone": tone_data.get("primary_emotion", "Neutral")  # Add tone per question
    }
    
    return {
        "evaluations": state.get("evaluations", []) + [report_entry],
        "next_action": res.topic_status
    }



def generate_final_markdown_report(candidate_name, job_desc, evaluations, tone_summary):
    """
    Compiles all interview data and asks the LLM to write the structured Markdown report.
    """
    
    # 1. Format the interview history for the LLM
    interview_text = ""
    total_score = 0
    for i, turn in enumerate(evaluations, 1):
        interview_text += f"\n### Question {i}\n"
        interview_text += f"Q: {turn['question']}\n"
        interview_text += f"A: {turn['answer']}\n"
        interview_text += f"Rubric Score: {turn['score']}/10\n"
        interview_text += f"Rubric Feedback: {turn['feedback']}\n"
        total_score += turn.get('score', 0)

    # 2. Prepare Tone Context
    tone_context = f"Primary Emotion: {tone_summary.get('primary_emotion', 'Neutral')}\n"
    tone_context += f"Detailed Analysis: {tone_summary.get('full_analysis', 'Audio analysis indicates stable speech patterns.')}"

    # 3. Invoke the LLM
    chain = FINAL_REPORT_PROMPT | llm
    
    response = chain.invoke({
        "candidate_name": candidate_name,
        "job_description": job_desc[:500] + "...", # Truncate to save tokens
        "interview_data": interview_text,
        "tone_analysis": tone_context
    })
    
    return response.content

# --- Graph Wiring ---
workflow = StateGraph(AgentState)

workflow.add_node("rewrite", rewrite_query_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_context_node)
workflow.add_node("generate", generate_question_node)
workflow.add_node("evaluate", evaluate_answer_node)

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
    """Decides whether to switch topic (rewrite) or drill down (generate)."""
    if len(state.get("evaluations", [])) >= 5:
        return END
    
    # FIX 2B: Proper topic status handling
    topic_status = state.get("next_action", "continue")
    
    if topic_status == "switch":
        return "rewrite"  # Go get new context for new topic
    elif topic_status == "drill_down":
        return "generate"  # Stay on topic, skip retrieval
    
    return "rewrite"  # Default: continue with new context

workflow.add_conditional_edges("process_answer", decide_next_step)
app_graph = workflow.compile()