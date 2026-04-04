import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

import torch

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import spacy  # type: ignore
except Exception:  # pragma: no cover
    spacy = None

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None


DISCOURSE_MARKERS = [
    "because", "therefore", "for example", "specifically",
    "however", "first", "second"
]
PROJECT_VERBS = ["led", "built", "managed", "developed", "implemented", "designed", "delivered"]
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "for", "to", "of", "in", "on", "at", "by",
    "with", "as", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "from", "into", "about", "over", "under", "than", "also", "can", "could", "should",
    "would", "will", "may", "might", "do", "does", "did", "have", "has", "had", "i", "we", "you",
    "they", "he", "she", "them", "our", "your", "my"
}


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return default if den == 0 else num / den


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class AnswerFeatureExtractor:
    def __init__(self) -> None:
        self.embedder = self._load_embedder()
        self.nlp = self._load_spacy()
        self._skill_matcher = self._load_skill_matcher()

    def _load_embedder(self):
        if SentenceTransformer is None:
            return None
        try:
            return SentenceTransformer("all-mpnet-base-v2")
        except Exception:
            return None

    def _load_spacy(self):
        if spacy is None:
            return None
        try:
            return spacy.load("en_core_web_sm")
        except Exception:
            try:
                return spacy.blank("en")
            except Exception:
                return None

    def _load_skill_matcher(self):
        try:
            from models.registry import registry  # type: ignore
            return registry.load_skill_matcher()
        except Exception:
            return None

    def extract(
        self,
        question: str,
        answer: str,
        jd_text: str,
        cv_text: str,
        tone_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[Iterable[str]] = None,
        precomputed_skill_match: Optional[float] = None,
    ) -> torch.Tensor:
        tone_data = tone_data or {}
        history_list = list(conversation_history or [])

        # Use pre-computed skill match from server.py if available
        if precomputed_skill_match is not None:
            skill = _clamp01(float(precomputed_skill_match))
        else:
            skill = self._skill_match(cv_text, jd_text)

        feature_values = [
            skill,
            self._relevance(question, answer),
            self._clarity(answer),
            self._technical_depth(answer, jd_text),
            self._confidence(tone_data),
            self._consistency(answer, history_list),
            self._gaps_inverted(answer, jd_text, history_list),
            self._experience(answer),
        ]

        return torch.tensor([feature_values], dtype=torch.float32)

    def _skill_match(self, cv_text: str, jd_text: str) -> float:
        if self._skill_matcher is not None:
            try:
                score = self._skill_matcher.calculate_match_score(cv_text or "", jd_text or "")
                if isinstance(score, (int, float)):
                    return _clamp01(float(score)) if score <= 1.0 else _clamp01(float(score) / 100.0)
            except Exception:
                pass
        return self._keyword_overlap(cv_text, jd_text)

    def _embed_text(self, text: str):
        if not text:
            return None
        if self.embedder is not None:
            try:
                return self.embedder.encode(text)
            except Exception:
                pass
        return Counter(self._tokenize(text))

    def _cosine(self, a, b) -> float:
        if a is None or b is None:
            return 0.0
        if np is not None and not isinstance(a, Counter) and not isinstance(b, Counter):
            a_arr = np.array(a)
            b_arr = np.array(b)
            denom = float(np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
            if denom == 0.0:
                return 0.0
            return float(np.dot(a_arr, b_arr) / denom)
        if isinstance(a, Counter) and isinstance(b, Counter):
            keys = set(a) | set(b)
            dot = sum(a[k] * b[k] for k in keys)
            norm_a = math.sqrt(sum(v * v for v in a.values()))
            norm_b = math.sqrt(sum(v * v for v in b.values()))
            return _safe_div(dot, norm_a * norm_b, 0.0)
        return 0.0

    def _relevance(self, question: str, answer: str) -> float:
        return _clamp01(self._cosine(self._embed_text(question), self._embed_text(answer)))

    def _clarity(self, answer: str) -> float:
        sentences = self._sentences(answer)
        tokens = self._tokenize(answer)
        if not tokens:
            return 0.0

        avg_sentence_length = len(tokens) / max(len(sentences), 1)
        sentence_score = _clamp01(1 - (avg_sentence_length / 50.0))

        ttr = _safe_div(len(set(tokens)), len(tokens), 0.0)

        lowered = answer.lower()
        discourse_hits = sum(lowered.count(marker) for marker in DISCOURSE_MARKERS)
        discourse_ratio = _clamp01(_safe_div(discourse_hits, max(len(sentences), 1), 0.0))

        score = 0.4 * sentence_score + 0.3 * ttr + 0.3 * discourse_ratio
        return _clamp01(score)

    def _technical_depth(self, answer: str, jd_text: str) -> float:
        jd_terms = self._extract_technical_terms(jd_text)
        if not jd_terms:
            return self._keyword_overlap(answer, jd_text)

        answer_tokens = set(self._tokenize(answer))
        hits = sum(1 for term in jd_terms if term in answer_tokens or term in answer.lower())
        return _clamp01(_safe_div(hits, len(jd_terms), 0.0))

    def _confidence(self, tone_data: Dict[str, Any]) -> float:
        value = tone_data.get("confidence", 0.5)
        try:
            return _clamp01(float(value))
        except Exception:
            return 0.5

    def _consistency(self, answer: str, conversation_history: List[str]) -> float:
        previous_answers = []
        for item in conversation_history:
            if isinstance(item, str) and item.startswith("Candidate:"):
                previous_answers.append(item.split(":", 1)[1].strip())
        if len(previous_answers) < 2:
            return 0.7

        current_emb = self._embed_text(answer)
        previous_embs = [self._embed_text(a) for a in previous_answers if a.strip()]
        previous_embs = [e for e in previous_embs if e is not None]
        if not previous_embs:
            return 0.7

        if np is not None and not isinstance(previous_embs[0], Counter):
            mean_emb = np.mean(np.array(previous_embs), axis=0)
        else:
            mean_emb = Counter()
            for emb in previous_embs:
                mean_emb.update(emb)
            for key in mean_emb:
                mean_emb[key] /= len(previous_embs)
        return _clamp01(self._cosine(current_emb, mean_emb))

    def _gaps_inverted(self, answer: str, jd_text: str, conversation_history: List[str]) -> float:
        requirements = self._extract_requirement_keywords(jd_text)
        if not requirements:
            return self._keyword_overlap(answer, jd_text)
        combined_answers = " ".join([
            answer,
            *[
                item.split(":", 1)[1].strip()
                for item in conversation_history
                if isinstance(item, str) and item.startswith("Candidate:")
            ]
        ]).lower()
        found = sum(1 for req in requirements if req in combined_answers)
        return _clamp01(_safe_div(found, len(requirements), 0.0))

    def _experience(self, answer: str) -> float:
        lowered = answer.lower()
        year_patterns = len(re.findall(r"\b\d+\s+years?\b", lowered))
        since_patterns = len(re.findall(r"\bsince\s+20\d{2}\b", lowered))
        project_mentions = sum(lowered.count(v) for v in PROJECT_VERBS)
        org_mentions = 0
        if self.nlp is not None:
            try:
                doc = self.nlp(answer)
                org_mentions = sum(1 for ent in getattr(doc, "ents", []) if getattr(ent, "label_", "") == "ORG")
            except Exception:
                org_mentions = 0
        total = year_patterns + since_patterns + project_mentions + org_mentions
        return _clamp01(total / 10.0)

    def _extract_technical_terms(self, jd_text: str) -> List[str]:
        tokens = [t for t in self._tokenize(jd_text) if len(t) > 2 and t not in STOPWORDS]
        if not tokens:
            return []
        counts = Counter(tokens)
        return [term for term, _ in counts.most_common(20)]

    def _extract_requirement_keywords(self, jd_text: str) -> List[str]:
        text = jd_text or ""
        keywords = set()
        if self.nlp is not None:
            try:
                doc = self.nlp(text)
                for token in doc:
                    if getattr(token, "pos_", "") in {"NOUN", "PROPN"}:
                        token_text = token.text.strip().lower()
                        if len(token_text) > 2 and token_text not in STOPWORDS:
                            keywords.add(token_text)
                for chunk in getattr(doc, "noun_chunks", []):
                    chunk_text = chunk.text.strip().lower()
                    if 2 < len(chunk_text) <= 40:
                        keywords.add(chunk_text)
            except Exception:
                pass
        if not keywords:
            keywords.update(self._extract_technical_terms(text))
        return sorted(keywords)

    def _keyword_overlap(self, text_a: str, text_b: str) -> float:
        a = set(self._tokenize(text_a))
        b = set(self._tokenize(text_b))
        if not a or not b:
            return 0.0
        return _clamp01(_safe_div(len(a & b), len(b), 0.0))

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[A-Za-z][A-Za-z0-9_+.#-]*", (text or "").lower())

    def _sentences(self, text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[.!?]+", text)
        return [p.strip() for p in parts if p.strip()]


extractor = AnswerFeatureExtractor()
