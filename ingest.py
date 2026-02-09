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
    Saves the structured interview data back into the index for future retrieval.
    Also generates a readable markdown report file automatically.
    Research Ref: Section 7.3 
    """
    index = get_session_index(session_id)
    if not index:
        return

    # Convert the full report list to a JSON string
    text_content = json.dumps(report_data, indent=2)
    
    # Create a document with rich metadata
    report_doc = Document(
        text=f"INTERVIEW REPORT FOR {candidate_name}\nDATE: {datetime.now()}\n\n{text_content}",
        metadata={
            "type": "interview_report",
            "session_id": session_id,
            "candidate_name": candidate_name,
            "date": str(datetime.now().date())
        }
    )
    
    # Insert into the existing index
    index.insert(report_doc)
    
    # Persist changes to disk
    index.storage_context.persist(persist_dir=os.path.join(STORAGE_DIR, session_id))
    
    # === AUTO-GENERATE READABLE MARKDOWN REPORT ===
    # Save reports in a separate folder (not in session folder with JSON)
    reports_dir = os.path.join(os.path.dirname(STORAGE_DIR), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Create readable filename with candidate name and date
    safe_name = candidate_name.replace(" ", "_").replace("/", "-")[:30]
    report_filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join(reports_dir, report_filename)
    
    try:
        md_content = f"# Interview Report for {candidate_name}\n\n"
        md_content += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        md_content += f"**Session ID:** {session_id}\n\n"
        md_content += "---\n\n"
        
        total_score = 0
        tone_counts = {}  # Track tone occurrences
        
        for i, item in enumerate(report_data, 1):
            question = item.get("question", "N/A")
            answer = item.get("answer", "N/A")
            score = item.get("score", 0)
            feedback = item.get("feedback", "N/A")
            tone = item.get("tone", "Neutral")
            total_score += score
            
            # Count tones for summary
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
            
            md_content += f"## Question {i}\n\n"
            md_content += f"**Q:** {question}\n\n"
            md_content += f"**A:** {answer}\n\n"
            md_content += f"**Score:** {score}/100 | **Tone:** {tone}\n\n"
            md_content += f"**Feedback:** {feedback}\n\n"
            md_content += "---\n\n"
        
        # Summary table with scores
        avg_score = total_score / len(report_data) if report_data else 0
        md_content += "## Summary\n\n"
        md_content += "### Scores\n\n"
        md_content += "| Question | Score | Tone |\n"
        md_content += "|----------|-------|------|\n"
        for i, item in enumerate(report_data, 1):
            md_content += f"| Q{i} | {item.get('score', 0)} | {item.get('tone', 'Neutral')} |\n"
        md_content += f"| **Average** | **{avg_score:.1f}** | - |\n\n"
        
        # Tone Analysis Summary
        md_content += "### Voice Tone Analysis\n\n"
        if tone_counts:
            dominant_tone = max(tone_counts, key=tone_counts.get)
            md_content += f"**Dominant Emotion:** {dominant_tone}\n\n"
            md_content += "**Tone Distribution:**\n"
            for tone, count in sorted(tone_counts.items(), key=lambda x: -x[1]):
                percentage = (count / len(report_data)) * 100
                md_content += f"- {tone}: {count} questions ({percentage:.0f}%)\n"
        else:
            md_content += "No tone data available.\n"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"📄 Markdown report saved: {report_path}")
    except Exception as e:
        print(f"Warning: Could not generate markdown report: {e}")
    
    print(f"✅ Interview Report saved for session {session_id}")


def get_candidate_history(candidate_name: str) -> str:
    """
    Queries vector DB for past interview reports for this candidate.
    Research Ref: Section 7.3 - Longitudinal Memory
    
    Args:
        candidate_name: Name of the candidate to search for.
        
    Returns:
        str: Summary of past weak points, or empty string if no history.
    """
    # Search all session directories for matching candidate reports
    if not os.path.exists(STORAGE_DIR):
        return ""
    
    past_reports = []
    
    for session_dir in os.listdir(STORAGE_DIR):
        session_path = os.path.join(STORAGE_DIR, session_dir)
        if not os.path.isdir(session_path):
            continue
            
        try:
            index = get_session_index(session_dir)
            if not index:
                continue
                
            # Query for interview reports matching candidate name
            retriever = index.as_retriever(similarity_top_k=3)
            nodes = retriever.retrieve(f"interview report {candidate_name}")
            
            for node in nodes:
                metadata = node.node.metadata
                if (metadata.get("type") == "interview_report" and 
                    metadata.get("candidate_name", "").lower() == candidate_name.lower()):
                    past_reports.append({
                        "date": metadata.get("date", "Unknown"),
                        "content": node.node.text[:500]  # Truncate for context
                    })
        except Exception as e:
            print(f"Warning: Could not read session {session_dir}: {e}")
            continue
    
    if not past_reports:
        return ""
    
    # Format summary of past performance
    summary = f"PAST INTERVIEW HISTORY FOR {candidate_name}:\n"
    for idx, report in enumerate(past_reports[:3], 1):  # Limit to 3 most recent
        summary += f"\n--- Report {idx} (Date: {report['date']}) ---\n"
        summary += report['content'] + "\n"
    
    return summary