"""
Phase 1 Divergence Test
=======================
Verifies that the AnswerFeatureExtractor produces DIFFERENT feature vectors
for strong, mediocre, and weak answers to the same question.

If features diverge → Phase 1 is working correctly.
If features are identical → something is still hardcoded.

Usage:
    python test_phase1_divergence.py
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

# ── Test Data ──────────────────────────────────────────────────────────
QUESTION = "Can you describe your experience with building RESTful APIs?"

JD_TEXT = """
Senior Backend Engineer — Python/Django
Requirements:
- 3+ years of experience building REST APIs with Django or Flask
- Strong knowledge of PostgreSQL, Redis, and caching strategies
- Experience with microservices architecture and Docker
- CI/CD pipelines, unit testing, and code review practices
- Excellent communication and problem-solving skills
"""

CV_TEXT = """
Software Engineer with 4 years of experience.
Built REST APIs using Django Rest Framework at TechCorp (2020-2024).
Led migration from monolith to microservices architecture.
Skills: Python, Django, PostgreSQL, Redis, Docker, Kubernetes, CI/CD.
"""

# ── Three Answer Quality Levels ──────────────────────────────────────
STRONG_ANSWER = (
    "Absolutely. At TechCorp I built and maintained 12 REST API endpoints serving "
    "2 million requests per day using Django Rest Framework. For example, I designed "
    "the payment processing API that integrated with Stripe — I used serializers for "
    "input validation, implemented rate limiting with Redis, and wrote comprehensive "
    "unit tests with pytest that achieved 94% coverage. I also led the migration from "
    "our monolithic Django app to a microservices architecture using Docker and "
    "Kubernetes, which reduced our deployment time from 45 minutes to under 5 minutes. "
    "Specifically, I developed a shared authentication service that all microservices "
    "consumed via JWT tokens. Therefore, I'm very comfortable with both building and "
    "scaling RESTful systems."
)

MEDIOCRE_ANSWER = (
    "Yes, I have some experience with APIs. I used Django to build a few endpoints "
    "at my previous job. We had a database and I wrote some views that returned JSON. "
    "I think we used PostgreSQL. It was okay, I learned a lot from my team."
)

WEAK_ANSWER = (
    "Um, not really sure. I've heard of REST APIs but I mostly worked on frontend "
    "stuff. I think an API is like, you send a request and get data back? I haven't "
    "really built one from scratch though."
)

CONVERSATION_HISTORY = [
    "AI: Tell me about yourself and your background.",
    "Candidate: I'm a software engineer with experience in Python and web development.",
    "AI: Can you describe your experience with building RESTful APIs?",
]

TONE_CONFIDENT = {"primary_emotion": "confident", "confidence": 0.85}
TONE_NEUTRAL = {"primary_emotion": "neutral", "confidence": 0.5}
TONE_NERVOUS = {"primary_emotion": "nervous", "confidence": 0.3}


def run_test():
    print("=" * 70)
    print("  PHASE 1 DIVERGENCE TEST — AnswerFeatureExtractor")
    print("=" * 70)
    print()

    # Import extractor (tests that it loads without crashing)
    print("Loading AnswerFeatureExtractor...")
    try:
        from models.feature_extractor import AnswerFeatureExtractor
        extractor = AnswerFeatureExtractor()
        print("✅ Extractor loaded successfully")
    except Exception as e:
        print(f"❌ FATAL: Could not load extractor: {e}")
        sys.exit(1)

    feature_names = [
        "skill_match", "relevance", "clarity", "technical_depth",
        "confidence", "consistency", "gaps_inverted", "experience"
    ]

    # ── Run extraction for all 3 answers ─────────────────────────────
    test_cases = [
        ("🟢 STRONG", STRONG_ANSWER, TONE_CONFIDENT),
        ("🟡 MEDIOCRE", MEDIOCRE_ANSWER, TONE_NEUTRAL),
        ("🔴 WEAK", WEAK_ANSWER, TONE_NERVOUS),
    ]

    results = {}

    for label, answer, tone in test_cases:
        features = extractor.extract(
            question=QUESTION,
            answer=answer,
            jd_text=JD_TEXT,
            cv_text=CV_TEXT,
            tone_data=tone,
            conversation_history=CONVERSATION_HISTORY,
        )
        results[label] = features.squeeze(0)  # [8] tensor

    # ── Print Feature Table ──────────────────────────────────────────
    print()
    print(f"{'Feature':<20} {'STRONG':>10} {'MEDIOCRE':>10} {'WEAK':>10} {'Δ(S-W)':>10}")
    print("-" * 62)

    divergent_count = 0

    for i, name in enumerate(feature_names):
        s = results["🟢 STRONG"][i].item()
        m = results["🟡 MEDIOCRE"][i].item()
        w = results["🔴 WEAK"][i].item()
        delta = abs(s - w)

        marker = "✅" if delta > 0.05 else "⚠️"
        if delta > 0.05:
            divergent_count += 1

        print(f"{name:<20} {s:>10.4f} {m:>10.4f} {w:>10.4f} {delta:>10.4f} {marker}")

    print("-" * 62)

    # ── Overall vector distance ──────────────────────────────────────
    strong_vec = results["🟢 STRONG"]
    weak_vec = results["🔴 WEAK"]
    l2_distance = torch.dist(strong_vec, weak_vec, p=2).item()
    cosine_sim = torch.nn.functional.cosine_similarity(
        strong_vec.unsqueeze(0), weak_vec.unsqueeze(0)
    ).item()

    print()
    print(f"  L2 Distance (Strong vs Weak):     {l2_distance:.4f}")
    print(f"  Cosine Similarity (Strong vs Weak): {cosine_sim:.4f}")
    print(f"  Features with meaningful divergence: {divergent_count}/{len(feature_names)}")

    # ── PASS / FAIL ──────────────────────────────────────────────────
    print()
    if divergent_count >= 4 and l2_distance > 0.1:
        print("=" * 70)
        print("  ✅ PHASE 1 PASSED — Feature vectors diverge meaningfully!")
        print("     Different answers produce measurably different inputs to")
        print("     the MultiHeadEvaluator and PerformancePredictor.")
        print("=" * 70)
        return True
    else:
        print("=" * 70)
        print("  ❌ PHASE 1 FAILED — Features are too similar.")
        print("     The neural models still receive nearly identical inputs.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
