"""
Generate 500+ realistic CV/JD skill pairs for training the Skill Matcher.

Uses the Groq API (already configured in this project) to produce diverse,
domain-specific pairs labelled as match (is_match=true) or mismatch (is_match=false).

Usage:
    python -m training.generate_skill_data               # full run: 250+250 pairs
    python -m training.generate_skill_data --test        # quick test: 5+5 pairs
"""

import json
import os
import time
import argparse
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DOMAINS = [
    "Backend Python",
    "Frontend React",
    "Data Science",
    "DevOps / Cloud Infrastructure",
    "Mobile iOS (Swift)",
    "Security Engineering",
    "ML Engineering",
    "Full Stack (MERN)",
    "Game Development (Unity/C#)",
    "Embedded Systems (C/C++)",
    "Cloud Architecture (AWS)",
    "Database Engineering (PostgreSQL/NoSQL)",
]

PROMPT_MATCH = """\
Generate a realistic CV skills section and a matching Job Description requirements section for the domain: {domain}.

Rules:
- The CV should convincingly qualify for the JD (genuine match).
- Use real-sounding technologies, years of experience, and project types.
- CV skills section: 3-5 lines, comma-separated technologies and short phrases.
- JD requirements section: 3-5 bullet-point requirements.

Return ONLY valid JSON (no markdown, no extra text):
{{"cv_skills": "...", "jd_requirements": "...", "is_match": true, "domain": "{domain}"}}"""

PROMPT_MISMATCH = """\
Generate a realistic CV skills section (domain: {cv_domain}) and a Job Description requirements section (domain: {jd_domain}).

Rules:
- The candidate clearly does NOT qualify — their skills target a completely different tech stack.
- Both should look realistic and professional in isolation.
- CV skills section: 3-5 lines, comma-separated technologies and short phrases.
- JD requirements section: 3-5 bullet-point requirements.

Return ONLY valid JSON (no markdown, no extra text):
{{"cv_skills": "...", "jd_requirements": "...", "is_match": false, "domain": "{jd_domain}"}}"""


def call_groq(client, prompt, retries=3):
    """Call Groq API with retry on failure. Returns parsed dict or None."""
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=512,
            )
            content = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                )

            return json.loads(content)

        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt+1}): {e}")
        except Exception as e:
            print(f"  API error (attempt {attempt+1}): {e}")
            time.sleep(2)

    return None


def generate_dataset(n_match=250, n_mismatch=250, output_path="data/skill_pairs.json"):
    client  = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    samples = []
    skipped = 0

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    # --- Matching pairs ---
    print(f"\nGenerating {n_match} matching pairs...")
    for i in range(n_match):
        domain = DOMAINS[i % len(DOMAINS)]
        prompt = PROMPT_MATCH.format(domain=domain)
        sample = call_groq(client, prompt)
        if sample and "cv_skills" in sample and "jd_requirements" in sample:
            samples.append(sample)
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{n_match} match pairs generated ({skipped} skipped)")
        else:
            skipped += 1
        time.sleep(0.3)  # gentle rate limiting

    # --- Mismatched pairs ---
    print(f"\nGenerating {n_mismatch} mismatched pairs...")
    for i in range(n_mismatch):
        cv_domain  = DOMAINS[i % len(DOMAINS)]
        # Offset by a prime to guarantee domain difference
        jd_domain  = DOMAINS[(i + 5) % len(DOMAINS)]
        prompt     = PROMPT_MISMATCH.format(cv_domain=cv_domain, jd_domain=jd_domain)
        sample     = call_groq(client, prompt)
        if sample and "cv_skills" in sample and "jd_requirements" in sample:
            samples.append(sample)
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{n_mismatch} mismatch pairs generated ({skipped} skipped)")
        else:
            skipped += 1
        time.sleep(0.3)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Generated {len(samples)} samples ({skipped} skipped) → {output_path}")
    match_count    = sum(1 for s in samples if s.get("is_match"))
    mismatch_count = len(samples) - match_count
    print(f"  Matches: {match_count}  |  Mismatches: {mismatch_count}")

    return samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate skill pair training data")
    parser.add_argument(
        "--test", action="store_true",
        help="Quick test run: generate only 5 match + 5 mismatch pairs"
    )
    parser.add_argument(
        "--n-match", type=int, default=250,
        help="Number of matching pairs to generate (default: 250)"
    )
    parser.add_argument(
        "--n-mismatch", type=int, default=250,
        help="Number of mismatched pairs to generate (default: 250)"
    )
    parser.add_argument(
        "--output", type=str, default="data/skill_pairs.json",
        help="Output JSON file path (default: data/skill_pairs.json)"
    )
    args = parser.parse_args()

    if args.test:
        print("Running in TEST mode (5 + 5 pairs)...")
        generate_dataset(n_match=5, n_mismatch=5, output_path=args.output)
    else:
        generate_dataset(
            n_match=args.n_match,
            n_mismatch=args.n_mismatch,
            output_path=args.output,
        )
