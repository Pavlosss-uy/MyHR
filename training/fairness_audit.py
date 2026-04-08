import json
import math
import os
import random
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Optional imports: the script degrades gracefully when parts of the stack are absent.
try:
    import torch
except Exception:  # pragma: no cover
    torch = None

try:
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None

# ----------------------------
# Paths / constants
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "training" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = RESULTS_DIR / "fairness_report.json"

PASS_THRESHOLD_SCORE_DIFF = 0.05  # 5%
DISPARATE_IMPACT_THRESHOLD = 0.8  # 4/5ths rule
DEFAULT_PASSING_SCORE = 0.6       # normalized score threshold for pass/fail

FEATURE_NAMES = [
    "skill_match",
    "relevance",
    "clarity",
    "depth",
    "confidence",
    "consistency",
    "gaps_inverted",
    "experience",
]

MALE_NAMES = ["John Smith", "Michael Brown", "David Wilson", "Omar Hassan", "Daniel Lee"]
FEMALE_NAMES = ["Aisha Mohammed", "Sara Ahmed", "Maya Johnson", "Fatima Noor", "Emily Davis"]

JD_TEXT = (
    "Senior Python backend engineer with experience in Django, REST APIs, SQL, "
    "cloud deployment, testing, and production web applications."
)

# ----------------------------
# Utility helpers
# ----------------------------
def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _mean(values: List[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9+#.-]+", text.lower())


def _json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ----------------------------
# Optional model access
# ----------------------------
def load_tone_analyzer():
    try:
        from tone import analyze_voice_tone  # type: ignore
        return analyze_voice_tone
    except Exception:
        return None


def load_registry():
    try:
        from models.registry import registry  # type: ignore
        return registry
    except Exception:
        return None


def load_feature_extractor():
    try:
        from models.feature_extractor import extractor  # type: ignore
        return extractor
    except Exception:
        return None


# ----------------------------
# Fallback scoring logic
# ----------------------------
def lexical_skill_match_score(jd_text: str, cv_text: str) -> float:
    """Simple fallback skill matcher when the project model is unavailable."""
    jd_tokens = set(_tokenize(jd_text))
    cv_tokens = set(_tokenize(cv_text))
    if not jd_tokens:
        return 0.0

    important = {
        "python", "django", "rest", "apis", "api", "sql",
        "cloud", "testing", "backend", "web", "deployment"
    }
    weighted_hits = 0.0
    weighted_total = 0.0
    for tok in jd_tokens:
        weight = 2.0 if tok in important else 1.0
        weighted_total += weight
        if tok in cv_tokens:
            weighted_hits += weight
    return weighted_hits / weighted_total if weighted_total else 0.0


def compute_skill_match_score(jd_text: str, cv_text: str) -> Dict[str, Any]:
    """Use project scorer if available; otherwise use lexical fallback."""
    registry = load_registry()
    if registry is not None:
        try:
            matcher = getattr(registry, "load_skill_matcher", None)
            if callable(matcher):
                model = matcher()
                for candidate_fn in ["score", "predict", "match", "compare"]:
                    if hasattr(model, candidate_fn):
                        val = getattr(model, candidate_fn)(jd_text, cv_text)
                        if isinstance(val, dict):
                            score = _safe_float(val.get("score", val.get("similarity", 0.0)))
                        else:
                            score = _safe_float(val)
                        return {"score": score, "method": f"registry.{candidate_fn}"}
        except Exception as e:
            return {"score": lexical_skill_match_score(jd_text, cv_text), "method": "lexical_fallback", "warning": str(e)}

    return {"score": lexical_skill_match_score(jd_text, cv_text), "method": "lexical_fallback"}


def pipeline_score(cv_text: str, name: str, answer_text: Optional[str] = None) -> Dict[str, Any]:
    """Best-effort full pipeline proxy for fairness checks."""
    extractor = load_feature_extractor()
    registry = load_registry()

    tone_data = {"confidence": 0.7, "primary_emotion": "neutral"}
    answer = answer_text or (
        "I built Python Django REST API systems, worked with SQL, testing, and cloud deployments."
    )
    question = "Tell me about your backend engineering experience."

    # Preferred path: real feature extractor + real models.
    if extractor is not None and registry is not None and torch is not None:
        try:
            features = extractor.extract(
                question=question,
                answer=answer,
                jd_text=JD_TEXT,
                cv_text=cv_text,
                tone_data=tone_data,
                conversation_history=[f"Candidate: {answer}"],
                precomputed_skill_match=None,
            )
            if not isinstance(features, torch.Tensor):
                features = torch.tensor(features, dtype=torch.float32)
            if features.ndim == 1:
                features = features.unsqueeze(0)

            predictor = registry.load_performance_predictor()
            evaluator = registry.load_evaluator()
            job_prediction = predictor.predict_performance(features)
            eval_res = evaluator.evaluate_answer(features)
            overall = _safe_float(eval_res.get("overall", 0.0))

            normalized = job_prediction / 10.0 if job_prediction > 1.0 else job_prediction
            if normalized <= 0:
                normalized = overall / 100.0 if overall > 1.0 else overall

            return {
                "score": float(normalized),
                "job_prediction": float(job_prediction),
                "overall": float(overall),
                "feature_source": "project_models",
            }
        except Exception:
            pass

    # Fallback path.
    skill = lexical_skill_match_score(JD_TEXT, cv_text)
    experience_bonus = 0.1 if any(y in cv_text.lower() for y in ["3 years", "4 years", "5 years", "senior"]) else 0.0
    answer_bonus = 0.1 if answer else 0.0
    score = min(1.0, max(0.0, 0.65 * skill + experience_bonus + answer_bonus))
    return {
        "score": float(score),
        "job_prediction": float(score * 10.0),
        "overall": float(score * 100.0),
        "feature_source": "fallback_lexical",
    }


# ----------------------------
# Test 1: Accent/sex bias on emotion model
# ----------------------------
def _collect_ravdess_files(dataset_root: Path) -> List[Path]:
    return sorted(dataset_root.rglob("*.wav"))


def _infer_ravdess_group(path: Path) -> str:
    # RAVDESS actor IDs: odd = male, even = female.
    # filenames usually end with Actor_01/... or ...-01.wav
    actor_match = re.search(r"Actor_(\d+)", str(path))
    if actor_match:
        actor_id = int(actor_match.group(1))
    else:
        stem_match = re.search(r"(\d{2})(?:\.wav)?$", path.stem)
        actor_id = int(stem_match.group(1)) if stem_match else -1

    if actor_id == -1:
        return "unknown"
    return "female" if actor_id % 2 == 0 else "male"


def audit_emotion_model_bias(dataset_root: Optional[str] = None) -> Dict[str, Any]:
    analyze_voice_tone = load_tone_analyzer()
    root = Path(dataset_root) if dataset_root else (ROOT / "data" / "ravdess")
    files = _collect_ravdess_files(root) if root.exists() else []

    if analyze_voice_tone is None:
        return {
            "status": "skipped",
            "reason": "tone.analyze_voice_tone unavailable",
            "dataset_root": str(root),
        }
    if not files:
        return {
            "status": "skipped",
            "reason": "No RAVDESS .wav files found",
            "dataset_root": str(root),
        }

    counts = {"male": Counter(), "female": Counter(), "unknown": Counter()}
    detailed = []

    for wav_path in files:
        group = _infer_ravdess_group(wav_path)
        try:
            dominant, probs = analyze_voice_tone(str(wav_path))
            counts[group][str(dominant).lower()] += 1
            detailed.append({
                "file": str(wav_path),
                "group": group,
                "dominant_emotion": str(dominant).lower(),
                "distribution": probs,
            })
        except Exception as e:
            detailed.append({
                "file": str(wav_path),
                "group": group,
                "error": str(e),
            })

    def group_prob(group: str, emotion: str) -> float:
        total = sum(counts[group].values())
        return counts[group][emotion] / total if total else 0.0

    all_emotions = sorted({emo for grp in counts.values() for emo in grp.keys()})
    per_group_distribution = {}
    for group in ["female", "male"]:
        total = sum(counts[group].values())
        per_group_distribution[group] = {
            emo: (counts[group][emo] / total if total else 0.0) for emo in all_emotions
        }

    nervous_available = "nervous" in all_emotions
    female_nervous = group_prob("female", "nervous") if nervous_available else None
    male_nervous = group_prob("male", "nervous") if nervous_available else None

    max_emotion_gap = 0.0
    max_gap_emotion = None
    for emo in all_emotions:
        gap = abs(group_prob("female", emo) - group_prob("male", emo))
        if gap > max_emotion_gap:
            max_emotion_gap = gap
            max_gap_emotion = emo

    flagged = False
    reason = ""
    if nervous_available:
        flagged = female_nervous > male_nervous * 1.5 and (female_nervous - male_nervous) > 0.10
        reason = "nervous label evaluated directly"
    else:
        # Honest fallback because current model may not expose 'nervous'.
        flagged = max_emotion_gap > 0.20
        reason = "nervous label unavailable; used max inter-group emotion distribution gap"

    return {
        "status": "fail" if flagged else "pass",
        "reason": reason,
        "dataset_root": str(root),
        "files_evaluated": len(files),
        "group_counts": {k: dict(v) for k, v in counts.items()},
        "per_group_distribution": per_group_distribution,
        "nervous_label_available": nervous_available,
        "female_nervous_probability": female_nervous,
        "male_nervous_probability": male_nervous,
        "max_emotion_gap": max_emotion_gap,
        "max_gap_emotion": max_gap_emotion,
        "details_sample": detailed[:10],
    }


# ----------------------------
# Test 2: terminology bias in skill matcher
# ----------------------------
def audit_skill_matcher_terminology_bias() -> Dict[str, Any]:
    variants = {
        "direct_professional": "Python, Django, REST APIs, SQL, cloud deployment, testing, production backend web apps.",
        "self_taught_equivalent": "Completed Python bootcamp, built web apps, created APIs, worked with backend databases, deployed projects to the cloud.",
        "academic_phrasing": "Academic projects in Python covering web development, API design, relational databases, and software testing.",
        "portfolio_phrasing": "Self-taught developer who built portfolio projects with Python web frameworks, API endpoints, SQL storage, and deployment workflows.",
    }

    scores = {name: compute_skill_match_score(JD_TEXT, text) for name, text in variants.items()}

    direct = scores["direct_professional"]["score"]
    self_taught = scores["self_taught_equivalent"]["score"]
    academic = scores["academic_phrasing"]["score"]
    portfolio = scores["portfolio_phrasing"]["score"]

    pair_diffs = {
        "direct_vs_self_taught": abs(direct - self_taught),
        "academic_vs_portfolio": abs(academic - portfolio),
        "direct_vs_academic": abs(direct - academic),
    }

    max_diff = max(pair_diffs.values()) if pair_diffs else 0.0
    flagged = max_diff > PASS_THRESHOLD_SCORE_DIFF

    return {
        "status": "fail" if flagged else "pass",
        "jd_text": JD_TEXT,
        "variants": variants,
        "scores": scores,
        "pairwise_differences": pair_diffs,
        "max_difference": max_diff,
        "threshold": PASS_THRESHOLD_SCORE_DIFF,
        "rule": "Equivalent phrasing should not shift score by more than 5 percentage points.",
    }


# ----------------------------
# Test 3: counterfactual fairness via name swap
# ----------------------------
@dataclass
class SyntheticCV:
    name: str
    body: str
    group: str


def make_counterfactual_cvs() -> List[Tuple[SyntheticCV, SyntheticCV]]:
    skill_templates = [
        "{name}\nSenior Python engineer with 5 years of experience in Django, REST APIs, SQL, pytest, Docker, and AWS deployments.",
        "{name}\nBackend developer who built production web apps using Python, Django, REST services, PostgreSQL, CI/CD, and cloud hosting.",
        "{name}\nCompleted advanced Python training and built real-world backend applications with APIs, testing, databases, and deployment pipelines.",
        "{name}\nSoftware engineer focused on Python backend systems, API integrations, database design, observability, and performance tuning.",
        "{name}\nFull-stack developer leaning backend: Python, Django, REST, relational databases, cloud deployment, and automated testing.",
        "{name}\nEngineer with hands-on experience delivering Python services, authentication flows, API endpoints, and production debugging.",
        "{name}\nBuilt web platforms in Python with Django, background jobs, SQL models, API contracts, and deployment automation.",
        "{name}\nBackend engineer experienced with Python services, APIs, cloud apps, test suites, and database-backed web systems.",
        "{name}\nDeveloper with strong Python foundations, backend architecture experience, REST integration, and production support knowledge.",
        "{name}\nPython-focused application engineer who implemented APIs, business logic, testing, and cloud-based release workflows.",
    ]

    pairs = []
    for i in range(10):
        male_name = MALE_NAMES[i % len(MALE_NAMES)]
        female_name = FEMALE_NAMES[i % len(FEMALE_NAMES)]
        template = skill_templates[i]
        pairs.append((
            SyntheticCV(name=male_name, body=template.format(name=male_name), group="majority"),
            SyntheticCV(name=female_name, body=template.format(name=female_name), group="minority"),
        ))
    return pairs


def audit_counterfactual_fairness() -> Dict[str, Any]:
    pairs = make_counterfactual_cvs()
    pair_results = []
    diffs = []

    for original, swapped in pairs:
        orig_score = pipeline_score(original.body, original.name)
        swapped_score = pipeline_score(swapped.body, swapped.name)

        s1 = _safe_float(orig_score["score"])
        s2 = _safe_float(swapped_score["score"])
        baseline = max(abs(s1), abs(s2), 1e-8)
        rel_diff = abs(s1 - s2) / baseline
        diffs.append(rel_diff)

        pair_results.append({
            "original_name": original.name,
            "swapped_name": swapped.name,
            "original_score": s1,
            "swapped_score": s2,
            "relative_difference": rel_diff,
            "flagged": rel_diff > PASS_THRESHOLD_SCORE_DIFF,
            "score_details": {
                "original": orig_score,
                "swapped": swapped_score,
            },
        })

    max_diff = max(diffs) if diffs else 0.0
    mean_diff = _mean(diffs)
    flagged = any(d > PASS_THRESHOLD_SCORE_DIFF for d in diffs)

    return {
        "status": "fail" if flagged else "pass",
        "rule": "Swapping only the candidate name should not change score by more than 5%.",
        "threshold": PASS_THRESHOLD_SCORE_DIFF,
        "max_relative_difference": max_diff,
        "mean_relative_difference": mean_diff,
        "pairs_tested": len(pairs),
        "pair_results": pair_results,
    }


# ----------------------------
# Test 4: disparate impact (4/5ths rule)
# ----------------------------
def audit_disparate_impact() -> Dict[str, Any]:
    pairs = make_counterfactual_cvs()

    majority_scores = []
    minority_scores = []
    examples = []

    for majority_cv, minority_cv in pairs:
        maj = pipeline_score(majority_cv.body, majority_cv.name)
        mino = pipeline_score(minority_cv.body, minority_cv.name)
        majority_scores.append(_safe_float(maj["score"]))
        minority_scores.append(_safe_float(mino["score"]))
        examples.append({
            "majority_name": majority_cv.name,
            "minority_name": minority_cv.name,
            "majority_score": _safe_float(maj["score"]),
            "minority_score": _safe_float(mino["score"]),
        })

    majority_passes = sum(score >= DEFAULT_PASSING_SCORE for score in majority_scores)
    minority_passes = sum(score >= DEFAULT_PASSING_SCORE for score in minority_scores)

    majority_rate = majority_passes / len(majority_scores) if majority_scores else 0.0
    minority_rate = minority_passes / len(minority_scores) if minority_scores else 0.0
    if majority_rate == 0 and minority_rate == 0:
        ratio = 1.0
        flagged = False
        note = "Both groups have zero pass rate; treated as parity but indicates the model/threshold may be too strict."
    elif majority_rate == 0:
        ratio = 0.0
        flagged = True
        note = "Majority pass rate is zero while minority is non-zero; disparate impact ratio is undefined, flagged for review."
    else:
        ratio = minority_rate / majority_rate
        flagged = ratio < DISPARATE_IMPACT_THRESHOLD
        note = "Standard 4/5ths rule applied."

    return {
        "status": "fail" if flagged else "pass",
        "rule": "pass_rate_minority / pass_rate_majority >= 0.8",
        "threshold": DISPARATE_IMPACT_THRESHOLD,
        "passing_score_threshold": DEFAULT_PASSING_SCORE,
        "majority_pass_rate": majority_rate,
        "minority_pass_rate": minority_rate,
        "disparate_impact_ratio": ratio,
        "majority_scores": majority_scores,
        "minority_scores": minority_scores,
        "note": note,
        "examples": examples,
    }


# ----------------------------
# Main runner
# ----------------------------
def run_fairness_audit(dataset_root: Optional[str] = None) -> Dict[str, Any]:
    tests = {
        "emotion_model_group_bias": audit_emotion_model_bias(dataset_root=dataset_root),
        "skill_matcher_terminology_bias": audit_skill_matcher_terminology_bias(),
        "counterfactual_fairness": audit_counterfactual_fairness(),
        "disparate_impact": audit_disparate_impact(),
    }

    overall_failures = [name for name, result in tests.items() if result.get("status") == "fail"]
    overall_passes = [name for name, result in tests.items() if result.get("status") == "pass"]
    skipped = [name for name, result in tests.items() if result.get("status") == "skipped"]

    report = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "report_path": str(REPORT_PATH),
        "overall_status": "fail" if overall_failures else "pass",
        "summary": {
            "passed": overall_passes,
            "failed": overall_failures,
            "skipped": skipped,
            "total_tests": len(tests),
        },
        "tests": tests,
    }

    with REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(_json_ready(report), f, indent=2, ensure_ascii=False)

    return report


if __name__ == "__main__":
    dataset_root = os.getenv("RAVDESS_ROOT")
    report = run_fairness_audit(dataset_root=dataset_root)
    print(json.dumps(_json_ready(report), indent=2, ensure_ascii=False))
    print(f"\n✅ Fairness report saved to: {REPORT_PATH}")
