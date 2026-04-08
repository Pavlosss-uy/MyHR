"""
Generate real performance prediction training data from the Stack Overflow
2018 Developer Survey using salary percentile (within DevType) as a proxy
for developer value / on-the-job performance.

Produces data/performance_data.json:
  {"samples": [{"features": [8 floats], "label": float (1.0–10.0)}, ...],
   "metadata": {...}}

Usage:
  python training/generate_performance_data.py
  python training/generate_performance_data.py --output data/performance_data.json
"""

import json
import argparse
import warnings
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# Reuse feature builder from generate_ranking_data
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from training.generate_ranking_data import (
    build_features,
    COMPANY_SIZE_MAP,
    EDUCATION_MAP,
    PROJECT_ROOT,
    SURVEY_PATH,
)

OUTPUT_PATH = PROJECT_ROOT / "data" / "performance_data.json"

# Seniority proxy from DevType string
SENIORITY_KEYWORDS = {
    "student": 0.0,
    "academic researcher": 0.1,
    "designer": 0.2,
    "data or business analyst": 0.3,
    "qa": 0.3,
    "front-end": 0.4,
    "back-end": 0.4,
    "full-stack": 0.5,
    "mobile": 0.5,
    "data scientist": 0.6,
    "devops": 0.6,
    "embedded": 0.6,
    "game": 0.5,
    "database": 0.5,
    "machine learning": 0.7,
    "engineer, data": 0.7,
    "engineering manager": 0.8,
    "c-suite": 1.0,
    "executive": 1.0,
    "cto": 1.0,
    "ceo": 1.0,
}


def devtype_seniority(devtype_str: str) -> float:
    """Map DevType string to seniority score [0, 1]."""
    lower = devtype_str.lower()
    best = 0.3  # default: mid-level
    for kw, score in SENIORITY_KEYWORDS.items():
        if kw in lower:
            best = max(best, score)
    return best


def generate(seed: int = 42) -> list:
    rng = np.random.default_rng(seed)

    print(f"Loading survey from {SURVEY_PATH} ...")
    df = pd.read_csv(SURVEY_PATH, encoding="latin-1", low_memory=False)
    print(f"  Total rows: {len(df):,}")

    # Filter: need salary and DevType
    df = df[df["ConvertedSalary"].notna() & df["DevType"].notna()].copy()
    df = df[(df["ConvertedSalary"] > 0) & (df["ConvertedSalary"] <= 500_000)]
    print(f"  After salary filter: {len(df):,} rows")

    # Build features + labels
    samples = []
    skipped = 0

    for _, row in df.iterrows():
        feat = build_features(row.to_dict())
        if feat is None:
            skipped += 1
            continue

        # Replace placeholder [7] with seniority (salary percentile added below)
        devtype_str = str(row["DevType"]).strip()
        feat[7] = devtype_seniority(devtype_str)

        samples.append({
            "features": feat,
            "salary":   float(row["ConvertedSalary"]),
            "devtype":  devtype_str.split(";")[0].strip(),
        })

    print(f"  Built {len(samples):,} feature vectors ({skipped} skipped)")

    # Add salary percentile within DevType — this becomes the training label
    groups = defaultdict(list)
    for i, s in enumerate(samples):
        groups[s["devtype"]].append(i)

    for dev_type, indices in groups.items():
        if len(indices) < 5:
            continue
        salaries = np.array([samples[i]["salary"] for i in indices])
        ranks = salaries.argsort().argsort()
        percentiles = ranks / (len(ranks) - 1 + 1e-9)
        for j, idx in enumerate(indices):
            # Scale percentile [0, 1] → label [1.0, 10.0]
            samples[idx]["label"] = float(1.0 + percentiles[j] * 9.0)

    # Remove samples without a label (groups < 5 rows)
    samples = [s for s in samples if "label" in s]
    print(f"  Samples with valid label: {len(samples):,}")

    # Strip helper fields, keep only features + label
    out = [{"features": s["features"], "label": s["label"]} for s in samples]

    return out, samples


def main():
    parser = argparse.ArgumentParser(
        description="Generate real performance prediction data from SO survey"
    )
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    out_samples, raw_samples = generate(seed=args.seed)

    # Stats
    labels = np.array([s["label"] for s in out_samples])
    print(f"\nLabel distribution (salary percentile scaled 1–10):")
    print(f"  Min:    {labels.min():.2f}")
    print(f"  Max:    {labels.max():.2f}")
    print(f"  Mean:   {labels.mean():.2f}")
    print(f"  Median: {np.median(labels):.2f}")
    print(f"  Std:    {labels.std():.2f}")

    # DevType distribution
    devtype_counts = defaultdict(int)
    for s in raw_samples:
        if "label" in s:
            devtype_counts[s["devtype"]] += 1
    top5 = sorted(devtype_counts.items(), key=lambda x: -x[1])[:5]
    print("\nTop 5 DevTypes by sample count:")
    for dt, cnt in top5:
        print(f"  {dt[:40]:40s}  {cnt:>5}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": {
            "total_samples": len(out_samples),
            "feature_dim": 8,
            "feature_names": [
                "years_coding_prof_norm",
                "n_languages_norm",
                "n_frameworks_norm",
                "has_backend_lang",
                "has_frontend_lang",
                "company_size_norm",
                "education_level_norm",
                "devtype_seniority_norm",
            ],
            "label": "salary_percentile_within_devtype_scaled_1_to_10",
            "label_range": [1.0, 10.0],
            "source": "Stack Overflow 2018 Developer Survey",
            "salary_filter": "0 < ConvertedSalary <= 500000 USD/year",
        },
        "samples": out_samples,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(out_samples):,} samples to {out_path}")
    print("Next: python -m training.train_predictor")


if __name__ == "__main__":
    main()
