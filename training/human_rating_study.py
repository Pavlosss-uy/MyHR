"""
Human-Rating Validation Study (Task 4.6)
=========================================
Samples Q&A pairs from eval_training_data.json and collects human ratings on
the same 0-100 rubric used by the LLM judge.  After rating is complete, computes:
  - Cohen's kappa (human vs LLM, discretized into 4 tiers)
  - Spearman correlation (human vs LLM scores, per criterion)
  - Inter-rater agreement (if multiple raters provide ratings CSV)

Usage — two modes:

  1. Generate rating sheet (no rater interaction required):
       python -m training.human_rating_study --export --n 40 --output ratings_sheet.json

  2. Interactive CLI rating session:
       python -m training.human_rating_study --rate --rater alice

  3. Compute agreement after collecting ratings:
       python -m training.human_rating_study --analyze --ratings alice.json [bob.json ...]

Rubric (shown to each rater):
  Relevance  (0-100): Does the answer address what was asked?
  Clarity    (0-100): Is the answer clear and well-structured?
  Depth      (0-100): Does the answer demonstrate technical depth?
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import random
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE    = PROJECT_ROOT / "data" / "eval_training_data.json"
RATINGS_DIR  = PROJECT_ROOT / "data" / "human_ratings"

RUBRIC = """
RATING RUBRIC
=============
Score each criterion from 0 to 100.

  Relevance  (0-100)
    100 = Directly and fully answers the question
     75 = Mostly relevant, minor drift
     50 = Partially answers, goes off-topic
     25 = Barely addresses the question
      0 = Completely irrelevant

  Clarity  (0-100)
    100 = Exceptionally clear, well-organized
     75 = Mostly clear, small ambiguities
     50 = Somewhat clear but hard to follow
     25 = Confusing or disorganized
      0 = Incomprehensible

  Technical Depth  (0-100)
    100 = Deep insight, concrete examples, advanced concepts
     75 = Good depth with some specifics
     50 = Surface-level understanding
     25 = Vague or mostly generic
      0 = No technical content
"""

TIER_BOUNDARIES = {
    "excellent": (75, 100),
    "good":      (50, 74),
    "mediocre":  (25, 49),
    "poor":      (0,  24),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_to_tier(score: float) -> str:
    for tier, (lo, hi) in TIER_BOUNDARIES.items():
        if lo <= score <= hi:
            return tier
    return "poor"


def _load_samples(n: int = 40, seed: int = 42) -> list:
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    samples = data["samples"]

    # Stratified sample: ~equal per tier
    by_tier: dict = {}
    for s in samples:
        tier = s.get("quality_tier", _score_to_tier(s.get("overall_quality", 0)))
        by_tier.setdefault(tier, []).append(s)

    rng = random.Random(seed)
    per_tier = max(1, n // max(len(by_tier), 1))
    selected = []
    for tier, tier_samples in by_tier.items():
        selected.extend(rng.sample(tier_samples, min(per_tier, len(tier_samples))))

    rng.shuffle(selected)
    return selected[:n]


def _cohen_kappa(rater_a: list, rater_b: list, labels: list) -> float:
    """Compute Cohen's kappa for two lists of categorical labels."""
    from collections import Counter
    n = len(rater_a)
    assert n == len(rater_b), "Rater lists must have equal length"

    label_set = sorted(set(labels))
    label_idx = {l: i for i, l in enumerate(label_set)}
    k = len(label_set)

    # Confusion matrix
    cm = [[0] * k for _ in range(k)]
    for a, b in zip(rater_a, rater_b):
        cm[label_idx[a]][label_idx[b]] += 1

    po = sum(cm[i][i] for i in range(k)) / n

    row_totals = [sum(cm[i]) for i in range(k)]
    col_totals = [sum(cm[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row_totals[i] * col_totals[i] for i in range(k)) / (n * n)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def _spearman(x: list, y: list) -> float:
    """Spearman rank correlation."""
    n = len(x)
    if n < 2:
        return 0.0

    def _rank(lst):
        sorted_pairs = sorted(enumerate(lst), key=lambda t: t[1])
        ranks = [0.0] * n
        for rank, (idx, _) in enumerate(sorted_pairs):
            ranks[idx] = float(rank + 1)
        return ranks

    rx, ry = _rank(x), _rank(y)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num   = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    denom = (sum((v - mean_rx) ** 2 for v in rx) *
             sum((v - mean_ry) ** 2 for v in ry)) ** 0.5
    return num / denom if denom else 0.0


# ---------------------------------------------------------------------------
# Mode 1 — Export rating sheet
# ---------------------------------------------------------------------------

def export_sheet(n: int = 40, output: str = "ratings_sheet.json", seed: int = 42):
    samples = _load_samples(n, seed)
    sheet = []
    for i, s in enumerate(samples):
        sheet.append({
            "id":            i,
            "question":      s.get("question", ""),
            "answer":        s.get("answer", ""),
            "llm_tier":      s.get("quality_tier", ""),
            "llm_relevance": s.get("relevance", None),
            "llm_clarity":   s.get("clarity", None),
            "llm_depth":     s.get("technical_depth", None),
            "human_relevance":  None,
            "human_clarity":    None,
            "human_depth":      None,
        })

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sheet, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(sheet)} Q&A pairs to {out_path}")
    print("Fill in human_relevance / human_clarity / human_depth (0-100) for each item,")
    print("then run:  python -m training.human_rating_study --analyze --ratings <file.json>")


# ---------------------------------------------------------------------------
# Mode 2 — Interactive CLI rating session
# ---------------------------------------------------------------------------

def rate_interactive(rater: str, n: int = 40, seed: int = 42):
    print(RUBRIC)
    samples = _load_samples(n, seed)
    results = []

    print(f"\nYou will rate {len(samples)} Q&A pairs.")
    print("Type a score 0-100 for each criterion, or 's' to skip, 'q' to quit early.\n")

    for i, s in enumerate(samples):
        print(f"\n{'='*70}")
        print(f"[{i+1}/{len(samples)}]  LLM tier: {s.get('quality_tier', 'N/A')}")
        print(f"\nQuestion:\n  {s.get('question', '(none)')}")
        print(f"\nAnswer:\n  {s.get('answer', '(none)')[:1000]}")
        print()

        scores = {}
        skip = False
        for crit in ["relevance", "clarity", "depth"]:
            while True:
                raw = input(f"  {crit.capitalize()} (0-100) > ").strip().lower()
                if raw == "q":
                    print("Quitting early...")
                    _save_ratings(results, rater)
                    return
                if raw == "s":
                    skip = True
                    break
                try:
                    val = int(raw)
                    if 0 <= val <= 100:
                        scores[crit] = val
                        break
                except ValueError:
                    pass
                print("  Please enter a number 0-100, 's' to skip, or 'q' to quit.")
            if skip:
                break

        if not skip:
            results.append({
                "id":               i,
                "question":         s.get("question", ""),
                "answer":           s.get("answer", ""),
                "llm_tier":         s.get("quality_tier", ""),
                "llm_relevance":    s.get("relevance", None),
                "llm_clarity":      s.get("clarity", None),
                "llm_depth":        s.get("technical_depth", None),
                "human_relevance":  scores.get("relevance"),
                "human_clarity":    scores.get("clarity"),
                "human_depth":      scores.get("depth"),
            })

    _save_ratings(results, rater)


def _save_ratings(results: list, rater: str):
    RATINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RATINGS_DIR / f"{rater}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} ratings to {out_path}")


# ---------------------------------------------------------------------------
# Mode 3 — Analyze collected ratings
# ---------------------------------------------------------------------------

def analyze(rating_files: list):
    all_rater_data = {}
    for path in rating_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rater_name = Path(path).stem
        all_rater_data[rater_name] = {item["id"]: item for item in data}

    raters = list(all_rater_data.keys())
    print(f"\nAnalyzing {len(raters)} rater(s): {raters}")

    if not raters:
        print("No rating files found.")
        return

    # --- Human vs LLM agreement ---
    print("\n" + "="*60)
    print("Human vs LLM Agreement")
    print("="*60)

    for rater_name, rater_data in all_rater_data.items():
        items = list(rater_data.values())
        print(f"\nRater: {rater_name}  ({len(items)} items rated)")

        for crit in ["relevance", "clarity", "depth"]:
            llm_key   = f"llm_{crit}"
            human_key = f"human_{crit}"
            pairs = [(item[llm_key], item[human_key])
                     for item in items
                     if item.get(llm_key) is not None and item.get(human_key) is not None]
            if not pairs:
                continue
            llm_scores, human_scores = zip(*pairs)
            rho = _spearman(list(llm_scores), list(human_scores))
            print(f"  {crit:<12}  Spearman(human, LLM) = {rho:+.3f}  (n={len(pairs)})")

        # Kappa on tier labels
        tier_pairs = [
            (_score_to_tier(item["llm_relevance"] or 0), _score_to_tier(item["human_relevance"] or 0))
            for item in items
            if item.get("llm_relevance") is not None and item.get("human_relevance") is not None
        ]
        if tier_pairs:
            tiers_a, tiers_b = zip(*tier_pairs)
            all_tiers = list(TIER_BOUNDARIES.keys())
            kappa = _cohen_kappa(list(tiers_a), list(tiers_b), all_tiers)
            interp = ("poor" if kappa < 0.20 else
                      "fair" if kappa < 0.40 else
                      "moderate" if kappa < 0.60 else
                      "substantial" if kappa < 0.80 else "almost perfect")
            print(f"  Cohen's kappa (tier, relevance): {kappa:+.3f}  [{interp}]")

    # --- Inter-rater agreement (if multiple raters) ---
    if len(raters) >= 2:
        print("\n" + "="*60)
        print("Inter-Rater Agreement")
        print("="*60)
        from itertools import combinations
        for r1, r2 in combinations(raters, 2):
            data1, data2 = all_rater_data[r1], all_rater_data[r2]
            common_ids = set(data1) & set(data2)
            if not common_ids:
                print(f"  {r1} vs {r2}: no overlapping items")
                continue
            print(f"\n  {r1} vs {r2}  ({len(common_ids)} common items)")
            for crit in ["relevance", "clarity", "depth"]:
                human_key = f"human_{crit}"
                pairs = [(data1[i][human_key], data2[i][human_key])
                         for i in common_ids
                         if data1[i].get(human_key) is not None
                         and data2[i].get(human_key) is not None]
                if pairs:
                    scores_a, scores_b = zip(*pairs)
                    rho = _spearman(list(scores_a), list(scores_b))
                    print(f"    {crit:<12}  Spearman = {rho:+.3f}")
            # Kappa
            tier_pairs = [
                (_score_to_tier(data1[i].get("human_relevance") or 0),
                 _score_to_tier(data2[i].get("human_relevance") or 0))
                for i in common_ids
                if data1[i].get("human_relevance") is not None
                and data2[i].get("human_relevance") is not None
            ]
            if tier_pairs:
                ta, tb = zip(*tier_pairs)
                kappa = _cohen_kappa(list(ta), list(tb), list(TIER_BOUNDARIES.keys()))
                print(f"    {'kappa (tier)':<12}  κ = {kappa:+.3f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Human rating validation study for MyHR")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", action="store_true",
                      help="Export rating sheet JSON for manual filling")
    mode.add_argument("--rate",   action="store_true",
                      help="Interactive CLI rating session")
    mode.add_argument("--analyze", action="store_true",
                      help="Analyze completed rating files")

    parser.add_argument("--n",       type=int,   default=40,
                        help="Number of Q&A pairs to sample (default: 40)")
    parser.add_argument("--seed",    type=int,   default=42)
    parser.add_argument("--output",  type=str,   default="ratings_sheet.json",
                        help="Output path for --export mode")
    parser.add_argument("--rater",   type=str,   default="rater1",
                        help="Rater name for --rate mode (used as filename)")
    parser.add_argument("--ratings", type=str,   nargs="+",
                        help="Rating JSON file(s) for --analyze mode")

    args = parser.parse_args()

    if args.export:
        if not DATA_FILE.exists():
            print(f"Error: {DATA_FILE} not found. Run generate_eval_data.py first.")
            sys.exit(1)
        export_sheet(n=args.n, output=args.output, seed=args.seed)

    elif args.rate:
        if not DATA_FILE.exists():
            print(f"Error: {DATA_FILE} not found. Run generate_eval_data.py first.")
            sys.exit(1)
        rate_interactive(rater=args.rater, n=args.n, seed=args.seed)

    elif args.analyze:
        if not args.ratings:
            # Auto-discover all JSON files in ratings dir
            files = list(RATINGS_DIR.glob("*.json")) if RATINGS_DIR.exists() else []
            if not files:
                print(f"No rating files found in {RATINGS_DIR} and none specified with --ratings")
                sys.exit(1)
            args.ratings = [str(f) for f in files]
        analyze(args.ratings)


if __name__ == "__main__":
    main()
