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