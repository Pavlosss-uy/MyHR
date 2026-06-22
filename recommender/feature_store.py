"""
Feature Store for Candidate Ranking (MOD-5)
============================================
Extracts the 8-D aggregate feature vector for a completed interview session.

The 8 features match exactly what NeuralCandidateRanker expects:
  [skill_match, relevance, clarity, depth, confidence, consistency, gaps_inverted, experience]

These are already computed per-answer by AnswerFeatureExtractor during the interview
and stored in evaluations[*].feature_values.  Averaging across all answered questions
gives a robust session-level representation without re-running the extractor.

Fallback: if feature_values are absent (old sessions) we derive a coarser vector
from the per-answer scores stored in evaluations[*].score.
"""
from __future__ import annotations

import os
import json
from typing import Optional

import torch


def _load_session_state(session_id: str) -> Optional[dict]:
    """Return the state_data dict for a session, or None on failure."""
    try:
        from firestore_client import get_session
        record = get_session(session_id)
        if record:
            return record.get("state_data", {})
    except Exception as e:
        print(f"[FeatureStore] Firestore lookup failed for {session_id}: {e}")

    # Fallback: check local rich-report file (useful in test/dev environments)
    report_path = os.path.join("storage", "reports", f"{session_id}_rich_report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return None


def extract_candidate_features(session_id: str) -> Optional[torch.Tensor]:
    """
    Return a (1, 7) float32 tensor representing the candidate's aggregate
    feature vector for this session, or None if the session cannot be loaded
    or has no evaluated answers.

    The 7 dimensions match NeuralCandidateRanker.input_features=7:
        0  skill_match      — CV-to-JD semantic match (0-1)
        1  relevance        — average answer relevance to questions (0-1)
        2  clarity          — average answer clarity score (0-1)
        3  depth            — average technical depth (0-1)
        4  confidence       — average vocal confidence from tone analysis (0-1)
        5  consistency      — thematic consistency across answers (0-1)
        6  gaps_inverted    — JD requirement coverage (0-1)

    NOTE: experience (formerly [7]) was dropped to match the 7-D training
    data after removing salary_percentile leakage from the ranker.
    """
    state = _load_session_state(session_id)
    if not state:
        return None

    evaluations = state.get("evaluations", []) or state.get("question_scores", [])
    if not evaluations:
        return None

    # --- Primary path: pre-computed feature_values from AnswerFeatureExtractor ---
    # Accept both 7-D (new) and 8-D (legacy) stored vectors; truncate 8-D to 7.
    feature_rows = []
    for e in evaluations:
        fv = e.get("feature_values")
        if fv and len(fv) >= 7:
            feature_rows.append(list(fv)[:7])

    if feature_rows:
        avg = torch.tensor(
            [sum(col) / len(feature_rows) for col in zip(*feature_rows)],
            dtype=torch.float32,
        )
        return avg.unsqueeze(0)  # (1, 7)

    # --- Fallback: reconstruct a coarser 7-D vector from stored scores ---
    # Only triggered for sessions that predate the feature_values field.
    scores, relevances, clarities, depths = [], [], [], []
    for e in evaluations:
        s = e.get("score", 0)
        scores.append(float(s) / 100.0)
        cb = e.get("criteria_breakdown") or {}
        relevances.append(float(cb.get("relevance", s)) / 100.0)
        clarities.append(float(cb.get("clarity", s)) / 100.0)
        depths.append(float(cb.get("technical_depth", s)) / 100.0)

    avg_score = sum(scores) / len(scores) if scores else 0.5

    def _avg(lst): return sum(lst) / len(lst) if lst else avg_score

    skill = float(state.get("skill_match_score", avg_score))
    if skill > 1.0:
        skill /= 100.0

    features = [
        min(max(skill, 0.0), 1.0),
        _avg(relevances),
        _avg(clarities),
        _avg(depths),
        avg_score,   # confidence proxy
        avg_score,   # consistency proxy
        avg_score,   # gaps proxy
    ]
    return torch.tensor([features], dtype=torch.float32)


def build_ideal_profile() -> torch.Tensor:
    """
    Return a (1, 7) ideal-candidate feature tensor used as the ranking anchor.
    All dimensions set to 1.0 — maximum performance on every axis.
    Ranking then orders candidates by cosine similarity to this anchor.
    """
    return torch.ones(1, 7, dtype=torch.float32)
