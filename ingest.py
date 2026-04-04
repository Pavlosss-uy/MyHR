import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Document, Settings
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pinecone import Pinecone, ServerlessSpec
import json
from datetime import datetime

# Tell LlamaIndex to use the free, local HuggingFace model instead of OpenAI
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-mpnet-base-v2")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "myhr-interviews"

# Create index if it doesn't exist
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=768, # Make sure this matches your HuggingFace model dimension
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

pinecone_index = pc.Index(index_name)

def create_session_index(session_id: str, cv_text: str, jd_text: str):
    """
    Creates embeddings and pushes them to Pinecone with namespace = session_id.
    """
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index, namespace=session_id)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # We pass raw text here instead of saving to disk first (addresses Task 1.3 as well)
    documents = [
        Document(text=cv_text, metadata={"type": "cv"}),
        Document(text=jd_text, metadata={"type": "jd"})
    ]

    index = VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context
    )
    return index

def get_session_index(session_id: str):
    """Loads the index for retriever.py using the namespace."""
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index, namespace=session_id)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


def save_interview_report(session_id: str, candidate_name: str, evaluations: list):
    """
    Generates a Markdown interview report from the evaluation data.
    Called when the interview reaches completion (5 questions answered).
    """
    report_dir = "storage/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{session_id}_report.md")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# Interview Report — {candidate_name}",
        f"**Session ID**: `{session_id}`",
        f"**Date**: {timestamp}",
        f"**Total Questions**: {len(evaluations)}",
        "",
        "---",
        "",
    ]

    overall_scores = []

    for i, ev in enumerate(evaluations, 1):
        score = ev.get("score", 0)
        overall_scores.append(score if isinstance(score, (int, float)) else 0)

        lines.append(f"## Question {i}")
        lines.append(f"**Q**: {ev.get('question', 'N/A')}")
        lines.append(f"**A**: {ev.get('answer', 'N/A')}")
        lines.append("")

        detailed = ev.get("detailed_scores", {})
        if detailed:
            lines.append(f"| Metric | Score |")
            lines.append(f"|--------|-------|")
            for k, v in detailed.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        perf = ev.get("predicted_job_performance", None)
        if perf is not None:
            lines.append(f"**Predicted Job Performance**: {perf}/10.0")

        lines.append(f"**Feedback**: {ev.get('feedback', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Summary
    avg_score = sum(overall_scores) / max(len(overall_scores), 1)
    lines.insert(7, f"**Average Score**: {avg_score:.1f}/100")
    lines.insert(8, "")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"📄 Interview report saved: {report_path}")
    return report_path