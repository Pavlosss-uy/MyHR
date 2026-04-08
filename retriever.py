import sys

# --- WINDOWS PATCH: Mock the 'resource' module ---
if sys.platform == "win32":
    import types
    resource_mock = types.ModuleType("resource")
    resource_mock.RLIMIT_NOFILE = 7

    def getrlimit(resource):
        return (4096, 4096)

    def setrlimit(resource, limits):
        pass

    resource_mock.getrlimit = getrlimit
    resource_mock.setrlimit = setrlimit
    sys.modules["resource"] = resource_mock
# --- END WINDOWS PATCH ---

from rank_bm25 import BM25Okapi

from llama_index.core import QueryBundle
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.schema import TextNode, NodeWithScore

from ingest import get_session_index, load_session_raw_texts

# ------------------------------
# Cached models / session BM25s
# ------------------------------
_reranker = None
_hybrid_cache = {}


def get_reranker():
    global _reranker
    if _reranker is None:
        print("🧠 Loading Cross-Encoder Reranker into memory...")
        _reranker = SentenceTransformerRerank(
            model="cross-encoder/ms-marco-MiniLM-L-12-v2",
            top_n=3
        )
    return _reranker


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


class HybridRetriever:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.vector_retriever = self._build_vector_retriever(session_id)
        self.bm25_corpus = []
        self.bm25 = None
        self._load_bm25()

    def _build_vector_retriever(self, session_id: str):
        index = get_session_index(session_id)
        if not index:
            raise ValueError(f"No index found for session {session_id}")

        return VectorIndexRetriever(
            index=index,
            similarity_top_k=20
        )

    def _load_bm25(self):
        raw_docs = load_session_raw_texts(self.session_id)

        # Filter empty chunks
        self.bm25_corpus = [doc.strip() for doc in raw_docs if doc and doc.strip()]

        if not self.bm25_corpus:
            self.bm25 = None
            return

        tokenized_corpus = [normalize_text(doc).split() for doc in self.bm25_corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(self, query: str, top_k: int = 20):
        """
        Returns fused candidate nodes before reranking.
        """
        # ---------- Stage 1a: Dense retrieval ----------
        dense_nodes = self.vector_retriever.retrieve(query)

        # ---------- Stage 1b: Sparse retrieval ----------
        bm25_nodes = []
        if self.bm25 is not None and self.bm25_corpus:
            tokenized_query = normalize_text(query).split()
            bm25_scores = self.bm25.get_scores(tokenized_query)

            ranked_indices = sorted(
                range(len(bm25_scores)),
                key=lambda i: bm25_scores[i],
                reverse=True
            )[:top_k]

            for idx in ranked_indices:
                text = self.bm25_corpus[idx]
                score = float(bm25_scores[idx])
                bm25_nodes.append(
                    NodeWithScore(
                        node=TextNode(text=text, metadata={"source": "bm25"}),
                        score=score
                    )
                )

        # ---------- Stage 2: Reciprocal Rank Fusion ----------
        k = 60  # smoothing constant
        fused_scores = {}
        text_to_node = {}

        # Dense contribution
        for rank, node_with_score in enumerate(dense_nodes):
            text = node_with_score.text.strip()
            if not text:
                continue

            fused_scores[text] = fused_scores.get(text, 0.0) + 1.0 / (k + rank + 1)
            text_to_node[text] = node_with_score  # prefer dense node object if available

        # BM25 contribution
        for rank, node_with_score in enumerate(bm25_nodes):
            text = node_with_score.text.strip()
            if not text:
                continue

            fused_scores[text] = fused_scores.get(text, 0.0) + 1.0 / (k + rank + 1)

            # only add BM25 node if text wasn't already present from dense retrieval
            if text not in text_to_node:
                text_to_node[text] = node_with_score

        # Build fused candidate list
        fused_ranked = sorted(
            fused_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        fused_nodes = []
        for text, fused_score in fused_ranked:
            base_node = text_to_node[text]
            fused_nodes.append(
                NodeWithScore(
                    node=base_node.node,
                    score=fused_score
                )
            )

        return fused_nodes


def get_hybrid_retriever(session_id: str):
    """
    Cache a HybridRetriever per session to avoid rebuilding BM25 repeatedly.
    """
    global _hybrid_cache

    if session_id not in _hybrid_cache:
        _hybrid_cache[session_id] = HybridRetriever(session_id)

    return _hybrid_cache[session_id]


def retrieve_context(session_id: str, query: str):
    """
    Full retrieval pipeline:
    1) Dense retrieval from Pinecone
    2) BM25 sparse retrieval from locally stored chunks
    3) Reciprocal Rank Fusion
    4) Cross-encoder reranking
    5) Return top 3 formatted results
    """
    hybrid_retriever = get_hybrid_retriever(session_id)

    # Get fused candidates
    fused_nodes = hybrid_retriever.retrieve(query, top_k=20)

    # Cross-encoder rerank top candidates -> final top 3
    reranker = get_reranker()
    reranked_nodes = reranker.postprocess_nodes(
        fused_nodes,
        query_bundle=QueryBundle(query)
    )

    if not reranked_nodes:
        return "No relevant context found."

    results = []
    for node in reranked_nodes:
        score = node.score if node.score is not None else 0.0
        results.append(f"[Score: {score:.4f}] {node.text}")

    return "\n\n".join(results)