"""
Generate real candidate ranking triplets from the Stack Overflow 2018
Developer Survey using salary percentile as a performance proxy.

Produces data/ranking_pairs.json:
  [{"anchor": [8 floats], "positive": [8 floats], "negative": [8 floats]}, ...]

Usage:
  python training/generate_ranking_data.py
  python training/generate_ranking_data.py --n-per-devtype 100 --output data/ranking_pairs.json
"""

import json
import argparse
import warnings
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SURVEY_PATH  = PROJECT_ROOT / "data" / "archive" / "survey_results_public.csv"
OUTPUT_PATH  = PROJECT_ROOT / "data" / "ranking_pairs.json"

# ---------------------------------------------------------------------------
# Feature encoding
# ---------------------------------------------------------------------------

COMPANY_SIZE_ORDER = [
    "Fewer than 10 employees",
    "10 to 19 employees",
    "20 to 99 employees",
    "100 to 499 employees",
    "500 to 999 employees",
    "1,000 to 4,999 employees",
    "5,000 to 9,999 employees",
    "10,000 or more employees",
]
COMPANY_SIZE_MAP = {v: i / (len(COMPANY_SIZE_ORDER) - 1)
                    for i, v in enumerate(COMPANY_SIZE_ORDER)}

EDUCATION_ORDER = [
    "I never completed any formal education",
    "Primary/elementary school",
    "Secondary school",
    "Some college/university study without earning a degree",
    "Associate degree",
    "Bachelor's degree",
    "Master's degree",
    "Doctoral degree",
    "Professional degree",
]
EDUCATION_MAP = {v: i / (len(EDUCATION_ORDER) - 1)
                 for i, v in enumerate(EDUCATION_ORDER)}

BACKEND_LANGS  = {"python", "java", "c#", "c++", "ruby", "go", "scala", "kotlin", "php"}
FRONTEND_LANGS = {"javascript", "typescript", "css", "html", "coffeescript"}


def _years_to_float(val) -> float:
    """Convert YearsCodingProf string to numeric years."""
    if pd.isna(val):
        return float("nan")
    s = str(val).lower().strip()
    if "less than" in s or "< 1" in s:
        return 0.5
    try:
        parts = s.split("-")
        if len(parts) == 2:
            lo = float(parts[0].strip().split()[0])
            hi_str = parts[1].strip().split()[0]
            hi = float(hi_str) if hi_str.replace(".", "").isdigit() else lo + 4
            return (lo + hi) / 2.0
        return float(s.split()[0])
    except Exception:
        return float("nan")


def build_features(row) -> list:
    """Encode a survey row as an 8-D feature vector.

    Returns None if required fields are missing.

    Dimensions:
      [0] years_coding_prof_norm  (0–1)
      [1] n_languages_norm        (0–1)
      [2] n_frameworks_norm       (0–1)
      [3] has_backend_lang        (0 or 1)
      [4] has_frontend_lang       (0 or 1)
      [5] company_size_norm       (0–1)
      [6] education_level_norm    (0–1)
      [7] salary_percentile       (0–1, filled separately)
    """
    # [0] years of professional coding
    years = _years_to_float(row.get("YearsCodingProf"))
    if np.isnan(years):
        return None
    years_norm = float(np.clip(years / 20.0, 0.0, 1.0))

    # [1] number of languages
    langs_raw = row.get("LanguageWorkedWith", "")
    langs = [l.strip().lower() for l in str(langs_raw).split(";") if l.strip()] \
        if not pd.isna(langs_raw) else []
    n_langs_norm = float(np.clip(len(langs) / 15.0, 0.0, 1.0))

    # [2] number of frameworks
    fwks_raw = row.get("FrameworkWorkedWith", "")
    fwks = [f.strip() for f in str(fwks_raw).split(";") if f.strip()] \
        if not pd.isna(fwks_raw) else []
    n_fwks_norm = float(np.clip(len(fwks) / 10.0, 0.0, 1.0))

    # [3] has backend language
    has_backend = float(any(l in BACKEND_LANGS for l in langs))

    # [4] has frontend language
    has_frontend = float(any(l in FRONTEND_LANGS for l in langs))

    # [5] company size
    company_size = row.get("CompanySize", "")
    size_norm = COMPANY_SIZE_MAP.get(str(company_size).strip(), float("nan"))
    if np.isnan(size_norm):
        size_norm = 0.5  # median fallback

    # [6] education level
    edu = row.get("FormalEducation", "")
    edu_norm = EDUCATION_MAP.get(str(edu).strip(), float("nan"))
    if np.isnan(edu_norm):
        edu_norm = 0.5  # median fallback

    # [7] salary percentile — filled later per DevType group
    return [years_norm, n_langs_norm, n_fwks_norm, has_backend, has_frontend,
            size_norm, edu_norm, 0.0]


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate(n_per_devtype: int = 200, seed: int = 42) -> list:
    rng = np.random.default_rng(seed)

    print(f"Loading survey from {SURVEY_PATH} ...")
    df = pd.read_csv(SURVEY_PATH, encoding="latin-1", low_memory=False)
    print(f"  Total rows: {len(df):,}")

    # Filter: need salary and DevType
    df = df[df["ConvertedSalary"].notna() & df["DevType"].notna()].copy()
    # Remove clear outliers
    df = df[(df["ConvertedSalary"] > 0) & (df["ConvertedSalary"] <= 500_000)]
    print(f"  After salary filter: {len(df):,} rows")

    # Build feature vectors
    features_list = []
    for _, row in df.iterrows():
        feat = build_features(row.to_dict())
        if feat is not None:
            features_list.append({
                "features": feat,
                "salary":   float(row["ConvertedSalary"]),
                "devtype":  str(row["DevType"]).strip(),
            })

    print(f"  Rows with complete features: {len(features_list):,}")

    # Group by primary DevType (use first value if semicolon-separated)
    groups = defaultdict(list)
    for item in features_list:
        primary = item["devtype"].split(";")[0].strip()
        groups[primary].append(item)

    # Add salary percentile within each DevType group
    for dev_type, items in groups.items():
        salaries = np.array([x["salary"] for x in items])
        ranks = salaries.argsort().argsort()  # ordinal rank
        percentiles = ranks / (len(ranks) - 1 + 1e-9)
        for i, item in enumerate(items):
            item["features"][7] = float(percentiles[i])

    # Build triplets
    triplets = []
    skipped  = 0

    for dev_type, items in sorted(groups.items()):
        if len(items) < 50:
            skipped += len(items)
            continue

        salaries = np.array([x["salary"] for x in items])
        p25 = np.percentile(salaries, 25)
        p75 = np.percentile(salaries, 75)

        high_pool = [x for x in items if x["salary"] >= p75]
        low_pool  = [x for x in items if x["salary"] <= p25]

        if not high_pool or not low_pool:
            continue

        # Anchor = mean feature vector of this DevType
        all_feats = np.array([x["features"] for x in items])
        anchor = all_feats.mean(axis=0).tolist()

        n = min(n_per_devtype, len(high_pool), len(low_pool))

        high_idx = rng.choice(len(high_pool), size=n, replace=len(high_pool) < n)
        low_idx  = rng.choice(len(low_pool),  size=n, replace=len(low_pool) < n)

        for hi, lo in zip(high_idx, low_idx):
            triplets.append({
                "anchor":   anchor,
                "positive": high_pool[hi]["features"],
                "negative": low_pool[lo]["features"],
                "devtype":  dev_type,
            })

    print(f"\nGenerated {len(triplets):,} triplets across {len(groups):,} DevType groups")
    print(f"(Skipped {skipped} rows from DevType groups with < 50 members)")

    # Show top DevTypes by triplet count
    devtype_counts = defaultdict(int)
    for t in triplets:
        devtype_counts[t["devtype"]] += 1
    top5 = sorted(devtype_counts.items(), key=lambda x: -x[1])[:5]
    print("\nTop 5 DevTypes by triplet count:")
    for dt, cnt in top5:
        print(f"  {dt[:40]:40s}  {cnt}")

    return triplets


def main():
    parser = argparse.ArgumentParser(description="Generate real ranking triplets from SO survey")
    parser.add_argument("--n-per-devtype", type=int, default=200,
                        help="Max triplets per DevType group (default: 200)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    triplets = generate(n_per_devtype=args.n_per_devtype, seed=args.seed)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(triplets, f, indent=2)

    print(f"\nSaved {len(triplets):,} triplets to {out_path}")
    print("Next: python -m training.train_ranker")


if __name__ == "__main__":
    main()
