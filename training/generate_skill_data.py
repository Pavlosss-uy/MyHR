"""
Generate CV/JD skill pairs for training the Skill Matcher.

Uses the Stack Overflow 2018 Developer Survey (data/archive/survey_results_public.csv)
— 76,865 real developer profiles — instead of LLM API calls.
Runs in under 5 seconds, no API key required.

Match pairs  (is_match=True):
    CV built from a developer's real tech stack.
    JD built from the same role (DevType) using a different developer's stack.

Mismatch pairs (is_match=False):
    CV built from a developer's real tech stack.
    JD built from a completely different DevType using another developer's stack.

Output format (same as before — train_skill_matcher.py needs no changes):
    [{"cv_skills": "...", "jd_requirements": "...", "is_match": true/false, "domain": "..."}, ...]

Usage:
    python -m training.generate_skill_data               # 250 + 250 pairs
    python -m training.generate_skill_data --test        # 10 + 10 pairs
    python -m training.generate_skill_data --n-match 100 --n-mismatch 100
"""

import json
import os
import argparse
import random
import pandas as pd


SURVEY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "archive", "survey_results_public.csv"
)

OUTPUT_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "skill_pairs.json"
)

SKILL_COLS = [
    "LanguageWorkedWith",
    "FrameworkWorkedWith",
    "DatabaseWorkedWith",
    "PlatformWorkedWith",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join(cell) -> str:
    """Convert a semicolon-separated cell to a comma-separated string, or ''."""
    if pd.isna(cell) or not str(cell).strip():
        return ""
    return ", ".join(p.strip() for p in str(cell).split(";") if p.strip())


def build_cv_skills(row) -> str:
    """
    Build a readable CV skills string from a survey row.
    e.g. "Languages: Python, JavaScript. Frameworks: Django. Databases: PostgreSQL. Experience: 3-5 years"
    """
    parts = []
    langs = _join(row.get("LanguageWorkedWith", ""))
    if langs:
        parts.append(f"Languages: {langs}")

    fw = _join(row.get("FrameworkWorkedWith", ""))
    if fw:
        parts.append(f"Frameworks: {fw}")

    db = _join(row.get("DatabaseWorkedWith", ""))
    if db:
        parts.append(f"Databases: {db}")

    plat = _join(row.get("PlatformWorkedWith", ""))
    if plat:
        parts.append(f"Platforms: {plat}")

    exp = row.get("YearsCodingProf", "")
    if pd.notna(exp) and str(exp).strip():
        parts.append(f"Experience: {str(exp).strip()}")

    return ". ".join(parts)


def build_jd_requirements(dev_type: str, jd_row) -> str:
    """
    Build a realistic JD requirements string from a DevType label and
    a sample developer row that represents the role's typical tech stack.
    e.g. "Seeking a Full-stack developer. Required: Python, JavaScript. Preferred frameworks: Django, React."
    """
    langs = _join(jd_row.get("LanguageWorkedWith", ""))
    fw    = _join(jd_row.get("FrameworkWorkedWith", ""))
    db    = _join(jd_row.get("DatabaseWorkedWith", ""))

    parts = [f"Seeking a {dev_type}."]
    if langs:
        parts.append(f"Required languages: {langs}.")
    if fw:
        parts.append(f"Preferred frameworks: {fw}.")
    if db:
        parts.append(f"Database experience: {db}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main dataset builder
# ---------------------------------------------------------------------------

def generate_dataset(n_match: int = 250, n_mismatch: int = 250,
                     output_path: str = OUTPUT_DEFAULT, seed: int = 42):
    random.seed(seed)

    print(f"Loading survey data from {SURVEY_PATH} ...")
    df = pd.read_csv(SURVEY_PATH, low_memory=False)

    # Keep rows that have at least one skill column and a DevType
    df = df.dropna(subset=["LanguageWorkedWith", "DevType"]).copy()
    print(f"  Usable rows: {len(df):,}")

    # Primary DevType = first role listed
    df["DevTypePrimary"] = df["DevType"].apply(
        lambda x: str(x).split(";")[0].strip()
    )

    # Build per-DevType groups (only types with >= 10 members for JD sampling)
    devtype_groups = {
        dt: grp.reset_index(drop=True)
        for dt, grp in df.groupby("DevTypePrimary")
        if len(grp) >= 10
    }
    devtypes = list(devtype_groups.keys())
    print(f"  Distinct DevTypes with >=10 members: {len(devtypes)}")

    samples = []
    skipped = 0

    # --- Match pairs ---
    print(f"\nGenerating {n_match} matching pairs ...")
    match_pool = df.sample(n=min(n_match * 2, len(df)), random_state=seed)
    count = 0
    for _, row in match_pool.iterrows():
        if count >= n_match:
            break
        cv = build_cv_skills(row)
        if not cv:
            skipped += 1
            continue
        dev_type = row["DevTypePrimary"]
        group = devtype_groups.get(dev_type, df)
        jd_row = group.sample(1, random_state=random.randint(0, 99999)).iloc[0]
        jd = build_jd_requirements(dev_type, jd_row)
        samples.append({
            "cv_skills":       cv,
            "jd_requirements": jd,
            "is_match":        True,
            "domain":          dev_type,
        })
        count += 1
        if count % 50 == 0:
            print(f"  {count}/{n_match} match pairs")

    # --- Mismatch pairs ---
    print(f"\nGenerating {n_mismatch} mismatch pairs ...")
    mismatch_pool = df.sample(n=min(n_mismatch * 2, len(df)), random_state=seed + 1)
    count = 0
    for _, row in mismatch_pool.iterrows():
        if count >= n_mismatch:
            break
        cv = build_cv_skills(row)
        if not cv:
            skipped += 1
            continue
        dev_type = row["DevTypePrimary"]
        other_types = [d for d in devtypes if d != dev_type]
        if not other_types:
            skipped += 1
            continue
        other_type = random.choice(other_types)
        jd_row = devtype_groups[other_type].sample(1, random_state=random.randint(0, 99999)).iloc[0]
        jd = build_jd_requirements(other_type, jd_row)
        samples.append({
            "cv_skills":       cv,
            "jd_requirements": jd,
            "is_match":        False,
            "domain":          other_type,
        })
        count += 1
        if count % 50 == 0:
            print(f"  {count}/{n_mismatch} mismatch pairs")

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    match_count    = sum(1 for s in samples if s["is_match"])
    mismatch_count = len(samples) - match_count
    print(f"\nDone! {len(samples)} samples saved -> {output_path}")
    print(f"  Matches: {match_count}  |  Mismatches: {mismatch_count}  |  Skipped: {skipped}")
    return samples


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate skill pair data from SO 2018 survey")
    parser.add_argument("--test",      action="store_true",
                        help="Quick test: 10 match + 10 mismatch pairs")
    parser.add_argument("--n-match",   type=int, default=250)
    parser.add_argument("--n-mismatch",type=int, default=250)
    parser.add_argument("--output",    type=str, default=OUTPUT_DEFAULT)
    args = parser.parse_args()

    if args.test:
        print("Running in TEST mode (10 + 10 pairs)...")
        generate_dataset(n_match=10, n_mismatch=10, output_path=args.output)
    else:
        generate_dataset(
            n_match=args.n_match,
            n_mismatch=args.n_mismatch,
            output_path=args.output,
        )
