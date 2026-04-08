"""
PPO-based adaptive difficulty training using the InterviewEnv Gymnasium environment.

Also performs a 3-way comparison:
    1. Rule-based heuristic  (if score > 70 → harder; if score < 50 → easier)
    2. REINFORCE policy       (existing AdaptiveDifficultyEngine checkpoint)
    3. PPO                   (trained here with stable-baselines3)

Results are saved to training/results/difficulty_comparison.json and printed as a table.

Usage:
    python -m training.train_difficulty_ppo          # full run
    python -m training.train_difficulty_ppo --test   # quick test (1000 timesteps)
"""

import os
import json
import argparse
import numpy as np

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback

from training.interview_env import InterviewEnv


# ---------------------------------------------------------------------------
# Train PPO
# ---------------------------------------------------------------------------

def train_ppo(total_timesteps: int = 50_000, save_path: str = "models/checkpoints/difficulty_ppo_v1"):
    print(f"Training PPO for {total_timesteps:,} timesteps...")

    # Vectorised environment (4 parallel workers = faster data collection)
    vec_env = make_vec_env(InterviewEnv, n_envs=4)

    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        tensorboard_log="training/runs/difficulty_ppo",
        learning_rate=3e-4,
        n_steps=128,        # steps per env per update
        batch_size=64,
        n_epochs=10,        # SGD passes per update
        gamma=0.99,
        ent_coef=0.01,      # entropy regularisation (mirrors REINFORCE bonus)
        clip_range=0.2,
    )

    eval_env = InterviewEnv()
    eval_callback = EvalCallback(
        eval_env,
        eval_freq=max(total_timesteps // 10, 1000),
        n_eval_episodes=50,
        verbose=0,
    )

    model.learn(total_timesteps=total_timesteps, callback=eval_callback)

    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
    model.save(save_path)
    print(f"PPO checkpoint saved → {save_path}")

    return model


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _compute_stats(results: list) -> dict:
    """results: list of per-episode score lists"""
    all_scores = [s for episode in results for s in episode]
    return {
        "score_variance":     float(np.var(all_scores)),
        "pct_in_target_zone": float(np.mean([50 <= s <= 80 for s in all_scores]) * 100),
        "mean_score":         float(np.mean(all_scores)),
        "n_episodes":         len(results),
        "n_steps":            len(all_scores),
    }


def run_heuristic(n_simulations: int = 500) -> list:
    """
    Rule-based baseline:
        if score > 70 and difficulty < 5 → increase difficulty
        if score < 50 and difficulty > 1 → decrease difficulty
    """
    env = InterviewEnv()
    results = []

    for _ in range(n_simulations):
        obs, _ = env.reset()
        current_diff = 2  # start at medium
        episode_scores = []

        for _ in range(env.max_questions):
            action = current_diff - 1  # diff level → 0-based action
            obs, reward, terminated, truncated, info = env.step(action)
            episode_scores.append(info["score"])

            if info["score"] > 70 and current_diff < 5:
                current_diff += 1
            elif info["score"] < 50 and current_diff > 1:
                current_diff -= 1

            if terminated or truncated:
                break

        results.append(episode_scores)

    return results


def run_reinforce(n_simulations: int = 500) -> list:
    """
    Use the existing REINFORCE checkpoint (AdaptiveDifficultyEngine).
    Falls back to random policy if checkpoint is missing.
    """
    import torch
    from models.difficulty_engine import AdaptiveDifficultyEngine

    engine = AdaptiveDifficultyEngine()
    checkpoint = "models/checkpoints/difficulty_engine_v1.pt"
    if os.path.exists(checkpoint):
        engine.load_state_dict(
            torch.load(checkpoint, map_location="cpu")
        )
        print(f"Loaded REINFORCE checkpoint: {checkpoint}")
    else:
        print(f"WARNING: {checkpoint} not found — using random REINFORCE policy")

    engine.eval()
    env = InterviewEnv()
    results = []

    for _ in range(n_simulations):
        obs, _ = env.reset()
        episode_scores = []

        with torch.no_grad():
            for _ in range(env.max_questions):
                next_diff, _ = engine.decide_next_difficulty(
                    episode_scores, len(episode_scores) + 1
                )
                action = next_diff - 1  # diff level → 0-based action
                obs, reward, terminated, truncated, info = env.step(action)
                episode_scores.append(info["score"])
                if terminated or truncated:
                    break

        results.append(episode_scores)

    return results


def run_ppo(model, n_simulations: int = 500) -> list:
    env = InterviewEnv()
    results = []

    for _ in range(n_simulations):
        obs, _ = env.reset()
        episode_scores = []
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(int(action))
            episode_scores.append(info["score"])
            done = terminated or truncated

        results.append(episode_scores)

    return results


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def compare_methods(total_timesteps: int = 50_000, n_simulations: int = 500):
    print("\n" + "="*60)
    print("Step 1/4 — Training PPO agent")
    print("="*60)
    ppo_model = train_ppo(total_timesteps=total_timesteps)

    print("\n" + "="*60)
    print("Step 2/4 — Running Heuristic baseline")
    print("="*60)
    heuristic_results = run_heuristic(n_simulations)

    print("\n" + "="*60)
    print("Step 3/4 — Running REINFORCE baseline")
    print("="*60)
    reinforce_results = run_reinforce(n_simulations)

    print("\n" + "="*60)
    print("Step 4/4 — Evaluating PPO")
    print("="*60)
    ppo_results = run_ppo(ppo_model, n_simulations)

    report = {
        "heuristic": _compute_stats(heuristic_results),
        "reinforce":  _compute_stats(reinforce_results),
        "ppo":        _compute_stats(ppo_results),
    }

    # Save results
    os.makedirs("training/results", exist_ok=True)
    out_path = "training/results/difficulty_comparison.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print comparison table
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    header = f"{'Method':<15} {'Variance':>10} {'%In50-80':>10} {'Mean Score':>12}"
    print(header)
    print("-" * len(header))
    for method, stats in report.items():
        print(
            f"{method:<15} "
            f"{stats['score_variance']:>10.2f} "
            f"{stats['pct_in_target_zone']:>10.1f} "
            f"{stats['mean_score']:>12.1f}"
        )
    print(f"\nFull results saved → {out_path}")

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PPO for adaptive interview difficulty")
    parser.add_argument(
        "--test", action="store_true",
        help="Quick test run (1000 PPO timesteps, 20 simulations per method)"
    )
    parser.add_argument(
        "--timesteps", type=int, default=50_000,
        help="PPO training timesteps (default: 50000)"
    )
    parser.add_argument(
        "--simulations", type=int, default=500,
        help="Number of simulations per method for comparison (default: 500)"
    )
    args = parser.parse_args()

    if args.test:
        print("Running in TEST mode...")
        compare_methods(total_timesteps=1_000, n_simulations=20)
    else:
        compare_methods(
            total_timesteps=args.timesteps,
            n_simulations=args.simulations,
        )
