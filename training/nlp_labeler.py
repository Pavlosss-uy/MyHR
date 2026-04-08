"""
NLP-based answer quality labeler.

Computes 6 objective linguistic signals per answer and maps them to
(relevance, clarity, technical_depth) scores in [0, 100].

No API calls. All signals derived from text analysis only.

Signals:
  1. Type-Token Ratio (TTR)         - vocabulary richness
  2. Sentence Count Normalized      - answer completeness
  3. Technical Keyword Density      - domain relevance / depth
  4. Discourse Marker Score         - coherence and structure
  5. Flesch-Kincaid Grade Level     - technical complexity
  6. Code / Example Presence        - concrete demonstration
"""

import re
import json
import math
import string
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------------
# Topic keyword banks — used for Technical Keyword Density
# Keys match the 'topic' field in eval_data_checkpoint.json
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS = {
    "database management and sql": [
        "index", "query", "join", "transaction", "normalization", "schema",
        "primary key", "foreign key", "constraint", "aggregate", "subquery",
        "execution plan", "b-tree", "clustered", "acid", "deadlock",
    ],
    "devops and ci/cd": [
        "pipeline", "docker", "container", "kubernetes", "deployment", "build",
        "jenkins", "github actions", "artifact", "rollback", "blue-green",
        "canary", "helm", "registry", "infrastructure as code",
    ],
    "frontend development": [
        "component", "state", "props", "dom", "virtual dom", "hook", "render",
        "css", "layout", "responsive", "accessibility", "bundle", "webpack",
        "react", "vue", "angular", "event loop",
    ],
    "javascript and typescript": [
        "async", "await", "promise", "closure", "prototype", "type", "interface",
        "generics", "event loop", "callback", "spread", "destructuring",
        "module", "transpile", "strict mode",
    ],
    "microservices architecture": [
        "service", "api gateway", "load balancer", "message queue", "event",
        "fault tolerance", "circuit breaker", "service mesh", "latency",
        "scalability", "distributed", "docker", "kubernetes", "grpc",
    ],
    "networking and security": [
        "encryption", "tls", "ssl", "firewall", "vpn", "protocol", "packet",
        "authentication", "authorization", "oauth", "jwt", "vulnerability",
        "penetration", "ddos", "certificate",
    ],
    "agile methodology and teamwork": [
        "sprint", "scrum", "kanban", "backlog", "retrospective", "standup",
        "velocity", "story point", "epic", "stakeholder", "iteration",
        "continuous improvement", "cross-functional", "agile",
    ],
    "python": [
        "generator", "decorator", "context manager", "gil", "list comprehension",
        "dictionary", "lambda", "class", "inheritance", "exception",
        "virtual environment", "pip", "asyncio", "dataclass",
    ],
    "machine learning and ai": [
        "model", "training", "overfitting", "regularization", "gradient",
        "loss", "feature", "embedding", "neural network", "backpropagation",
        "cross-validation", "hyperparameter", "inference", "precision", "recall",
    ],
    "system design": [
        "scalability", "availability", "consistency", "partition", "cap theorem",
        "cache", "cdn", "load balancer", "database sharding", "replication",
        "message queue", "event driven", "latency", "throughput",
    ],
    "cloud computing": [
        "instance", "s3", "lambda", "vpc", "auto scaling", "elasticity",
        "serverless", "managed service", "region", "availability zone",
        "iam", "cloud formation", "terraform", "cost optimization",
    ],
    "data structures and algorithms": [
        "complexity", "big o", "array", "linked list", "tree", "graph",
        "hash table", "stack", "queue", "dynamic programming", "recursion",
        "binary search", "sorting", "traversal", "memoization",
    ],
}

# Fallback general software engineering keywords
GENERAL_TECH_KEYWORDS = [
    "algorithm", "function", "variable", "loop", "condition", "class",
    "method", "object", "array", "string", "integer", "boolean",
    "framework", "library", "api", "database", "server", "client",
    "interface", "module", "package", "test", "debug", "performance",
    "memory", "cache", "thread", "async", "error", "exception",
]

DISCOURSE_MARKERS = [
    "however", "therefore", "specifically", "for example", "for instance",
    "in contrast", "as a result", "first", "second", "third", "finally",
    "in addition", "furthermore", "moreover", "on the other hand",
    "to summarize", "in conclusion", "because", "since", "although",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list:
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return [w for w in text.split() if w]


def _count_sentences(text: str) -> int:
    sentences = re.split(r"[.!?]+", text.strip())
    return max(1, len([s for s in sentences if s.strip()]))


def _count_syllables(word: str) -> int:
    """Approximate syllable count for Flesch-Kincaid."""
    word = word.lower().strip(".,!?")
    if not word:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _has_code_or_example(text: str) -> bool:
    """Detect code blocks, numbered steps, or concrete examples."""
    patterns = [
        r"```",                          # markdown code fence
        r"`[^`]+`",                      # inline code
        r"\b(step \d|1\.|2\.|3\.)",      # numbered steps
        r"for example|for instance",     # explicit example signal
        r"\bdef \w+\(",                  # Python function def
        r"\bclass \w+",                  # class definition
        r"SELECT|INSERT|UPDATE|DELETE",  # SQL
        r"\$\w+|\bvar \b|\blet \b|\bconst \b",  # JS variables
        r"import \w+|from \w+ import",   # Python import
    ]
    text_lower = text.lower()
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# 6 Quality Signals
# ---------------------------------------------------------------------------

def signal_ttr(answer: str) -> float:
    """Type-Token Ratio: vocabulary richness. Clamped [0.1, 0.9]."""
    words = _tokenize(answer)
    if len(words) < 3:
        return 0.1
    ttr = len(set(words)) / len(words)
    return float(max(0.1, min(0.9, ttr)))


def signal_sentence_norm(answer: str) -> float:
    """Normalized sentence count. 8 sentences = 1.0."""
    n = _count_sentences(answer)
    return float(min(1.0, n / 8.0))


def signal_keyword_density(answer: str, topic: str) -> float:
    """Technical keyword density relative to answer length."""
    words = _tokenize(answer)
    if not words:
        return 0.0
    topic_lower = topic.lower().strip()
    keywords = TOPIC_KEYWORDS.get(topic_lower, GENERAL_TECH_KEYWORDS)
    answer_lower = answer.lower()
    hits = sum(1 for kw in keywords if kw in answer_lower)
    density = hits / (len(words) + 1)
    return float(min(1.0, density * 8.0))  # scale so ~1 kw per 8 words = 1.0


def signal_discourse(answer: str) -> float:
    """Discourse marker score: coherence / logical structure."""
    answer_lower = answer.lower()
    hits = sum(1 for m in DISCOURSE_MARKERS if m in answer_lower)
    return float(min(1.0, hits / 3.0))


def signal_fkgl_norm(answer: str) -> float:
    """Flesch-Kincaid Grade Level, normalized to [0, 1].

    FKGL = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59
    Grade 5 = score 0.0, Grade 18 = score 1.0 (technical writing)
    """
    words = _tokenize(answer)
    n_words = len(words)
    if n_words < 5:
        return 0.3
    n_sentences = _count_sentences(answer)
    n_syllables = sum(_count_syllables(w) for w in words)
    fkgl = (0.39 * (n_words / n_sentences)
            + 11.8 * (n_syllables / n_words)
            - 15.59)
    normalized = (fkgl - 5.0) / 13.0  # map [5, 18] → [0, 1]
    return float(max(0.0, min(1.0, normalized)))


def signal_code_presence(answer: str) -> float:
    """Binary: 1.0 if answer contains code or concrete example."""
    return 1.0 if _has_code_or_example(answer) else 0.0


# ---------------------------------------------------------------------------
# Composite scores → 3 evaluator heads
# ---------------------------------------------------------------------------

def compute_nlp_scores(answer: str, topic: str) -> dict:
    """Compute raw NLP signal scores for a single answer.

    Returns dict with all 6 signals and composite raw scores (0–100).
    """
    ttr        = signal_ttr(answer)
    sent_norm  = signal_sentence_norm(answer)
    kw_density = signal_keyword_density(answer, topic)
    discourse  = signal_discourse(answer)
    fkgl_norm  = signal_fkgl_norm(answer)
    code_pres  = signal_code_presence(answer)

    raw_relevance = (40 * ttr + 30 * kw_density + 30 * discourse)
    raw_clarity   = (50 * ttr + 30 * sent_norm  + 20 * discourse)
    raw_depth     = (50 * fkgl_norm + 30 * kw_density + 20 * code_pres)

    return {
        "signals": {
            "ttr": ttr, "sent_norm": sent_norm, "kw_density": kw_density,
            "discourse": discourse, "fkgl_norm": fkgl_norm, "code_pres": code_pres,
        },
        "raw_relevance": raw_relevance,
        "raw_clarity":   raw_clarity,
        "raw_depth":     raw_depth,
    }


# ---------------------------------------------------------------------------
# Tier-anchored scaling
# ---------------------------------------------------------------------------

TIER_RANGES = {
    "excellent": (80.0, 100.0),
    "good":      (60.0,  80.0),
    "mediocre":  (35.0,  60.0),
    "poor":      ( 0.0,  35.0),
}


def _scale_to_tier(raw_score: float, tier: str) -> float:
    """Scale raw composite score (0–100) into the tier's expected range.

    Method: min-max normalize the raw score within [0, 100], then map
    linearly into the tier's [lo, hi] interval.
    """
    lo, hi = TIER_RANGES.get(tier, (35.0, 60.0))
    raw_norm = max(0.0, min(100.0, raw_score)) / 100.0
    scaled = lo + raw_norm * (hi - lo)
    return round(float(scaled), 1)


def apply_nlp_labels(samples: list) -> list:
    """Apply NLP quality labels to a list of Q&A samples in place.

    Each sample must have 'question', 'answer', 'topic', 'quality_tier'.
    Adds / overwrites: 'relevance', 'clarity', 'technical_depth', 'overall_quality'.
    """
    for s in samples:
        topic  = s.get("topic", "")
        answer = s.get("answer", "")
        tier   = s.get("quality_tier", "mediocre")

        scores = compute_nlp_scores(answer, topic)

        relevance = _scale_to_tier(scores["raw_relevance"], tier)
        clarity   = _scale_to_tier(scores["raw_clarity"],   tier)
        depth     = _scale_to_tier(scores["raw_depth"],     tier)
        overall   = round((relevance + clarity + depth) / 3.0, 1)

        s["relevance"]       = relevance
        s["clarity"]         = clarity
        s["technical_depth"] = depth
        s["overall_quality"] = overall

    return samples


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import sys
    import numpy as np
    from collections import defaultdict

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    CHECKPOINT   = PROJECT_ROOT / "data" / "eval_data_checkpoint.json"
    OUTPUT       = PROJECT_ROOT / "data" / "eval_training_data.json"

    print("=" * 60)
    print("  NLP Quality Labeler")
    print("=" * 60)

    # Load checkpoint
    with open(CHECKPOINT, encoding="utf-8") as f:
        checkpoint = json.load(f)
    samples = checkpoint["samples"]
    print(f"\nLoaded {len(samples)} samples from checkpoint")

    # Apply NLP labels
    samples = apply_nlp_labels(samples)

    # Extract embeddings (reuse existing ones if present, else generate)
    embedding_source = "existing"
    if "features" not in samples[0]:
        embedding_source = "generating"
        print("Extracting SentenceTransformer embeddings...")
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            questions = [s["question"] for s in samples]
            answers   = [s["answer"]   for s in samples]
            q_emb = model.encode(questions, show_progress_bar=True, batch_size=32)
            a_emb = model.encode(answers,   show_progress_bar=True, batch_size=32)
            for i, s in enumerate(samples):
                import numpy as np_inner
                s["features"] = np_inner.concatenate([q_emb[i], a_emb[i]]).tolist()
        except ImportError:
            print("[WARN] sentence-transformers not available, skipping features")

    # Load existing features from eval_training_data.json if available
    if "features" not in samples[0] and OUTPUT.exists():
        print("Loading existing features from eval_training_data.json...")
        with open(OUTPUT, encoding="utf-8") as f:
            existing = json.load(f)
        existing_map = {s["hash"]: s["features"]
                        for s in existing["samples"]
                        if "features" in s and "hash" in s}
        for s in samples:
            if "hash" in s and s["hash"] in existing_map:
                s["features"] = existing_map[s["hash"]]
        embedding_source = "loaded_from_existing"

    # Stats per tier
    from collections import defaultdict
    tier_stats = defaultdict(lambda: {"relevance": [], "clarity": [], "depth": []})
    for s in samples:
        t = s.get("quality_tier", "?")
        tier_stats[t]["relevance"].append(s["relevance"])
        tier_stats[t]["clarity"].append(s["clarity"])
        tier_stats[t]["depth"].append(s["technical_depth"])

    print("\nScore Distribution by Tier:")
    print("-" * 55)
    print(f"  {'Tier':10s}  {'N':>4}  {'Rel':>6}  {'Cla':>6}  {'Dep':>6}")
    print("-" * 55)
    for tier in ["excellent", "good", "mediocre", "poor"]:
        if tier not in tier_stats:
            continue
        st = tier_stats[tier]
        n  = len(st["relevance"])
        ar = sum(st["relevance"]) / n
        ac = sum(st["clarity"])   / n
        ad = sum(st["depth"])     / n
        print(f"  {tier:10s}  {n:>4}  {ar:>6.1f}  {ac:>6.1f}  {ad:>6.1f}")

    # Verify tier separation
    print("\nTier Separation Check:")
    for head in ["relevance", "clarity", "depth"]:
        exc_mean = (sum(tier_stats["excellent"][head]) /
                    len(tier_stats["excellent"][head]))
        poor_mean = (sum(tier_stats["poor"][head]) /
                     len(tier_stats["poor"][head]))
        gap = exc_mean - poor_mean
        status = "OK" if gap >= 40 else "WARN"
        print(f"  {head:15s}: excellent={exc_mean:.1f}  poor={poor_mean:.1f}"
              f"  gap={gap:.1f}  [{status}]")

    # Build distribution count
    from collections import Counter
    dist = Counter(s["quality_tier"] for s in samples)

    # Save
    output_data = {
        "metadata": {
            "total_samples": len(samples),
            "feature_dim": len(samples[0].get("features", [])),
            "quality_distribution": dict(dist),
            "labeling_method": "nlp_signals",
            "signals": [
                "type_token_ratio",
                "sentence_count_normalized",
                "technical_keyword_density",
                "discourse_marker_score",
                "flesch_kincaid_grade_level",
                "code_example_presence",
            ],
            "embedding_source": embedding_source,
        },
        "samples": samples,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(samples)} labeled samples to {OUTPUT}")
    print("\nNext: python -m training.train_evaluator")


if __name__ == "__main__":
    main()
