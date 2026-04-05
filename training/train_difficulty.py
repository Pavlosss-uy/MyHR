import torch
import torch.optim as optim
from torch.distributions import Categorical
import os
import random

from models.difficulty_engine import AdaptiveDifficultyEngine
from training.metrics import rl_metrics, make_writer


def simulate_candidate_answer(difficulty, candidate_skill):
    """
    Simulates candidate score based on the gap between their skill and the difficulty.
    skill == difficulty → score ~65
    skill > difficulty  → score higher
    skill < difficulty  → score lower
    """
    diff_gap   = candidate_skill - difficulty
    base_score = 65 + (diff_gap * 15)
    actual     = base_score + random.uniform(-10, 10)
    return max(0.0, min(100.0, actual))


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Reinforcement Learning training on {device}...")

    model     = AdaptiveDifficultyEngine().to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    writer    = make_writer("difficulty_engine")

    epochs       = 2000
    target_score = 65.0

    # Accumulate episode data for batch logging every 400 epochs
    batch_rewards = []
    batch_scores  = []

    for epoch in range(epochs):
        score_history = []
        log_probs     = []
        rewards       = []
        entropies     = []
        current_difficulty = 3
        candidate_skill    = random.choice([1, 2, 3, 4, 5])

        for step in range(5):
            avg_score = (sum(score_history) / len(score_history)
                         if score_history else target_score)
            avg_score_norm   = avg_score / 100.0
            trend            = ((score_history[-1] - score_history[-2]) / 100.0
                                if len(score_history) >= 2 else 0.0)
            current_diff_norm = (current_difficulty - 1) / 4.0

            state  = torch.tensor(
                [[avg_score_norm, trend, current_diff_norm]], dtype=torch.float32
            ).to(device)

            logits = model(state)
            probs  = torch.softmax(logits, dim=-1)
            m      = Categorical(probs)
            action = m.sample()
            current_difficulty = action.item() + 1

            log_probs.append(m.log_prob(action))
            entropies.append(m.entropy())

            actual_score = simulate_candidate_answer(current_difficulty, candidate_skill)
            score_history.append(actual_score)

            reward = -abs(actual_score - target_score)
            rewards.append(reward)

        # Policy gradient update
        optimizer.zero_grad()
        returns = torch.tensor(rewards)
        returns = (returns - returns.mean()) / (returns.std() + 1e-9)

        policy_loss = []
        for log_prob, R, entropy in zip(log_probs, returns, entropies):
            policy_loss.append(-log_prob * R - 0.1 * entropy)

        loss = torch.cat(policy_loss).sum()
        loss.backward()
        optimizer.step()

        # Accumulate for batch logging
        batch_rewards.append(rewards)
        batch_scores.append(score_history)

        # Log every 400 epochs
        if (epoch + 1) % 400 == 0:
            step_num = (epoch + 1) // 400
            metrics  = rl_metrics(batch_rewards, batch_scores)

            writer.add_scalar("Reward/avg",              metrics["avg_reward"],         step_num)
            writer.add_scalar("Score/variance",          metrics["score_variance"],      step_num)
            writer.add_scalar("Score/pct_in_target_zone",metrics["pct_in_target_zone"], step_num)

            print(
                f"Epoch {epoch+1}/{epochs} | "
                f"Avg Reward: {metrics['avg_reward']:.2f}  "
                f"Score Variance: {metrics['score_variance']:.2f}  "
                f"% in 50-80 zone: {metrics['pct_in_target_zone']:.1f}%"
            )

            # Reset batch accumulators
            batch_rewards = []
            batch_scores  = []

    writer.close()
    os.makedirs("models/checkpoints", exist_ok=True)
    torch.save(model.state_dict(), "models/checkpoints/difficulty_engine_v1.pt")
    print("\nRL Checkpoint saved: models/checkpoints/difficulty_engine_v1.pt")

    # Quick inference test
    print("\n--- Quick Inference Test ---")
    test_history_smart = [95, 92]
    next_diff_smart, _ = model.decide_next_difficulty(test_history_smart, 2)
    print(f"Candidate acing questions (95, 92) → Next Difficulty: {next_diff_smart}")

    test_history_struggling = [30, 25]
    next_diff_struggling, _ = model.decide_next_difficulty(test_history_struggling, 4)
    print(f"Candidate struggling (30, 25) → Next Difficulty: {next_diff_struggling}")


if __name__ == "__main__":
    main()
