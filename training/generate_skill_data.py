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

import sys
sys.stdout.reconfigure(encoding='utf-8')
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
# Paraphrase style tables (Task 4.1 — terminology bias fix)
#
# The same skills expressed in 5 different CV styles and 4 different JD styles.
# Each match pair is generated with a randomly-chosen (cv_style, jd_style) pair,
# so the Siamese network must match on semantic content, not surface phrasing.
# ---------------------------------------------------------------------------

_CV_STYLES = [
    # 0 — formal / technical resume
    lambda langs, fw, db, exp: ". ".join(filter(None, [
        f"Languages: {langs}" if langs else "",
        f"Frameworks: {fw}" if fw else "",
        f"Databases: {db}" if db else "",
        f"Experience: {exp}" if exp else "",
    ])),
    # 1 — first-person narrative
    lambda langs, fw, db, exp: " ".join(filter(None, [
        f"I work primarily with {langs}." if langs else "",
        f"I build applications using {fw}." if fw else "",
        f"I manage data in {db}." if db else "",
        f"Professional coding experience: {exp}." if exp else "",
    ])),
    # 2 — academic / coursework
    lambda langs, fw, db, exp: " ".join(filter(None, [
        f"Studied and applied {langs} in academic and research projects." if langs else "",
        f"Hands-on academic experience with {fw}." if fw else "",
        f"Database coursework covering {db}." if db else "",
    ])),
    # 3 — self-taught / portfolio
    lambda langs, fw, db, exp: " ".join(filter(None, [
        f"Self-taught in {langs}; shipped personal and open-source projects." if langs else "",
        f"Used {fw} in side projects and freelance work." if fw else "",
        f"Deployed with {db} backends." if db else "",
        f"Coding since: {exp}." if exp else "",
    ])),
    # 4 — bullet-point
    lambda langs, fw, db, exp: "\n".join(filter(None, [
        f"- Tech stack: {langs}" if langs else "",
        f"- Frameworks & libraries: {fw}" if fw else "",
        f"- Data stores: {db}" if db else "",
        f"- Years of experience: {exp}" if exp else "",
    ])),
]

_JD_STYLES = [
    # 0 — corporate / formal
    lambda dt, langs, fw, db: " ".join(filter(None, [
        f"Seeking a {dt}.",
        f"Required languages: {langs}." if langs else "",
        f"Preferred frameworks: {fw}." if fw else "",
        f"Database experience: {db}." if db else "",
    ])),
    # 1 — startup / casual
    lambda dt, langs, fw, db: " ".join(filter(None, [
        f"We're looking for a {dt} who knows {langs} cold." if langs
        else f"We're hiring a {dt}.",
        f"You'll ship features with {fw}." if fw else "",
        f"Experience with {db} is a plus." if db else "",
    ])),
    # 2 — academic / research lab
    lambda dt, langs, fw, db: " ".join(filter(None, [
        f"Candidates for the {dt} role should demonstrate proficiency in {langs}."
        if langs else f"Candidates for the {dt} role are sought.",
        f"Familiarity with {fw} is expected." if fw else "",
        f"Knowledge of {db} systems is required." if db else "",
    ])),
    # 3 — requirements list
    lambda dt, langs, fw, db: "\n".join(filter(None, [
        f"Role: {dt}",
        f"Must-have languages: {langs}" if langs else "",
        f"Framework experience: {fw}" if fw else "",
        f"Database skills: {db}" if db else "",
    ])),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join(cell) -> str:
    """Convert a semicolon-separated cell to a comma-separated string, or ''."""
    if pd.isna(cell) or not str(cell).strip():
        return ""
    return ", ".join(p.strip() for p in str(cell).split(";") if p.strip())


def build_cv_skills(row, style: int = 0) -> str:
    """Build a CV skills string using the given phrasing style (0–4)."""
    langs = _join(row.get("LanguageWorkedWith", ""))
    fw    = _join(row.get("FrameworkWorkedWith", ""))
    db    = _join(row.get("DatabaseWorkedWith", ""))
    exp_raw = row.get("YearsCodingProf", "")
    exp = str(exp_raw).strip() if pd.notna(exp_raw) and str(exp_raw).strip() else ""
    return _CV_STYLES[style % len(_CV_STYLES)](langs, fw, db, exp).strip()


def build_jd_requirements(dev_type: str, jd_row, style: int = 0) -> str:
    """Build a JD requirements string using the given phrasing style (0–3)."""
    langs = _join(jd_row.get("LanguageWorkedWith", ""))
    fw    = _join(jd_row.get("FrameworkWorkedWith", ""))
    db    = _join(jd_row.get("DatabaseWorkedWith", ""))
    return _JD_STYLES[style % len(_JD_STYLES)](dev_type, langs, fw, db).strip()


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
    n_cv_styles = len(_CV_STYLES)
    n_jd_styles = len(_JD_STYLES)

    # --- Match pairs (with random phrasing style per pair) ---
    # Half the budget uses matching CV+JD styles; the other half deliberately
    # mismatches styles (e.g. academic CV paired with startup JD for same skills)
    # to force the network to match on semantics, not surface form.
    print(f"\nGenerating {n_match} matching pairs (cross-phrasing enabled) ...")
    match_pool = df.sample(n=min(n_match * 3, len(df)), random_state=seed)
    count = 0
    for _, row in match_pool.iterrows():
        if count >= n_match:
            break
        cv_style = random.randint(0, n_cv_styles - 1)
        jd_style = random.randint(0, n_jd_styles - 1)
        cv = build_cv_skills(row, style=cv_style)
        if not cv:
            skipped += 1
            continue
        dev_type = row["DevTypePrimary"]
        group = devtype_groups.get(dev_type, df)
        jd_row = group.sample(1, random_state=random.randint(0, 99999)).iloc[0]
        jd = build_jd_requirements(dev_type, jd_row, style=jd_style)
        samples.append({
            "cv_skills":       cv,
            "jd_requirements": jd,
            "is_match":        True,
            "domain":          dev_type,
            "cv_style":        cv_style,
            "jd_style":        jd_style,
        })
        count += 1
        if count % 50 == 0:
            print(f"  {count}/{n_match} match pairs")

    # --- Mismatch pairs (also randomized styles to avoid style-match shortcuts) ---
    print(f"\nGenerating {n_mismatch} mismatch pairs ...")
    mismatch_pool = df.sample(n=min(n_mismatch * 3, len(df)), random_state=seed + 1)
    count = 0
    for _, row in mismatch_pool.iterrows():
        if count >= n_mismatch:
            break
        cv_style = random.randint(0, n_cv_styles - 1)
        jd_style = random.randint(0, n_jd_styles - 1)
        cv = build_cv_skills(row, style=cv_style)
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
        jd = build_jd_requirements(other_type, jd_row, style=jd_style)
        samples.append({
            "cv_skills":       cv,
            "jd_requirements": jd,
            "is_match":        False,
            "domain":          other_type,
            "cv_style":        cv_style,
            "jd_style":        jd_style,
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
