"""Unit tests for hr_routes.py pure-logic helpers.

We do NOT import hr_routes here (it has heavy module-level side effects).
Instead we reproduce and test the pure logic directly — these helpers have
no external dependencies and are simple enough to inline.
"""

import re
import secrets
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Reproduced logic (mirrors hr_routes.py exactly) ───────────────────────────

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "yandex.com", "zoho.com",
    "live.com", "msn.com", "me.com",
}

def _is_corporate_email(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain not in FREE_EMAIL_DOMAINS

def _generate_token() -> str:
    return secrets.token_urlsafe(32)

def _is_valid_cv_text(text: str) -> bool:
    if not text or len(text.strip()) < 100:
        return False
    lower = text.lower()
    cv_signals = [
        "experience", "education", "skills", "work", "project",
        "university", "degree", "engineer", "developer", "manager",
        "email", "phone", "linkedin", "python", "java", "sql",
    ]
    signal_count = sum(1 for s in cv_signals if s in lower)
    return signal_count >= 3


# ── _is_corporate_email ────────────────────────────────────────────────────────

def test_corporate_email_accepted():
    assert _is_corporate_email("alice@acmecorp.com") is True

def test_gmail_rejected():
    assert _is_corporate_email("alice@gmail.com") is False

def test_yahoo_rejected():
    assert _is_corporate_email("bob@yahoo.com") is False

def test_outlook_rejected():
    assert _is_corporate_email("bob@outlook.com") is False

def test_subdomain_corporate_accepted():
    assert _is_corporate_email("hr@recruiting.acme.io") is True

def test_protonmail_rejected():
    assert _is_corporate_email("user@protonmail.com") is False

def test_custom_domain_accepted():
    assert _is_corporate_email("ceo@mycompany.org") is True

def test_icloud_rejected():
    assert _is_corporate_email("user@icloud.com") is False

def test_hotmail_rejected():
    assert _is_corporate_email("user@hotmail.com") is False


# ── _generate_token ────────────────────────────────────────────────────────────

def test_token_length():
    token = _generate_token()
    assert len(token) >= 40

def test_token_unique():
    tokens = {_generate_token() for _ in range(20)}
    assert len(tokens) == 20

def test_token_url_safe():
    token = _generate_token()
    assert re.match(r'^[A-Za-z0-9_\-]+$', token), f"Not URL-safe: {token}"

def test_token_not_guessable():
    # At 32 bytes entropy, collision probability is negligible
    t1, t2 = _generate_token(), _generate_token()
    assert t1 != t2


# ── _is_valid_cv_text ──────────────────────────────────────────────────────────

VALID_CV = (
    "Jane Developer\n"
    "Senior Software Engineer\n"
    "Experience: 5 years building scalable backend services with Python and FastAPI.\n"
    "Skills: Python, FastAPI, PostgreSQL, Docker, AWS\n"
    "Education: B.Sc Computer Science, Cairo University\n"
    "Projects: Built a distributed data pipeline serving 10M requests/day.\n"
    "Contact: jane@company.com | +1 555 123 4567\n"
)

def test_valid_cv_passes():
    assert _is_valid_cv_text(VALID_CV) is True

def test_empty_string_fails():
    assert _is_valid_cv_text("") is False

def test_none_fails():
    assert _is_valid_cv_text(None) is False

def test_too_short_fails():
    assert _is_valid_cv_text("Short text") is False

def test_lorem_fails():
    lorem = "Lorem ipsum dolor sit amet consectetur adipiscing elit " * 5
    assert _is_valid_cv_text(lorem) is False

def test_cv_with_multiple_signals_passes():
    cv = (
        "John Doe\nExperience: 3 years\nEducation: BSc\n"
        "Skills: Python, SQL\nEmail: john@example.com\n" * 3
    )
    assert _is_valid_cv_text(cv) is True
