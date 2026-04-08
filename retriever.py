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
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from ingest import get_session_index

# 👇 CACHE THE MODEL IN MEMORY 👇
_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        print("🧠 Loading Cross-Encoder Reranker into memory...")
        _reranker = SentenceTransformerRerank(
            model="cross-encoder/ms-marco-MiniLM-L-12-v2", 
            top_n=3
        )
    return _reranker

def get_retriever_pipeline(session_id: str):
    index = get_session_index(session_id)
    if not index:
        raise ValueError(f"No index found for session {session_id}")
    vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=5)
    return vector_retriever

def retrieve_context(session_id: str, query: str):
    retriever = get_retriever_pipeline(session_id)
    nodes = retriever.retrieve(query)
    
    # 👇 USE THE CACHED MODEL 👇
    reranker = get_reranker()
    
    reranked_nodes = reranker.postprocess_nodes(
        nodes, 
        query_bundle=QueryBundle(query)
    )
    
    results = []
    for node in reranked_nodes:
        results.append(f"[Score: {node.score:.4f}] {node.text}")
        
    return "\n\n".join(results)