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
    print(f"✅ Interview Report saved for session {session_id}")