import sys

# --- WINDOWS PATCH: Mock the 'resource' module ---
if sys.platform == "win32":
    import types
    resource_mock = types.ModuleType("resource")
    resource_mock.RLIMIT_NOFILE = 7
    def getrlimit(resource): return (4096, 4096)
    def setrlimit(resource, limits): pass
    resource_mock.getrlimit = getrlimit
    resource_mock.setrlimit = setrlimit
    sys.modules["resource"] = resource_mock
# --- END WINDOWS PATCH ---

from llama_index.core import QueryBundle
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from ingest import get_session_index

def get_retriever_pipeline(session_id: str):
    # 1. Load the specific session index
    index = get_session_index(session_id)
    if not index:
        raise ValueError(f"No index found for session {session_id}")
        
    # 2. Create Retrievers
    # Vector Retriever (Dense)
    vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=5)
    
    # BM25 Retriever (Sparse)
    bm25_retriever = BM25Retriever.from_defaults(docstore=index.docstore, similarity_top_k=5)
    
    # 3. Fusion
    # FIX: Use the string "reciprocal_rerank" directly to avoid ImportError on FusionMode
    fusion_retriever = QueryFusionRetriever(
        [vector_retriever, bm25_retriever],
        similarity_top_k=5,
        num_queries=1,
        mode="reciprocal_rerank",  # Correct value is 'reciprocal_rerank', not 'reciprocal_rank'
        use_async=False
    )
    
    return fusion_retriever

def retrieve_context(session_id: str, query: str):
    # Pass session_id to get the correct retriever
    retriever = get_retriever_pipeline(session_id)
    
    # Run Retrieval
    nodes = retriever.retrieve(query)
    
    # 4. Rerank (Cross-Encoder)
    reranker = SentenceTransformerRerank(
        model="cross-encoder/ms-marco-MiniLM-L-12-v2", 
        top_n=3
    )
    
    reranked_nodes = reranker.postprocess_nodes(
        nodes, 
        query_bundle=QueryBundle(query)
    )
    
    # Format Output
    results = []
    for node in reranked_nodes:
        results.append(f"[Score: {node.score:.4f}] {node.text}")
        
    return "\n\n".join(results)