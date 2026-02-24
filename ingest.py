import os
import shutil
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import StorageContext, load_index_from_storage
from config import STORAGE_DIR
from llama_index.core import Document
import json
from datetime import datetime

# Initialize Global Models (Run once)
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-mpnet-base-v2")
Settings.text_splitter = SentenceSplitter(chunk_size=500, chunk_overlap=50)

def get_session_index(session_id: str):
    """
    Loads the raw Index object for advanced retrieval pipelines.
    Required by retriever.py for Hybrid Search.
    """
    session_dir = os.path.join(STORAGE_DIR, session_id)
    if not os.path.exists(session_dir):
        return None
        
    storage_context = StorageContext.from_defaults(persist_dir=session_dir)
    return load_index_from_storage(storage_context)

def create_session_index(session_id: str, cv_path: str, jd_text: str):
    """
    Creates a dedicated vector index for a specific session.
    """
    session_dir = os.path.join(STORAGE_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # 1. Save JD as a text file to be indexed alongside CV
    jd_path = os.path.join(session_dir, "job_description.txt")
    with open(jd_path, "w") as f:
        f.write(jd_text)

    # 2. Load Documents (CV + JD)
    # We copy CV to session dir to keep things clean
    local_cv_path = os.path.join(session_dir, "candidate_cv.pdf")
    shutil.copy(cv_path, local_cv_path)
    
    documents = SimpleDirectoryReader(session_dir).load_data()

    # 3. Build & Persist Index
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=session_dir)
    
    return index

def get_session_retriever(session_id: str):
    """
    Loads the specific index for a session.
    """
    from llama_index.core import StorageContext, load_index_from_storage
    session_dir = os.path.join(STORAGE_DIR, session_id)
    
    if not os.path.exists(session_dir):
        return None
        
    storage_context = StorageContext.from_defaults(persist_dir=session_dir)
    index = load_index_from_storage(storage_context)
    return index.as_retriever(similarity_top_k=3)

def save_interview_report(session_id: str, candidate_name: str, report_data: list):
    """
    Saves the structured interview data back into the index for future retrieval,
    AND saves a readable Markdown report file to the reports/ folder.
    """
    # --- 1. Save to Vector Index (existing behavior) ---
    index = get_session_index(session_id)
    if index:
        text_content = json.dumps(report_data, indent=2)
        report_doc = Document(
            text=f"INTERVIEW REPORT FOR {candidate_name}\nDATE: {datetime.now()}\n\n{text_content}",
            metadata={
                "type": "interview_report",
                "session_id": session_id,
                "candidate_name": candidate_name,
                "date": str(datetime.now().date())
            }
        )
        index.insert(report_doc)
        index.storage_context.persist(persist_dir=os.path.join(STORAGE_DIR, session_id))
    
    # --- 2. Save readable Markdown report file ---
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_name = candidate_name.replace(' ', '_')
    filename = f"{safe_name}_{date_str}.md"
    filepath = os.path.join(reports_dir, filename)
    
    # Calculate stats
    scores = [e.get("score", 0) for e in report_data]
    avg_score = sum(scores) / len(scores) if scores else 0
    tones = [e.get("tone", "N/A") for e in report_data]
    
    # Determine recommendation
    if avg_score >= 75:
        recommendation = "✅ STRONG HIRE"
        rec_summary = "The candidate demonstrated strong technical competency and clear communication throughout the interview."
    elif avg_score >= 55:
        recommendation = "⚠️ CONDITIONAL HIRE"
        rec_summary = "The candidate showed promise in several areas but needs improvement in others. Consider with additional evaluation or onboarding support."
    else:
        recommendation = "❌ NO HIRE"
        rec_summary = "The candidate did not meet the minimum requirements for this role based on the interview performance."
    
    # Build Markdown content
    md = f"# 📋 Interview Report: {candidate_name}\n\n"
    md += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    md += f"**Average Score:** {avg_score:.1f}/100\n\n"
    md += "---\n\n"
    
    # Executive Summary
    md += "## 📝 Executive Summary\n\n"
    md += f"**Recommendation:** {recommendation}\n\n"
    md += f"{rec_summary}\n\n"
    md += "---\n\n"
    
    # Detailed Q&A with Tone
    md += "## 🎯 Detailed Interview Analysis\n\n"
    for i, entry in enumerate(report_data, 1):
        score = entry.get("score", "N/A")
        tone = entry.get("tone", "N/A")
        tone_details = entry.get("tone_details", {})
        
        # Score emoji
        if isinstance(score, (int, float)):
            score_emoji = "🟢" if score >= 70 else "🟡" if score >= 40 else "🔴"
        else:
            score_emoji = "⚪"
        
        md += f"### Question {i} {score_emoji}\n\n"
        md += f"**Q:** {entry.get('question', 'N/A')}\n\n"
        md += f"**A:** {entry.get('answer', 'N/A')}\n\n"
        md += f"**Score:** {score}/100 | **Tone:** {tone}\n\n"
        md += f"**Feedback:** {entry.get('feedback', 'N/A')}\n\n"
        
        # Tone details if available
        if tone_details and isinstance(tone_details, dict):
            md += "**Tone Breakdown:** "
            tone_parts = [f"{k}: {v}" for k, v in tone_details.items()]
            md += " | ".join(tone_parts) + "\n\n"
        
        md += "---\n\n"
    
    # Tone Analysis Summary
    md += "## 🎭 Behavioral & Communication Insights\n\n"
    tone_counts = {}
    for t in tones:
        tone_counts[t] = tone_counts.get(t, 0) + 1
    dominant_tone = max(tone_counts, key=tone_counts.get) if tone_counts else "N/A"
    
    md += f"**Dominant Tone Across Interview:** {dominant_tone}\n\n"
    md += "**Tone Distribution:**\n\n"
    md += "| Tone | Occurrences |\n"
    md += "|------|-------------|\n"
    for tone, count in sorted(tone_counts.items(), key=lambda x: -x[1]):
        md += f"| {tone} | {count}/{len(tones)} questions |\n"
    md += "\n---\n\n"
    
    # Scoring Table
    md += "## 📊 Scoring Breakdown\n\n"
    md += "| # | Topic | Score | Tone |\n"
    md += "|---|-------|-------|------|\n"
    for i, entry in enumerate(report_data, 1):
        q_short = entry.get("question", "N/A")[:60] + "..." if len(entry.get("question", "")) > 60 else entry.get("question", "N/A")
        md += f"| {i} | {q_short} | {entry.get('score', 'N/A')}/100 | {entry.get('tone', 'N/A')} |\n"
    md += f"\n**Average:** {avg_score:.1f}/100\n"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"✅ Interview Report saved: {filepath}")