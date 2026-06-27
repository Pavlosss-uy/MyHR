"""Unit tests for cv_parser.py — pure functions, no I/O, no mocking needed."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv_parser import (
    extract_email,
    extract_phone,
    extract_candidate_name,
    extract_skills_keyword,
    compute_match_details,
    compute_rubric_score,
)


# ── extract_email ──────────────────────────────────────────────────────────────

def test_email_standard():
    assert extract_email("Contact: john.doe@company.com") == "john.doe@company.com"

def test_email_with_plus():
    assert extract_email("john+filter@example.org") == "john+filter@example.org"

def test_email_empty():
    assert extract_email("") is None

def test_email_none_input():
    assert extract_email(None) is None

def test_email_no_email():
    assert extract_email("No email here at all") is None

def test_email_picks_first():
    result = extract_email("a@first.com and b@second.com")
    assert result == "a@first.com"


# ── extract_phone ──────────────────────────────────────────────────────────────

def test_phone_us_format():
    result = extract_phone("Call me at (555) 123-4567")
    assert result is not None
    assert "123" in result

def test_phone_international():
    result = extract_phone("+1 800 555 1234")
    assert result is not None

def test_phone_empty():
    assert extract_phone("") is None

def test_phone_none():
    assert extract_phone(None) is None

def test_phone_no_number():
    assert extract_phone("No phone number in this text") is None


# ── extract_candidate_name ─────────────────────────────────────────────────────

def test_name_labeled():
    cv = "Name: John Smith\nExperience: 5 years"
    result = extract_candidate_name(cv)
    assert "John" in result and "Smith" in result

def test_name_standalone_top():
    cv = "Jane Developer\nSenior Engineer at Acme Corp"
    assert extract_candidate_name(cv) == "Jane Developer"

def test_name_from_filename_fallback():
    result = extract_candidate_name("", filename="john_smith_cv.pdf")
    assert "John" in result and "Smith" in result

def test_name_strips_cv_from_filename():
    result = extract_candidate_name("", filename="jane_doe_resume.pdf")
    assert "resume" not in result.lower() or "Jane" in result

def test_name_default_fallback():
    result = extract_candidate_name("", filename="")
    assert result == "Candidate"


# ── extract_skills_keyword ─────────────────────────────────────────────────────

def test_skills_basic():
    skills = extract_skills_keyword("Proficient in Python, FastAPI, and PostgreSQL")
    lower = [s.lower() for s in skills]
    assert "python" in lower
    assert "fastapi" in lower
    assert "postgresql" in lower

def test_skills_empty():
    assert extract_skills_keyword("") == []

def test_skills_none():
    assert extract_skills_keyword(None) == []

def test_skills_no_duplicates():
    skills = extract_skills_keyword("Python Python python")
    assert skills.count(next(s for s in skills if s.lower() == "python")) == 1

def test_skills_case_insensitive():
    skills = extract_skills_keyword("PYTHON REACT DOCKER")
    lower = [s.lower() for s in skills]
    assert "python" in lower
    assert "react" in lower
    assert "docker" in lower

def test_skills_multi_word():
    skills = extract_skills_keyword("Expert in machine learning and deep learning")
    lower = [s.lower() for s in skills]
    assert "machine learning" in lower or "deep learning" in lower


# ── compute_match_details ──────────────────────────────────────────────────────

def test_match_details_perfect():
    result = compute_match_details(["Python", "React"], ["Python", "React"])
    assert result["matchPercent"] == 100.0
    assert len(result["matched"]) == 2
    assert result["missing"] == []

def test_match_details_no_overlap():
    result = compute_match_details(["Go", "Rust"], ["Python", "React"])
    assert result["matchPercent"] == 0.0
    assert len(result["missing"]) == 2

def test_match_details_partial():
    result = compute_match_details(["Python", "Docker"], ["Python", "React"])
    assert result["matchPercent"] == 50.0

def test_match_details_extra_skills():
    result = compute_match_details(["Python", "Go", "Rust"], ["Python"])
    assert len(result["extra"]) == 2

def test_match_details_case_insensitive():
    result = compute_match_details(["python"], ["Python"])
    assert result["matchPercent"] == 100.0

def test_match_details_empty_jd():
    result = compute_match_details(["Python"], [])
    assert result["matchPercent"] == 0.0


# ── compute_rubric_score ───────────────────────────────────────────────────────

STRONG_CV = """
John Smith
Senior Software Engineer

Experience:
2018 - 2023: Senior Backend Engineer at TechCorp
Architected and deployed scalable microservices using Python, FastAPI, Docker, Kubernetes.
Designed distributed systems with Redis caching and PostgreSQL.
Led migration from monolith to microservices, reducing latency by 40%.

2015 - 2018: Software Engineer at StartupX
Built REST APIs with Django and deployed on AWS.

Skills: Python, FastAPI, Docker, Kubernetes, Redis, PostgreSQL, AWS, CI/CD
Education: B.Sc Computer Science
Certified AWS Solutions Architect
"""

WEAK_CV = """
Bob Jones
I know some programming and did some projects in college.
Used Microsoft Word and Excel at my internship.
"""

JD_TEXT = """
Senior Backend Engineer
Requirements: Python, FastAPI, Docker, Kubernetes, PostgreSQL, AWS
Experience: 5+ years backend development
Full-stack knowledge preferred.
"""

JD_SKILLS = ["python", "fastapi", "docker", "kubernetes", "postgresql", "aws"]


def test_rubric_strong_cv_scores_high():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, JD_SKILLS)
    assert result["total"] >= 70, f"Expected ≥70, got {result['total']}"

def test_rubric_weak_cv_scores_low():
    result = compute_rubric_score(WEAK_CV, JD_TEXT, JD_SKILLS)
    assert result["total"] <= 50, f"Expected ≤50, got {result['total']}"

def test_rubric_returns_required_keys():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, JD_SKILLS)
    for key in ("total", "breakdown", "rawTotal", "koApplied", "strengths", "gaps", "experienceTier"):
        assert key in result, f"Missing key: {key}"

def test_rubric_breakdown_axes():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, JD_SKILLS)
    bd = result["breakdown"]
    for axis in ("techStack", "architecture", "experience", "preferred"):
        assert axis in bd
        assert 0 <= bd[axis] <= 40

def test_rubric_score_clamped_0_100():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, JD_SKILLS)
    assert 0 <= result["total"] <= 100

def test_rubric_no_skills_jd_ko():
    no_match_cv = "I play video games and watch movies."
    result = compute_rubric_score(no_match_cv, JD_TEXT, JD_SKILLS)
    assert result["koApplied"] == "framework_cap"
    assert result["total"] <= 40

def test_rubric_experience_tier_senior():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, JD_SKILLS)
    assert result["experienceTier"] == "senior"

def test_rubric_experience_tier_junior():
    result = compute_rubric_score(WEAK_CV, JD_TEXT, JD_SKILLS)
    assert result["experienceTier"] == "junior"

def test_rubric_preextracted_skills_respected():
    result = compute_rubric_score(WEAK_CV, JD_TEXT, JD_SKILLS, cv_skills=["python", "fastapi"])
    assert result["breakdown"]["techStack"] > 0

def test_rubric_empty_jd_skills():
    result = compute_rubric_score(STRONG_CV, JD_TEXT, [])
    assert result["total"] >= 0
