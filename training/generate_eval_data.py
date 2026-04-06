"""
Evaluation Data Generator (LLM-as-Labeler)
============================================
Generates labeled training data for the Multi-Head Evaluator and Cross-Encoder
using Groq LLM as a judge.

Pipeline:
1. Generate diverse (question, answer) pairs across 4 quality tiers
2. Label each with LLM judge → (relevance, clarity, depth, overall_quality)
3. Extract 768-dim sentence embeddings as feature vectors
4. Save everything to data/eval_training_data.json

Supports:
- Progress checkpointing (resume after API failures)
- Exponential backoff for rate limits
- Quality tier distribution: excellent, good, mediocre, poor
"""

import os
import sys
import json
import time
import random
import hashlib
import numpy as np
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer


# ─── Configuration ───────────────────────────────────────────────────────────

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "eval_training_data.json")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "eval_data_checkpoint.json")

# Quality tier distribution
QUALITY_TIERS = {
    "excellent": 50,
    "good": 50,
    "mediocre": 50,
    "poor": 50,
}
TOTAL_SAMPLES = sum(QUALITY_TIERS.values())  # 200

# Retry config
MAX_RETRIES = 5
BASE_DELAY = 2.0  # seconds


# ─── LLM Setup ──────────────────────────────────────────────────────────────

def get_llm():
    """Initialize Groq LLM client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Set it as an environment variable:\n"
            "  Windows: set GROQ_API_KEY=your_key_here\n"
            "  Linux:   export GROQ_API_KEY=your_key_here"
        )
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        openai_api_key=api_key,
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.7,
    )


# ─── Question/Answer Templates ──────────────────────────────────────────────

INTERVIEW_TOPICS = [
    "data structures and algorithms",
    "object-oriented programming",
    "system design and architecture",
    "database management and SQL",
    "REST APIs and web services",
    "version control with Git",
    "testing and debugging strategies",
    "cloud computing and deployment",
    "agile methodology and teamwork",
    "behavioral and leadership",
    "problem-solving approach",
    "machine learning basics",
    "networking and security",
    "DevOps and CI/CD",
    "frontend development",
    "Python programming",
    "JavaScript and TypeScript",
    "microservices architecture",
    "performance optimization",
    "code review practices",
]

QUALITY_PROMPTS = {
    "excellent": (
        "Generate an EXCELLENT interview Q&A pair about {topic}. "
        "The answer should be comprehensive, well-structured, use specific examples, "
        "demonstrate deep technical knowledge, and be clearly articulated. "
        "The answer should be 3-5 sentences long."
    ),
    "good": (
        "Generate a GOOD interview Q&A pair about {topic}. "
        "The answer should be mostly correct and relevant, with decent structure, "
        "but may lack some depth or specific examples. "
        "The answer should be 2-4 sentences long."
    ),
    "mediocre": (
        "Generate a MEDIOCRE interview Q&A pair about {topic}. "
        "The answer should be vague, partially correct, lack structure, "
        "miss key points, or use only surface-level knowledge. "
        "The answer should be 1-3 sentences long."
    ),
    "poor": (
        "Generate a POOR interview Q&A pair about {topic}. "
        "The answer should be wrong, off-topic, extremely vague, "
        "or demonstrate a fundamental misunderstanding of the concept. "
        "The answer should be 1-2 sentences long."
    ),
}

GENERATION_PROMPT = """You are an interview simulation system. {quality_instruction}

Return ONLY a JSON object with these exact keys:
{{
    "question": "the interview question",
    "answer": "the candidate's answer"
}}

Do not include any text outside the JSON object."""

LABELING_PROMPT = """You are an expert interview evaluator. Rate this interview answer on three dimensions (0-100 each).

Question: {question}
Answer: {answer}

Scoring criteria:
- relevance (0-100): How well does the answer address the specific question asked?
- clarity (0-100): How clear, well-structured, and easy to understand is the answer?
- technical_depth (0-100): How much technical knowledge, specific examples, and depth does the answer demonstrate?

Also provide an overall_quality score (0-100) that reflects the holistic quality.

Return ONLY a JSON object:
{{"relevance": int, "clarity": int, "technical_depth": int, "overall_quality": int}}"""


# ─── Helper Functions ────────────────────────────────────────────────────────

def call_llm_with_retry(llm, prompt: str, max_retries: int = MAX_RETRIES) -> str:
    """Call LLM with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  ❌ Failed after {max_retries} attempts: {e}")
                raise
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            print(f"  ⚠️  Attempt {attempt + 1} failed ({e}). Retrying in {delay:.1f}s...")
            time.sleep(delay)


def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    return json.loads(text)


def load_checkpoint() -> dict:
    """Load progress checkpoint if it exists."""
    if Path(CHECKPOINT_FILE).exists():
        with open(CHECKPOINT_FILE, "r") as f:
            data = json.load(f)
            print(f"📂 Resuming from checkpoint: {len(data.get('samples', []))} samples completed")
            return data
    return {"samples": [], "completed_hashes": set()}


def save_checkpoint(data: dict):
    """Save progress checkpoint."""
    # Convert set to list for JSON serialization
    save_data = {
        "samples": data["samples"],
        "completed_hashes": list(data.get("completed_hashes", set())),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(save_data, f, indent=2)


def make_sample_hash(tier: str, topic: str, index: int) -> str:
    """Create a unique hash for a sample to track completion."""
    return hashlib.md5(f"{tier}:{topic}:{index}".encode()).hexdigest()[:12]


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def generate_qa_pairs(llm, num_per_tier: dict) -> list:
    """
    Step 1: Generate diverse (question, answer) pairs across quality tiers.
    """
    checkpoint = load_checkpoint()
    samples = checkpoint["samples"]
    completed = set(checkpoint.get("completed_hashes", []))

    total_needed = sum(num_per_tier.values())
    print(f"\n🔄 Generating {total_needed} Q&A pairs ({len(samples)} already done)...\n")

    for tier, count in num_per_tier.items():
        print(f"  📝 Tier: {tier.upper()} ({count} samples)")

        for i in range(count):
            topic = random.choice(INTERVIEW_TOPICS)
            sample_hash = make_sample_hash(tier, topic, i)

            if sample_hash in completed:
                continue

            quality_instruction = QUALITY_PROMPTS[tier].format(topic=topic)
            prompt = GENERATION_PROMPT.format(quality_instruction=quality_instruction)

            try:
                response = call_llm_with_retry(llm, prompt)
                qa = parse_json_response(response)

                if "question" not in qa or "answer" not in qa:
                    print(f"    ⚠️  Malformed response, skipping")
                    continue

                samples.append({
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "quality_tier": tier,
                    "topic": topic,
                    "hash": sample_hash,
                })
                completed.add(sample_hash)

                # Checkpoint every 10 samples
                if len(samples) % 10 == 0:
                    save_checkpoint({"samples": samples, "completed_hashes": completed})
                    print(f"    💾 Checkpoint: {len(samples)}/{total_needed} samples")

                # Rate limit protection
                time.sleep(1.5)

            except Exception as e:
                print(f"    ❌ Failed to generate ({tier}/{topic}/{i}): {e}")
                continue

    save_checkpoint({"samples": samples, "completed_hashes": completed})
    print(f"\n✅ Generated {len(samples)} Q&A pairs total\n")
    return samples


def label_samples(llm, samples: list) -> list:
    """
    Step 2: Label each (question, answer) pair with LLM judge scores.
    """
    print(f"🏷️  Labeling {len(samples)} samples with LLM judge...\n")

    labeled = 0
    for i, sample in enumerate(samples):
        # Skip already labeled
        if "relevance" in sample:
            labeled += 1
            continue

        prompt = LABELING_PROMPT.format(
            question=sample["question"],
            answer=sample["answer"],
        )

        try:
            response = call_llm_with_retry(llm, prompt)
            labels = parse_json_response(response)

            sample["relevance"] = int(np.clip(labels.get("relevance", 50), 0, 100))
            sample["clarity"] = int(np.clip(labels.get("clarity", 50), 0, 100))
            sample["technical_depth"] = int(np.clip(labels.get("technical_depth", 50), 0, 100))
            sample["overall_quality"] = int(np.clip(labels.get("overall_quality", 50), 0, 100))
            labeled += 1

            if labeled % 10 == 0:
                save_checkpoint({"samples": samples, "completed_hashes": set()})
                print(f"  💾 Labeled: {labeled}/{len(samples)}")

            time.sleep(1.5)

        except Exception as e:
            print(f"  ❌ Failed to label sample {i}: {e}")
            # Assign default scores based on tier
            tier_defaults = {
                "excellent": {"relevance": 90, "clarity": 90, "technical_depth": 85, "overall_quality": 88},
                "good": {"relevance": 72, "clarity": 70, "technical_depth": 65, "overall_quality": 69},
                "mediocre": {"relevance": 48, "clarity": 45, "technical_depth": 35, "overall_quality": 42},
                "poor": {"relevance": 20, "clarity": 25, "technical_depth": 15, "overall_quality": 18},
            }
            defaults = tier_defaults.get(sample.get("quality_tier", "mediocre"), tier_defaults["mediocre"])
            sample.update(defaults)
            labeled += 1

    print(f"\n✅ Labeled {labeled} samples\n")
    return samples


def extract_embeddings(samples: list) -> list:
    """
    Step 3: Extract 768-dim sentence embeddings as feature vectors.
    Uses all-MiniLM-L6-v2 (384-dim) — concatenates Q and A embeddings → 768-dim.
    """
    print("🧠 Extracting sentence embeddings...\n")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"  Model: all-MiniLM-L6-v2 ({embedding_dim}-dim)")
    print(f"  Output: {embedding_dim * 2}-dim (Q + A concatenated)\n")

    questions = [s["question"] for s in samples]
    answers = [s["answer"] for s in samples]

    # Batch encode
    q_embeddings = model.encode(questions, show_progress_bar=True, batch_size=32)
    a_embeddings = model.encode(answers, show_progress_bar=True, batch_size=32)

    # Concatenate Q and A embeddings → 768-dim feature vectors
    for i, sample in enumerate(samples):
        combined = np.concatenate([q_embeddings[i], a_embeddings[i]])
        sample["features"] = combined.tolist()

    print(f"\n✅ Extracted {len(samples)} feature vectors ({embedding_dim * 2}-dim each)\n")
    return samples


def save_dataset(samples: list, output_path: str = None):
    """Save the complete labeled dataset."""
    path = output_path or OUTPUT_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "created": datetime.now().isoformat(),
                "total_samples": len(samples),
                "feature_dim": len(samples[0].get("features", [])) if samples else 0,
                "quality_distribution": {
                    tier: sum(1 for s in samples if s.get("quality_tier") == tier)
                    for tier in QUALITY_TIERS
                },
            },
            "samples": samples,
        }, f, indent=2)

    print(f"💾 Dataset saved to {path}")
    print(f"   Total samples: {len(samples)}")
    print(f"   Feature dim: {len(samples[0].get('features', [])) if samples else 0}")

    # Clean up checkpoint
    if Path(CHECKPOINT_FILE).exists():
        os.remove(CHECKPOINT_FILE)
        print("   Cleaned up checkpoint file")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  📊 Evaluation Data Generator (LLM-as-Labeler)")
    print("=" * 60)

    # Check if data already exists
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)
        n = existing["metadata"]["total_samples"]
        print(f"\n⚠️  Existing dataset found with {n} samples.")
        response = input("   Regenerate? (y/N): ").strip().lower()
        if response != "y":
            print("   Using existing data. Exiting.")
            return

    llm = get_llm()

    # Step 1: Generate Q&A pairs
    samples = generate_qa_pairs(llm, QUALITY_TIERS)

    # Step 2: Label with LLM judge
    samples = label_samples(llm, samples)

    # Step 3: Extract embeddings
    samples = extract_embeddings(samples)

    # Step 4: Save
    save_dataset(samples)

    # Summary statistics
    print("\n📈 Score Distribution by Tier:")
    print("-" * 50)
    for tier in QUALITY_TIERS:
        tier_samples = [s for s in samples if s.get("quality_tier") == tier]
        if tier_samples:
            avg_rel = np.mean([s["relevance"] for s in tier_samples])
            avg_cla = np.mean([s["clarity"] for s in tier_samples])
            avg_dep = np.mean([s["technical_depth"] for s in tier_samples])
            print(f"  {tier:10s}: relevance={avg_rel:.1f} clarity={avg_cla:.1f} depth={avg_dep:.1f}")

    print("\n✅ Data generation complete! Next step:")
    print("   python training/train_evaluator.py")
    print("   python training/train_cross_encoder.py")


if __name__ == "__main__":
    main()
