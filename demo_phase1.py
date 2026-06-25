"""
demo_phase1.py — See the Phase 1 fixes with your own eyes.

Run:  python demo_phase1.py

Shows:
  FIX #1  The answer-evaluator now scores good vs bad answers DIFFERENTLY
          (because training now uses the same embeddings as inference).
  FIX #2  The CV-grounding guard: empty/placeholder CV -> generic question,
          real CV -> normal flow (so the AI can't invent CV details).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

# Load .env so importing agent/retriever (which init Pinecone) works.
from dotenv import load_dotenv
load_dotenv()

print("\n" + "=" * 64)
print("  PHASE 1 DEMO")
print("=" * 64)

# ─────────────────────────────────────────────────────────────────────────────
# FIX #1 — Evaluator now responds to answer quality
# ─────────────────────────────────────────────────────────────────────────────
print("\n[FIX #1] Answer-evaluator: good vs bad answers should now SEPARATE\n")

import torch
from sentence_transformers import SentenceTransformer
from models.registry import registry

embedder = SentenceTransformer("all-mpnet-base-v2")   # exact inference embedder
evaluator = registry.load_evaluator()                 # loads the retrained, guarded checkpoint
device = next(evaluator.parameters()).device

answers = {
    "EXCELLENT (detailed, specific)":
        "I reduced p99 latency from 1.2s to 90ms by adding a composite index on the "
        "(tenant_id, created_at) columns, switching the hot query to a keyset pagination "
        "pattern, and caching the aggregate counts in Redis with a 30s TTL. I validated "
        "the change with a load test at 5x peak traffic before rolling out.",
    "MEDIOCRE (vague)":
        "I made the database faster by adding some indexes and a bit of caching, and it "
        "seemed to help with the slow pages.",
    "POOR (non-answer)":
        "Um, I'm not really sure, I didn't work on that part much. Maybe something with the database?",
}

print(f"  {'Answer':<34}{'relevance':>10}{'clarity':>9}{'depth':>8}{'overall':>9}")
print("  " + "-" * 68)
for label, text in answers.items():
    emb = embedder.encode(text, convert_to_numpy=True)
    t = torch.tensor(emb, dtype=torch.float32).unsqueeze(0).to(device)
    s = evaluator.evaluate_answer(t)
    print(f"  {label:<34}{s['relevance']:>10}{s['clarity']:>9}{s['technical_depth']:>8}{s['overall']:>9}")

print("\n  → A clear top-to-bottom drop means the evaluator now tracks quality.")
print("    (Before the fix it was fed a different vector space and produced noise.)")

# ─────────────────────────────────────────────────────────────────────────────
# FIX #2 — CV grounding guard
# ─────────────────────────────────────────────────────────────────────────────
print("\n[FIX #2] CV grounding guard: empty CV must NOT produce a CV-specific question\n")

from agent import _has_grounded_cv, _generic_question

samples = {
    "No CV context found.": "placeholder (retrieval failed)",
    "": "empty",
    "Candidate: Jane | Led a migration to Kubernetes and Go, cut costs 35%.": "real CV chunk",
}
for cv, desc in samples.items():
    grounded = _has_grounded_cv(cv)
    verdict = "REAL CV → ask CV-grounded question" if grounded else "NO CV → ask generic question"
    print(f"  {desc:<28} grounded={str(grounded):<6} {verdict}")

print(f"\n  Example generic fallback used when CV is missing:\n    \"{_generic_question(0)}\"")
print("\n" + "=" * 64)
print("  Done. Both fixes are observable above.")
print("=" * 64 + "\n")
