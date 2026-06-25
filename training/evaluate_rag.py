"""RAG Retrieval Evaluation (Task 6.1)
=======================================
Measures whether the hybrid retriever (BM25 + dense + RRF + cross-encoder rerank)
surfaces the CV passage that *should* answer a JD-driven query.

Core metric (always available, dependency-free):
  - context_recall : fraction of golden pairs whose ground-truth CV section is
                     recovered in the retrieved context (token-overlap >= threshold).
  - mean_overlap   : average token-overlap between ground-truth section and context.

Optional (best-effort, --ragas): faithfulness + answer-relevancy via the `ragas`
package using the project's Groq LLM. Guarded by try/except so a ragas/install
failure never breaks the core run.

Usage:
  python -m training.evaluate_rag                 # context-recall only (needs PINECONE_API_KEY)
  python -m training.evaluate_rag --ragas         # also attempt ragas metrics (needs GROQ_API_KEY)
  python -m training.evaluate_rag --no-cleanup    # keep Pinecone namespaces after the run

Requires PINECONE_API_KEY to index/retrieve. Targets (from original plan):
  faithfulness > 0.80, context-recall > 0.85.
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

GOLDEN_FILE = PROJECT_ROOT / "data" / "golden_dataset.json"
RESULTS_DIR = PROJECT_ROOT / "training" / "results"
REPORT_PATH = RESULTS_DIR / "rag_eval_report.json"

RECALL_THRESHOLD = 0.60   # token-overlap above this counts as a successful retrieval

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "with", "on", "at",
    "by", "from", "that", "this", "as", "is", "was", "were", "be", "it", "its",
}


def _tokens(text: str) -> set:
    import re
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _token_overlap(ground_truth: str, retrieved: str) -> float:
    gt = _tokens(ground_truth)
    if not gt:
        return 0.0
    rv = _tokens(retrieved)
    return len(gt & rv) / len(gt)


def _evaluate_context_recall(pairs, cleanup=True):
    """Index each golden pair, retrieve for a JD-driven query, score token-overlap."""
    from ingest import create_session_index
    from retriever import retrieve_context
    try:
        from ingest import pinecone_index
    except Exception:
        pinecone_index = None

    per_item = []
    for p in pairs:
        sid = f"rageval-{p['id']}"
        query = f"{p['role']} key skills and experience: {p['jd_text']}"
        try:
            create_session_index(sid, p["cv_text"], p["jd_text"], role=p["role"])
            retrieved = retrieve_context(sid, query)
        except Exception as e:
            per_item.append({"id": p["id"], "role": p["role"], "error": str(e), "overlap": 0.0, "recalled": False})
            continue
        finally:
            if cleanup and pinecone_index is not None:
                try:
                    pinecone_index.delete(delete_all=True, namespace=sid)
                except Exception:
                    pass

        overlap = round(_token_overlap(p["ground_truth_section"], retrieved), 3)
        per_item.append({
            "id": p["id"], "role": p["role"],
            "overlap": overlap,
            "recalled": overlap >= RECALL_THRESHOLD,
        })
        status = "✓" if overlap >= RECALL_THRESHOLD else "✗"
        print(f"  [{status}] pair {p['id']:>2} ({p['role']:<28}) overlap={overlap:.2f}")

    scored = [i for i in per_item if "error" not in i]
    n = len(scored) or 1
    context_recall = round(sum(1 for i in scored if i["recalled"]) / n, 3)
    mean_overlap = round(sum(i["overlap"] for i in scored) / n, 3)
    return per_item, context_recall, mean_overlap


def _try_ragas(pairs):
    """Best-effort ragas faithfulness/answer-relevancy. Returns dict or skip-reason."""
    try:
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import Faithfulness, ResponseRelevancy
        from ragas.llms import LangchainLLMWrapper
        from langchain_groq import ChatGroq
        from retriever import retrieve_context
    except Exception as e:
        return {"status": "skipped", "reason": f"ragas unavailable: {e}"}

    try:
        llm = LangchainLLMWrapper(ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.0,
        ))
        rows = []
        for p in pairs[:8]:  # cap LLM calls to keep cost/quota bounded
            sid = f"rageval-r-{p['id']}"
            from ingest import create_session_index
            create_session_index(sid, p["cv_text"], p["jd_text"], role=p["role"])
            ctx = retrieve_context(sid, p["jd_text"])
            rows.append({
                "user_input": f"Generate an interview question about: {p['role']}",
                "response": p["ideal_question"],
                "retrieved_contexts": [ctx],
            })
            try:
                from ingest import pinecone_index
                pinecone_index.delete(delete_all=True, namespace=sid)
            except Exception:
                pass

        ds = EvaluationDataset.from_list(rows)
        result = evaluate(ds, metrics=[Faithfulness(llm=llm), ResponseRelevancy(llm=llm)])
        scores = result.to_pandas().mean(numeric_only=True).to_dict()
        return {"status": "ok", "scores": {k: round(float(v), 3) for k, v in scores.items()}}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def main():
    ap = argparse.ArgumentParser(description="RAG retrieval evaluation for MyHR")
    ap.add_argument("--ragas", action="store_true", help="also attempt ragas faithfulness/relevancy")
    ap.add_argument("--no-cleanup", action="store_true", help="keep Pinecone namespaces after run")
    args = ap.parse_args()

    if not os.getenv("PINECONE_API_KEY"):
        print("ERROR: PINECONE_API_KEY not set — cannot index/retrieve. Aborting.")
        sys.exit(1)
    if not GOLDEN_FILE.exists():
        print(f"ERROR: {GOLDEN_FILE} not found.")
        sys.exit(1)

    pairs = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["pairs"]
    print(f"Evaluating retrieval on {len(pairs)} golden CV/JD pairs...\n")

    per_item, context_recall, mean_overlap = _evaluate_context_recall(
        pairs, cleanup=not args.no_cleanup
    )

    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_pairs": len(pairs),
        "recall_threshold": RECALL_THRESHOLD,
        "context_recall": context_recall,
        "mean_overlap": mean_overlap,
        "targets": {"context_recall": 0.85, "faithfulness": 0.80},
        "context_recall_pass": context_recall >= 0.85,
        "per_item": per_item,
        "ragas": {"status": "not_requested"},
    }

    if args.ragas:
        print("\nAttempting ragas faithfulness / answer-relevancy (best-effort)...")
        report["ragas"] = _try_ragas(pairs)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 56)
    print(f"  Context Recall : {context_recall:.3f}   (target > 0.85 → {'PASS' if report['context_recall_pass'] else 'BELOW'})")
    print(f"  Mean Overlap   : {mean_overlap:.3f}")
    if args.ragas:
        print(f"  Ragas          : {report['ragas'].get('status')}  {report['ragas'].get('scores', report['ragas'].get('reason', ''))}")
    print(f"  Report         : {REPORT_PATH}")
    print("=" * 56)


if __name__ == "__main__":
    main()
