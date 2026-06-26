"""
CV text extraction and entity parsing module.
Handles PDF and DOCX file formats, extracts candidate contact info and skills.
"""
import io
import re
from typing import List, Optional, Tuple

import PyPDF2


# ---------- Text extraction ----------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text.strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document as DocxDocument
    except ImportError:
        raise ImportError(
            "python-docx is required for DOCX parsing. "
            "Install it with: pip install python-docx"
        )

    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """
    Extract text from a file based on its content type.
    Supports PDF and DOCX.
    """
    ct = (content_type or "").lower()

    if "pdf" in ct:
        return extract_text_from_pdf(file_bytes)
    elif "docx" in ct or "wordprocessingml" in ct:
        return extract_text_from_docx(file_bytes)
    elif "doc" in ct:
        # Legacy .doc format — attempt PDF extraction as fallback
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            raise ValueError(
                "Legacy .doc format is not supported. Please upload PDF or DOCX."
            )
    else:
        # Try PDF first, then DOCX
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            try:
                return extract_text_from_docx(file_bytes)
            except Exception:
                raise ValueError(f"Unsupported file type: {content_type}")


# ---------- Entity extraction ----------

def extract_email(cv_text: str) -> Optional[str]:
    """Extract the first email address from CV text."""
    if not cv_text:
        return None

    # Match standard email patterns
    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, cv_text)
    return match.group(0) if match else None


def extract_phone(cv_text: str) -> Optional[str]:
    """Extract the first phone number from CV text."""
    if not cv_text:
        return None

    # International and domestic phone patterns
    patterns = [
        r'\+?\d{1,3}[\s\-.]?\(?\d{1,4}\)?[\s\-.]?\d{1,4}[\s\-.]?\d{1,9}',
        r'\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}',
    ]

    for pattern in patterns:
        match = re.search(pattern, cv_text)
        if match:
            phone = match.group(0).strip()
            # Ensure it looks like a phone number (at least 7 digits)
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 7:
                return phone
    return None


def extract_candidate_name(cv_text: str, filename: str = "") -> str:
    """
    Extract candidate name from CV text or filename.
    Reuses the name-extraction logic from server.py.
    """
    if cv_text:
        first_block = cv_text[:600].strip()

        # Look for a labeled name field
        label_match = re.search(
            r"(?i)(?:full\s+)?name\s*[:\-]\s*([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){1,2})",
            first_block,
        )
        if label_match:
            return label_match.group(1).strip()

        # Look for standalone name at the top of the document
        standalone = re.search(
            r"^([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){1,2})\s*$",
            first_block,
            re.MULTILINE,
        )
        if standalone:
            candidate = standalone.group(1).strip()
            noise = {
                "curriculum", "vitae", "resume", "profile", "summary",
                "contact", "address", "objective", "education", "experience",
            }
            if candidate.split()[0].lower() not in noise:
                return candidate

    # Fall back to filename
    if filename:
        name = re.sub(r"\.[^.]+$", "", filename)
        name = re.sub(r"[_\-]+", " ", name)
        name = re.sub(
            r"\b(?:cv|resume|curriculum|vitae|application|candidate|profile)\b",
            "", name, flags=re.IGNORECASE,
        )
        name = " ".join(name.split()).strip()
        if len(name.split()) >= 2:
            return name.title()

    return "Candidate"


# ---------- Skill extraction ----------

# Common technical skills to detect via keyword matching (fast, no LLM needed)
COMMON_SKILLS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
    "react", "angular", "vue", "next.js", "node.js", "express", "django",
    "flask", "fastapi", "spring", "rails",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
    "ci/cd", "git", "linux", "nginx",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "langchain", "langgraph", "openai", "llm", "rag",
    "graphql", "rest api", "microservices", "serverless",
    "agile", "scrum", "jira", "confluence",
    "html", "css", "tailwind", "sass",
    "figma", "sketch", "adobe xd",
    "power bi", "tableau", "data analysis", "data engineering",
    "spark", "hadoop", "airflow", "kafka", "rabbitmq",
    "oauth", "jwt", "security", "penetration testing",
    "flutter", "react native", "ios", "android",
    "blockchain", "web3", "solidity",
]

# Pre-compiled regex: single alternation of all skills with word boundaries.
# Skills are sorted longest-first so that multi-word skills (e.g. "machine learning")
# are matched before shorter substrings (e.g. "machine").
_SKILLS_RE = re.compile(
    r'\b(?:' +
    '|'.join(re.escape(s) for s in sorted(COMMON_SKILLS, key=len, reverse=True)) +
    r')\b',
    re.IGNORECASE,
)

# Lookup table for canonical display casing (short skills → UPPER, rest → Title)
_SKILLS_DISPLAY: dict[str, str] = {
    s: (s.upper() if len(s) <= 2 else s.title()) for s in COMMON_SKILLS
}


def extract_skills_keyword(text: str) -> list[str]:
    """
    Extract skills from text using keyword matching.
    Fast, deterministic, no API calls.

    Uses a single pre-compiled regex (_SKILLS_RE) instead of
    iterating over every skill individually.
    """
    if not text:
        return []

    seen: set[str] = set()
    found: list[str] = []
    for m in _SKILLS_RE.finditer(text):
        key = m.group(0).lower()
        if key not in seen:
            seen.add(key)
            found.append(_SKILLS_DISPLAY.get(key, key.title()))
    return found


def compute_match_details(
    cv_skills: list[str], jd_skills: list[str]
) -> dict:
    """
    Compare candidate skills against job requirements.
    Returns matched, missing, and extra skills.
    """
    cv_set = {s.lower() for s in cv_skills}
    jd_set = {s.lower() for s in jd_skills}

    matched = sorted(cv_set & jd_set)
    missing = sorted(jd_set - cv_set)
    extra = sorted(cv_set - jd_set)

    # Restore original casing from input lists
    cv_map = {s.lower(): s for s in cv_skills}
    jd_map = {s.lower(): s for s in jd_skills}
    all_map = {**jd_map, **cv_map}

    return {
        "matched": [all_map.get(s, s.title()) for s in matched],
        "missing": [jd_map.get(s, s.title()) for s in missing],
        "extra": [cv_map.get(s, s.title()) for s in extra],
        "matchPercent": round(
            (len(matched) / max(len(jd_set), 1)) * 100, 1
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  100-Point Structured Rubric Scorer
#  Axes: Tech Stack (40) · Architecture (25) · Experience (20) · Preferred (15)
#
#  Design principles:
#   - Tech uses pre-extracted skill lists (reliable, no raw-text guessing)
#   - Architecture has a non-zero base so candidates aren't punished for not
#     using enterprise buzzwords in a junior/startup JD
#   - Experience uses multiple date formats and defaults to "junior" rather than
#     "unknown" when signals are ambiguous
#   - KO rules only fire on unambiguous disqualifying conditions
# ─────────────────────────────────────────────────────────────────────────────

# Depth/complexity signals found in technical CVs (not overly enterprise-specific)
_ARCH_SIGNALS: List[str] = [
    "microservices", "kubernetes", "docker", "ci/cd", "pipeline",
    "distributed", "kafka", "message queue", "rabbitmq", "graphql",
    "grpc", "rest api", "system design", "data warehouse", "etl",
    "real-time", "streaming", "terraform", "infrastructure", "cloud",
    "high availability", "scalable", "load balancer", "caching", "redis",
    "elasticsearch", "monitoring", "observability", "sre", "devops",
]

_DEPTH_VERBS: List[str] = [
    "architected", "designed", "led", "managed", "built", "launched",
    "delivered", "optimized", "migrated", "scaled", "developed", "implemented",
    "deployed", "integrated", "refactored", "established",
]

_BONUS_INDICATORS: List[str] = [
    "certified", "certification", "open source", "open-source",
    "kaggle", "hackathon", "published", "conference", "speaker",
    "agile", "scrum", "startup", "patent", "research",
]

# Multiple date-range patterns to handle varied CV formats
_DATE_RANGE_PATTERNS: List[re.Pattern] = [
    # "2020 - 2023" or "2020 – Present"
    re.compile(r'\b(20\d{2})\s*[-–—]\s*(20\d{2}|present|current|now)\b', re.IGNORECASE),
    # "Jan 2020 - Dec 2022" or "March 2021 – Present"
    re.compile(
        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+20\d{2}'
        r'\s*[-–—]\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+20\d{2}',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+20\d{2}'
        r'\s*[-–—]\s*(?:present|current|now)\b',
        re.IGNORECASE,
    ),
    # "Q1 2021 – Q3 2022"
    re.compile(r'\bQ[1-4]\s+20\d{2}\s*[-–—]\s*(?:Q[1-4]\s+20\d{2}|present|current)\b', re.IGNORECASE),
]

_EXPLICIT_YEARS_RE = re.compile(
    r'\b(\d+)\+?\s+years?\s+(?:of\s+)?(?:experience|exp|work)\b', re.IGNORECASE
)
_SENIORITY_RE = re.compile(
    r'\b(?:senior|sr\.?|lead|principal|staff|head\s+of|director|vp|chief|manager|architect)\b',
    re.IGNORECASE,
)
_INTERN_RE = re.compile(r'\b(?:intern|internship|co.?op|trainee|apprentice)\b', re.IGNORECASE)


def _count_positions(cv_text: str) -> int:
    """Count distinct employment periods across all date-range formats."""
    matches = set()
    for pattern in _DATE_RANGE_PATTERNS:
        for m in pattern.finditer(cv_text):
            matches.add(m.start())  # deduplicate by position
    return len(matches)


def _score_tech_stack(
    cv_skills: List[str], jd_skills: List[str]
) -> Tuple[int, List[str], List[str]]:
    """
    Core Tech Stack Alignment — 0 to 40 points.

    Uses pre-extracted skill lists (already filtered through COMMON_SKILLS)
    so matching is accurate and symmetric on both sides.

    Bands:
      36-40 : ≥ 75 % of JD skills present  (strong alignment)
      22-35 : 40-74 % match                 (solid partial)
      12-21 : 15-39 % match                 (some overlap)
       0-11 : < 15 % match                  (missing ecosystem)
    """
    if not jd_skills:
        return 20, [], []

    cv_set = {s.lower() for s in cv_skills}
    jd_set = {s.lower() for s in jd_skills}

    matched = sorted(cv_set & jd_set)
    missing = sorted(jd_set - cv_set)
    ratio   = len(matched) / len(jd_set)

    if ratio >= 0.75:
        score = int(36 + 4 * min((ratio - 0.75) / 0.25, 1.0))
    elif ratio >= 0.40:
        score = int(22 + ((ratio - 0.40) / 0.35) * 13)
    elif ratio >= 0.15:
        score = int(12 + ((ratio - 0.15) / 0.25) * 9)
    else:
        score = int((ratio / 0.15) * 11)

    return min(score, 40), matched, missing


def _score_architecture(cv_lower: str, jd_lower: str) -> Tuple[int, List[str]]:
    """
    Architectural Project Depth — 0 to 25 points.

    Base of 10 ensures candidates aren't punished for working in a domain
    where enterprise buzzwords don't naturally appear (e.g. frontend, mobile).
    Additional points come from architecture signals and execution-quality verbs.
    """
    cv_arch    = [s for s in _ARCH_SIGNALS if s in cv_lower]
    depth_hits = sum(1 for v in _DEPTH_VERBS if v in cv_lower)

    # JD-alignment bonus: extra credit when CV signals match what JD asks for
    jd_arch  = [s for s in _ARCH_SIGNALS if s in jd_lower]
    jd_align = len([a for a in cv_arch if a in jd_arch]) if jd_arch else 0

    arch_bonus  = min(len(cv_arch) / 4.0, 1.0) * 10   # up to +10 for 4+ signals
    depth_bonus = min(depth_hits / 4.0, 1.0) * 4       # up to +4 for 4+ verbs
    align_bonus = min(jd_align / max(len(jd_arch), 1), 1.0) * 1  # up to +1

    score = int(10 + arch_bonus + depth_bonus + align_bonus)
    return min(score, 25), cv_arch[:5]


def _score_experience(cv_text: str, cv_lower: str, jd_lower: str) -> Tuple[int, str]:
    """
    Professional Experience — 0 to 20 points.

    Detects date ranges across multiple common CV formats, explicit year
    claims, and seniority title keywords. Defaults to 'junior' when evidence
    is sparse (rather than the harsher 'student/unknown' from the old code).
    """
    n_positions   = _count_positions(cv_text)
    is_senior     = bool(_SENIORITY_RE.search(cv_lower))
    has_intern    = bool(_INTERN_RE.search(cv_lower))

    explicit_years_list = [int(m.group(1)) for m in _EXPLICIT_YEARS_RE.finditer(cv_text)]
    total_years = max(explicit_years_list, default=0)

    # Tier → base score
    if is_senior or total_years >= 5:
        tier, base = "senior", 16
    elif total_years >= 2 or n_positions >= 2:
        tier, base = "mid", 12
    elif total_years >= 1 or n_positions >= 1 or (has_intern and n_positions == 0):
        tier, base = "junior", 8
    else:
        # Even without date signals: ambiguous but give benefit of the doubt
        tier, base = "junior", 7

    # +2 if JD seniority level matches CV seniority level
    jd_senior = bool(re.search(r'\b(?:senior|lead|sr\.?|5\+|6\+|7\+\s+years?)\b', jd_lower, re.IGNORECASE))
    if jd_senior == is_senior:
        base += 2

    # Role-type alignment bonus
    jd_roles = set(re.findall(r'\b(?:engineer|developer|architect|scientist|analyst|manager|designer)\b', jd_lower))
    cv_roles  = set(re.findall(r'\b(?:engineer|developer|architect|scientist|analyst|manager|designer)\b', cv_lower))
    if jd_roles & cv_roles:
        base += 1

    return min(base, 20), tier


def _score_preferred(
    cv_lower: str, cv_skills: List[str], jd_skills: List[str]
) -> Tuple[int, List[str]]:
    """
    Preferred Qualifications — 0 to 15 points.

    Base of 5 rewards any candidate who submitted a real CV.
    Additional points come from:
      - Bonus qualifications (certifications, OS contributions, etc.)
      - Breadth: extra CV skills that happen to overlap with the JD
        (signals a broader toolbox beyond the core required set)
    """
    cv_set = {s.lower() for s in cv_skills}
    jd_set = {s.lower() for s in jd_skills}
    breadth_overlap = cv_set & jd_set

    bonus_hits     = [b for b in _BONUS_INDICATORS if b in cv_lower]
    bonus_score    = min(len(bonus_hits) / 2.0, 1.0) * 5   # up to +5 for 2+ hits
    breadth_score  = min(len(breadth_overlap) / max(len(jd_set), 1), 1.0) * 5  # up to +5

    score = int(5 + bonus_score + breadth_score)
    return min(score, 15), bonus_hits[:3]


def _apply_ko_rules(
    raw: int,
    tech_matched: List[str],
    jd_skills: List[str],
    cv_lower: str,
    jd_lower: str,
) -> Tuple[int, Optional[str]]:
    """
    Knockout caps — only applied when the condition is unambiguous.

    framework_cap     : Zero skill overlap AND JD has at least 5 extractable
                        skills to judge against → genuine missing ecosystem.
    halfstack_penalty : JD explicitly says "full-stack" AND candidate is
                        provably missing an entire side (backend OR frontend),
                        not merely light on it.
    """
    # Framework cap: truly zero matches against a non-trivial JD skill list
    if len(jd_skills) >= 5 and len(tech_matched) == 0:
        return min(raw, 40), "framework_cap"

    # Half-stack penalty: explicit full-stack role + one entire half missing
    jd_fullstack = bool(re.search(r'\bfull.?stack\b', jd_lower, re.IGNORECASE))
    if jd_fullstack:
        has_backend  = bool(re.search(
            r'\b(?:node|django|flask|fastapi|spring|express|rails|laravel|backend|server.side)\b',
            cv_lower,
        ))
        has_frontend = bool(re.search(
            r'\b(?:react|angular|vue|svelte|next\.?js|frontend|html|css|tailwind)\b',
            cv_lower,
        ))
        if has_backend ^ has_frontend:
            return min(raw, 70), "halfstack_penalty"

    return raw, None


def compute_rubric_score(
    cv_text: str,
    jd_text: str,
    jd_skills: List[str],
    cv_skills: Optional[List[str]] = None,
) -> dict:
    """
    Compute the 100-point structured rubric score for a candidate against a JD.

    Args:
      cv_text   — raw CV text
      jd_text   — raw job-description text
      jd_skills — pre-extracted JD skill list
      cv_skills — optional pre-extracted CV skill list; when supplied the
                  function skips its own extract_skills_keyword() call,
                  saving a redundant regex pass over the CV text.

    Returns:
      total          — final clamped score after KO rules (0–100)
      breakdown      — per-axis raw scores before KO
      rawTotal       — uncapped sum of all four axes
      koApplied      — "framework_cap" | "halfstack_penalty" | null
      strengths      — human-readable matched criteria list
      gaps           — human-readable missing criteria / KO notes
      experienceTier — "senior" | "mid" | "junior"
    """
    cv_lower  = cv_text.lower()
    jd_lower  = jd_text.lower()
    if cv_skills is None:
        cv_skills = extract_skills_keyword(cv_text)

    tech_score, tech_matched, tech_missing = _score_tech_stack(cv_skills, jd_skills)
    arch_score, arch_signals              = _score_architecture(cv_lower, jd_lower)
    exp_score,  exp_tier                  = _score_experience(cv_text, cv_lower, jd_lower)
    pref_score, bonus_matched             = _score_preferred(cv_lower, cv_skills, jd_skills)

    raw_total            = tech_score + arch_score + exp_score + pref_score
    final_score, ko_rule = _apply_ko_rules(
        raw_total, tech_matched, jd_skills, cv_lower, jd_lower
    )

    strengths: List[str] = []
    gaps: List[str]      = []

    if tech_matched:
        strengths.append(f"Tech: {', '.join(s.title() for s in tech_matched[:6])}")
    if tech_missing:
        gaps.append(f"Missing skills: {', '.join(s.title() for s in tech_missing[:6])}")
    if arch_signals:
        strengths.append(f"Architecture signals: {', '.join(arch_signals[:3])}")
    if exp_tier in ("senior", "mid"):
        strengths.append(f"Experience level: {exp_tier}")
    elif exp_tier == "junior":
        gaps.append("Limited experience signals — junior level assumed")
    if bonus_matched:
        strengths.append(f"Bonus qualifications: {', '.join(bonus_matched)}")
    if ko_rule == "framework_cap":
        gaps.append("KO rule: No skill overlap with JD — score capped at 40")
    elif ko_rule == "halfstack_penalty":
        gaps.append("KO rule: Half-stack profile on full-stack role — score capped at 70")

    return {
        "total":       final_score,
        "breakdown": {
            "techStack":    tech_score,
            "architecture": arch_score,
            "experience":   exp_score,
            "preferred":    pref_score,
        },
        "rawTotal":       raw_total,
        "koApplied":      ko_rule,
        "strengths":      strengths,
        "gaps":           gaps,
        "experienceTier": exp_tier,
    }
