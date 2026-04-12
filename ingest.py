import os
import json
from datetime import datetime

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Document,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pinecone import Pinecone, ServerlessSpec

# Tell LlamaIndex to use a local HuggingFace embedding model instead of OpenAI
Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-mpnet-base-v2"
)

# ---------- Local storage for BM25 raw texts ----------
BM25_STORE_DIR = "storage/bm25"
os.makedirs(BM25_STORE_DIR, exist_ok=True)

# ---------- Initialize Pinecone ----------
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "myhr-interviews"

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=768,  # matches all-mpnet-base-v2
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

pinecone_index = pc.Index(index_name)


def _chunk_documents(documents: list[Document]):
    """
    Splits documents into smaller chunks so both Pinecone and BM25
    operate on meaningful retrieval units instead of one giant CV / JD blob.
    """
    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    return nodes


def _bm25_store_path(session_id: str) -> str:
    return os.path.join(BM25_STORE_DIR, f"{session_id}.json")


def save_session_raw_texts(session_id: str, chunks: list[str]):
    """
    Persist chunk texts locally so BM25 can load them later.
    """
    path = _bm25_store_path(session_id)
    payload = {
        "session_id": session_id,
        "chunks": chunks,
        "saved_at": datetime.now().isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_session_raw_texts(session_id: str) -> list[str]:
    """
    Load BM25 chunk texts for a session.
    """
    path = _bm25_store_path(session_id)
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("chunks", [])
    except Exception as e:
        print(f"⚠️ Failed to load BM25 texts for session {session_id}: {e}")
        return []


def create_session_index(
    session_id: str,
    cv_text: str,
    jd_text: str,
    candidate_name: str = "Candidate",
    role: str = "",
):
    """
    Creates chunked embeddings and pushes them to Pinecone with namespace=session_id.
    Also stores raw chunk texts locally for BM25 indexing.
    Header injection: candidate name and role are prepended to every CV chunk so
    the retriever always returns contextually grounded passages.
    """
    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index,
        namespace=session_id
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    documents = [
        Document(text=cv_text, metadata={"type": "cv"}),
        Document(text=jd_text, metadata={"type": "jd"}),
    ]

    # Chunk documents first
    nodes = _chunk_documents(documents)

    # Header injection: prepend candidate metadata to every CV chunk
    cv_header = f"Candidate: {candidate_name}"
    if role:
        cv_header += f" | Role: {role}"
    cv_header += " | "

    for node in nodes:
        if node.metadata.get("type") == "cv":
            node.text = cv_header + node.text

    # Save raw chunk texts for BM25
    raw_chunks = [node.text for node in nodes if node.text and node.text.strip()]
    save_session_raw_texts(session_id, raw_chunks)

    # Build Pinecone vector index using the same chunks
    index = VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
    )
    return index


def get_session_index(session_id: str):
    """
    Loads the Pinecone-backed vector index for retriever.py using the namespace.
    """
    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index,
        namespace=session_id
    )
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


def save_rich_report(session_id: str, rich_report: dict) -> str:
    """
    Persist the synthesized rich report (JSON) to storage.
    This is the authoritative final report — same content shown to the user and stored.
    """
    report_dir = "storage/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{session_id}_rich_report.json")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(rich_report, f, ensure_ascii=False, indent=2)

    print(f"📊 Rich report saved: {report_path}")
    return report_path


def save_interview_report(session_id: str, candidate_name: str, evaluations: list):
    """
    Generates a Markdown interview report from the evaluation data.
    Called when the interview reaches completion.
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
            lines.append("| Metric | Score |")
            lines.append("|--------|-------|")
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

    avg_score = sum(overall_scores) / max(len(overall_scores), 1)
    lines.insert(7, f"**Average Score**: {avg_score:.1f}/100")
    lines.insert(8, "")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"📄 Interview report saved: {report_path}")
    return report_path