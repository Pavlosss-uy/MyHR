"""
CSV → JSON Converter for Evaluator Training Data
===================================================
Converts the existing synthetic_interview_data.csv (504 samples)
into the eval_training_data.json format expected by train_evaluator.py
and train_cross_encoder.py.

Pipeline:
1. Read CSV with columns: question, answer, relevance, clarity, technical_depth, quality
2. Extract 768-dim sentence embeddings (Q+A concatenated via all-MiniLM-L6-v2)
3. Save to data/eval_training_data.json

Usage:
    python training/convert_csv_to_eval_json.py
"""

import os
import sys
import csv
import json
import numpy as np
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

CSV_PATH = os.path.join(PROJECT_ROOT, "data", "synthetic_interview_data.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "eval_training_data.json")


def main():
    print("=" * 60)
    print("  📊 CSV → JSON Converter for Evaluator Training Data")
    print("=" * 60)

    # ── Step 1: Read CSV ────────────────────────────────────────────
    if not os.path.exists(CSV_PATH):
        print(f"\n❌ CSV not found at {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n📂 Loaded {len(rows)} samples from CSV")
    print(f"   Columns: {list(rows[0].keys())}")

    # ── Step 2: Convert to samples ──────────────────────────────────
    samples = []
    skipped = 0

    for row in rows:
        try:
            question = row.get("question", "").strip()
            answer = row.get("answer", "").strip()

            if not question or not answer:
                skipped += 1
                continue

            relevance = float(row.get("relevance", 50))
            clarity = float(row.get("clarity", 50))
            technical_depth = float(row.get("technical_depth", 50))

            # overall_quality: use 'quality' column if present, else average
            quality_raw = row.get("quality", "")
            if quality_raw and quality_raw.strip():
                overall_quality = float(quality_raw)
            else:
                overall_quality = np.mean([relevance, clarity, technical_depth])

            # Determine quality tier from overall_quality score
            if overall_quality >= 80:
                tier = "excellent"
            elif overall_quality >= 60:
                tier = "good"
            elif overall_quality >= 40:
                tier = "mediocre"
            else:
                tier = "poor"

            samples.append({
                "question": question,
                "answer": answer,
                "relevance": int(np.clip(relevance, 0, 100)),
                "clarity": int(np.clip(clarity, 0, 100)),
                "technical_depth": int(np.clip(technical_depth, 0, 100)),
                "overall_quality": int(np.clip(overall_quality, 0, 100)),
                "quality_tier": tier,
                "topic": row.get("category", "general"),
            })
        except (ValueError, KeyError) as e:
            skipped += 1
            continue

    print(f"   Converted: {len(samples)} samples ({skipped} skipped)")

    # Distribution summary
    tier_counts = {}
    for s in samples:
        tier_counts[s["quality_tier"]] = tier_counts.get(s["quality_tier"], 0) + 1
    print(f"   Quality tiers: {tier_counts}")

    # ── Step 3: Extract embeddings ──────────────────────────────────
    print("\n🧠 Extracting sentence embeddings...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"   Model: all-MiniLM-L6-v2 ({embedding_dim}-dim)")
    print(f"   Output: {embedding_dim * 2}-dim (Q + A concatenated)")

    questions = [s["question"] for s in samples]
    answers = [s["answer"] for s in samples]

    q_embeddings = model.encode(questions, show_progress_bar=True, batch_size=32)
    a_embeddings = model.encode(answers, show_progress_bar=True, batch_size=32)

    for i, sample in enumerate(samples):
        combined = np.concatenate([q_embeddings[i], a_embeddings[i]])
        sample["features"] = combined.tolist()

    print(f"\n✅ Extracted {len(samples)} feature vectors ({embedding_dim * 2}-dim each)")

    # ── Step 4: Save JSON ───────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "created": datetime.now().isoformat(),
                "source": "synthetic_interview_data.csv",
                "total_samples": len(samples),
                "feature_dim": embedding_dim * 2,
                "quality_distribution": tier_counts,
            },
            "samples": samples,
        }, f, indent=2)

    file_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n💾 Saved to {OUTPUT_PATH} ({file_size_mb:.1f} MB)")

    # ── Score distribution ──────────────────────────────────────────
    print("\n📈 Score Distribution by Tier:")
    print("-" * 50)
    for tier in ["excellent", "good", "mediocre", "poor"]:
        tier_samples = [s for s in samples if s["quality_tier"] == tier]
        if tier_samples:
            avg_rel = np.mean([s["relevance"] for s in tier_samples])
            avg_cla = np.mean([s["clarity"] for s in tier_samples])
            avg_dep = np.mean([s["technical_depth"] for s in tier_samples])
            avg_ovr = np.mean([s["overall_quality"] for s in tier_samples])
            print(f"  {tier:10s} ({len(tier_samples):3d}): "
                  f"rel={avg_rel:.1f} cla={avg_cla:.1f} dep={avg_dep:.1f} ovr={avg_ovr:.1f}")

    print("\n✅ Conversion complete! Next steps:")
    print("   python training/train_evaluator.py")
    print("   python training/train_cross_encoder.py")


if __name__ == "__main__":
    main()
