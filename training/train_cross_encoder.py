"""
Cross-Encoder Fine-Tuning Script
==================================
Fine-tunes a cross-encoder (ms-marco-MiniLM-L-12-v2) for interview answer
quality scoring. Runs a comparison experiment against LLM-as-judge baseline.

Pipeline:
1. Load/extend labeled data from data/eval_training_data.json
2. Optionally generate additional diverse samples (behavioral, off-topic, vague)
3. Fine-tune cross-encoder with sentence-transformers .fit()
4. Compare: Cross-Encoder vs. LLM-as-Judge baseline (Spearman ρ)
5. Save to models/checkpoints/cross_encoder_scorer_v1/

Usage:
    python training/train_cross_encoder.py
    
Prerequisites:
    python training/generate_eval_data.py  (generates training data first)
"""

import os
import sys
import json
import time
import random
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sentence_transformers import CrossEncoder, InputExample
from torch.utils.data import DataLoader


# ─── Configuration ───────────────────────────────────────────────────────────

DATA_FILE = os.path.join(PROJECT_ROOT, "data", "eval_training_data.json")
EXTENDED_DATA_FILE = os.path.join(PROJECT_ROOT, "data", "cross_encoder_training_data.json")
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "models", "checkpoints", "cross_encoder_scorer_v1")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "training", "results")

BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

# Training hyperparameters
EPOCHS = 5
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
WARMUP_STEPS = 100
TRAIN_SPLIT = 0.8

# Additional data generation
GENERATE_EXTRA_SAMPLES = True
EXTRA_SAMPLE_COUNT = 300  # On top of existing ~200

SEED = 42


# ─── Additional Data Generation ─────────────────────────────────────────────

EXTRA_CATEGORIES = {
    "behavioral": {
        "prompt": (
            "Generate a {quality} behavioral interview Q&A pair. "
            "Topics: teamwork, conflict resolution, leadership, time management, adaptability. "
            "Question should start with 'Tell me about a time...' or 'Describe a situation...'. "
            "Return JSON: {{\"question\": str, \"answer\": str, \"overall_quality\": int_0_to_100}}"
        ),
        "count": 100,
    },
    "off_topic": {
        "prompt": (
            "Generate an interview Q&A pair where the answer is OFF-TOPIC or IRRELEVANT. "
            "The question is about {topic} but the answer talks about something completely different. "
            "The quality should be very low (10-25). "
            "Return JSON: {{\"question\": str, \"answer\": str, \"overall_quality\": int_0_to_100}}"
        ),
        "count": 80,
    },
    "vague": {
        "prompt": (
            "Generate an interview Q&A pair where the answer is VAGUE and GENERIC. "
            "The question is about {topic}. The answer uses buzzwords but says nothing concrete. "
            "Quality should be mediocre (25-45). "
            "Return JSON: {{\"question\": str, \"answer\": str, \"overall_quality\": int_0_to_100}}"
        ),
        "count": 60,
    },
    "concise_good": {
        "prompt": (
            "Generate an interview Q&A pair about {topic} where the answer is CONCISE but CORRECT. "
            "The answer is brief (1-2 sentences) but technically accurate. Quality: 55-75. "
            "Return JSON: {{\"question\": str, \"answer\": str, \"overall_quality\": int_0_to_100}}"
        ),
        "count": 60,
    },
}

TOPICS = [
    "data structures", "algorithms", "system design", "databases",
    "REST APIs", "Git workflow", "testing", "cloud computing",
    "Python", "JavaScript", "machine learning", "networking",
    "DevOps", "microservices", "performance optimization",
]


def generate_extra_data(existing_samples: list) -> list:
    """Generate additional diverse training samples via Groq."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("⚠️  GROQ_API_KEY not set. Skipping extra data generation.")
        print("   Training will use existing data only.")
        return existing_samples

    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile",
        openai_api_key=api_key,
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.8,
    )

    extra_samples = []
    quality_levels = ["excellent", "good", "mediocre", "poor"]

    for category, config in EXTRA_CATEGORIES.items():
        print(f"\n  📝 Generating {config['count']} {category} samples...")
        count = 0

        for i in range(config["count"]):
            quality = random.choice(quality_levels)
            topic = random.choice(TOPICS)

            prompt = config["prompt"].format(quality=quality, topic=topic)

            try:
                response = llm.invoke(prompt)
                text = response.content.strip()

                # Parse JSON
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

                data = json.loads(text.strip())

                extra_samples.append({
                    "question": data["question"],
                    "answer": data["answer"],
                    "overall_quality": int(np.clip(data.get("overall_quality", 50), 0, 100)),
                    "category": category,
                })
                count += 1

                if count % 20 == 0:
                    print(f"    Progress: {count}/{config['count']}")

                time.sleep(1.5)  # Rate limit

            except Exception as e:
                if i % 20 == 0:
                    print(f"    ⚠️  Error at sample {i}: {e}")
                continue

        print(f"    ✅ Generated {count}/{config['count']} {category} samples")

    # Combine with existing
    combined = existing_samples + extra_samples
    print(f"\n  📊 Total training data: {len(combined)} samples")
    print(f"     Original: {len(existing_samples)} | Extra: {len(extra_samples)}")

    # Save extended dataset
    os.makedirs(os.path.dirname(EXTENDED_DATA_FILE), exist_ok=True)
    with open(EXTENDED_DATA_FILE, "w") as f:
        json.dump({
            "metadata": {
                "created": datetime.now().isoformat(),
                "total_samples": len(combined),
                "original_samples": len(existing_samples),
                "extra_samples": len(extra_samples),
            },
            "samples": combined,
        }, f, indent=2)

    return combined


# ─── Data Preparation ────────────────────────────────────────────────────────

def load_and_prepare_data() -> tuple:
    """
    Load training data and prepare for cross-encoder fine-tuning.
    
    Returns:
        (train_examples, test_data) where test_data is list of
        (question, answer, quality_score) tuples
    """
    # Load base data
    if not Path(DATA_FILE).exists():
        print(f"❌ Base training data not found at {DATA_FILE}")
        print("   Run first: python training/generate_eval_data.py")
        sys.exit(1)

    with open(DATA_FILE) as f:
        dataset = json.load(f)

    samples = dataset["samples"]
    print(f"📂 Loaded {len(samples)} base samples")

    # Convert to cross-encoder format (use overall_quality score)
    ce_samples = []
    for s in samples:
        quality = s.get("overall_quality")
        if quality is None:
            # Fall back to average of relevance, clarity, depth
            quality = np.mean([s.get("relevance", 50), s.get("clarity", 50), s.get("technical_depth", 50)])
        ce_samples.append({
            "question": s["question"],
            "answer": s["answer"],
            "overall_quality": float(quality),
        })

    # Try to generate or load extra data
    if GENERATE_EXTRA_SAMPLES:
        if Path(EXTENDED_DATA_FILE).exists():
            print(f"📂 Loading existing extended data from {EXTENDED_DATA_FILE}")
            with open(EXTENDED_DATA_FILE) as f:
                extended = json.load(f)
            ce_samples = extended["samples"]
        else:
            ce_samples = generate_extra_data(ce_samples)

    # Shuffle and split
    random.seed(SEED)
    random.shuffle(ce_samples)

    split_idx = int(len(ce_samples) * TRAIN_SPLIT)
    train_data = ce_samples[:split_idx]
    test_data = ce_samples[split_idx:]

    print(f"\n📊 Split: {len(train_data)} train / {len(test_data)} test")

    # Create InputExamples for sentence-transformers
    train_examples = [
        InputExample(
            texts=[s["question"], s["answer"]],
            label=float(s["overall_quality"]) / 100.0,  # Normalize to [0, 1]
        )
        for s in train_data
    ]

    return train_examples, test_data


# ─── Training ────────────────────────────────────────────────────────────────

def train_cross_encoder(train_examples: list) -> CrossEncoder:
    """Fine-tune the cross-encoder model."""
    print(f"\n🚀 Fine-tuning Cross-Encoder")
    print(f"   Base model: {BASE_MODEL}")
    print(f"   Epochs: {EPOCHS} | Batch: {BATCH_SIZE} | LR: {LEARNING_RATE}")
    print(f"   Warmup steps: {WARMUP_STEPS}")
    print(f"   Training examples: {len(train_examples)}")
    print("=" * 60)

    model = CrossEncoder(BASE_MODEL, num_labels=1)

    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=BATCH_SIZE,
    )

    model.fit(
        train_dataloader=train_dataloader,
        epochs=EPOCHS,
        warmup_steps=WARMUP_STEPS,
        optimizer_params={"lr": LEARNING_RATE},
        output_path=CHECKPOINT_DIR,
        show_progress_bar=True,
    )

    print(f"\n✅ Model fine-tuned and saved to {CHECKPOINT_DIR}")
    return model


# ─── Evaluation & Comparison ─────────────────────────────────────────────────

def evaluate_model(model: CrossEncoder, test_data: list) -> dict:
    """Evaluate cross-encoder on test set."""
    pairs = [(s["question"], s["answer"]) for s in test_data]
    true_scores = [s["overall_quality"] / 100.0 for s in test_data]

    pred_scores = model.predict(pairs).tolist()

    # Spearman correlation
    rho, p_value = spearmanr(pred_scores, true_scores)

    # MSE
    mse = float(np.mean((np.array(pred_scores) - np.array(true_scores)) ** 2))

    return {
        "spearman_rho": float(rho),
        "spearman_p": float(p_value),
        "mse": mse,
        "n_samples": len(test_data),
    }


def run_comparison_experiment(model: CrossEncoder, test_data: list):
    """
    Compare 3 approaches on test set:
    1. Cross-Encoder (fine-tuned)
    2. Cross-Encoder (base, no fine-tuning)
    3. LLM-as-Judge baseline (Groq direct scoring)
    """
    print("\n" + "=" * 70)
    print("  📊 Comparison Experiment: Cross-Encoder vs. Baselines")
    print("=" * 70)

    results = {}

    # 1. Fine-tuned Cross-Encoder
    print("\n  🔬 Evaluating: Fine-tuned Cross-Encoder...")
    finetuned_results = evaluate_model(model, test_data)
    results["Cross-Encoder (fine-tuned)"] = finetuned_results
    print(f"     Spearman ρ = {finetuned_results['spearman_rho']:.4f} "
          f"(p = {finetuned_results['spearman_p']:.4f})")

    # 2. Base Cross-Encoder (no fine-tuning)
    print("\n  🔬 Evaluating: Base Cross-Encoder (no fine-tuning)...")
    try:
        base_model = CrossEncoder(BASE_MODEL, num_labels=1)
        base_results = evaluate_model(base_model, test_data)
        results["Cross-Encoder (base)"] = base_results
        print(f"     Spearman ρ = {base_results['spearman_rho']:.4f} "
              f"(p = {base_results['spearman_p']:.4f})")
    except Exception as e:
        print(f"     ⚠️  Failed: {e}")
        results["Cross-Encoder (base)"] = {"spearman_rho": "N/A", "mse": "N/A"}

    # 3. LLM-as-Judge baseline (on subset to save API calls)
    print("\n  🔬 Evaluating: LLM-as-Judge baseline...")
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model="llama-3.3-70b-versatile",
                openai_api_key=api_key,
                openai_api_base="https://api.groq.com/openai/v1",
                temperature=0.0,
            )

            # Use subset to save API calls
            subset = test_data[:min(50, len(test_data))]
            llm_preds = []
            true_subset = [s["overall_quality"] / 100.0 for s in subset]

            for s in subset:
                prompt = (
                    f"Rate this interview answer quality 0-100. "
                    f"Question: {s['question']}\nAnswer: {s['answer']}\n"
                    f"Return ONLY a number."
                )
                try:
                    resp = llm.invoke(prompt)
                    score = float(resp.content.strip().split()[0]) / 100.0
                    llm_preds.append(np.clip(score, 0, 1))
                    time.sleep(1.0)
                except:
                    llm_preds.append(0.5)

            rho, p = spearmanr(llm_preds, true_subset)
            mse = float(np.mean((np.array(llm_preds) - np.array(true_subset)) ** 2))
            results["LLM-as-Judge (Groq)"] = {
                "spearman_rho": float(rho),
                "spearman_p": float(p),
                "mse": mse,
                "n_samples": len(subset),
            }
            print(f"     Spearman ρ = {rho:.4f} (p = {p:.4f}) [on {len(subset)} samples]")

        except Exception as e:
            print(f"     ⚠️  LLM baseline failed: {e}")
            results["LLM-as-Judge (Groq)"] = {"spearman_rho": "N/A", "mse": "N/A"}
    else:
        print("     ⚠️  GROQ_API_KEY not set — skipping LLM baseline")
        results["LLM-as-Judge (Groq)"] = {"spearman_rho": "N/A (no API key)", "mse": "N/A"}

    # Print comparison table
    print("\n" + "=" * 70)
    print("  📋 Results Comparison Table")
    print("=" * 70)
    print(f"\n  {'Method':<30} {'Spearman ρ':>12} {'MSE':>10} {'N':>6}")
    print(f"  {'-'*60}")

    for method, res in results.items():
        rho_str = f"{res['spearman_rho']:.4f}" if isinstance(res.get("spearman_rho"), float) else str(res.get("spearman_rho", "N/A"))
        mse_str = f"{res['mse']:.4f}" if isinstance(res.get("mse"), float) else str(res.get("mse", "N/A"))
        n_str = str(res.get("n_samples", "N/A"))
        print(f"  {method:<30} {rho_str:>12} {mse_str:>10} {n_str:>6}")

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_path = os.path.join(RESULTS_DIR, "cross_encoder_comparison.json")
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": {k: {kk: str(vv) for kk, vv in v.items()} for k, v in results.items()},
        }, f, indent=2)
    print(f"\n  💾 Results saved to {results_path}")

    return results


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🎯 Cross-Encoder Answer Quality Scorer Training")
    print("=" * 60)

    # Load and prepare data
    train_examples, test_data = load_and_prepare_data()

    # Train
    model = train_cross_encoder(train_examples)

    # Reload fine-tuned model for evaluation
    finetuned_model = CrossEncoder(CHECKPOINT_DIR, num_labels=1)

    # Run comparison experiment
    run_comparison_experiment(finetuned_model, test_data)

    print(f"\n✅ Cross-encoder training complete!")
    print(f"   Checkpoint: {CHECKPOINT_DIR}")
    print(f"   Next step: python training/preprocessing.py")


if __name__ == "__main__":
    main()
