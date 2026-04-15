"""
CV text extraction and entity parsing module.
Handles PDF and DOCX file formats, extracts candidate contact info and skills.
"""
import io
import re
from typing import Optional

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


def extract_skills_keyword(text: str) -> list[str]:
    """
    Extract skills from text using keyword matching.
    Fast, deterministic, no API calls.
    """
    if not text:
        return []

    text_lower = text.lower()
    found = []

    for skill in COMMON_SKILLS:
        # Word boundary matching for short skills (avoid false positives)
        if len(skill) <= 2:
            pattern = rf'\b{re.escape(skill)}\b'
            if re.search(pattern, text_lower):
                found.append(skill.title() if len(skill) > 2 else skill.upper())
        else:
            if skill in text_lower:
                # Capitalize properly
                found.append(skill.title() if skill.islower() else skill)

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
