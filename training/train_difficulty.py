import torch
import torch.optim as optim
from torch.distributions import Categorical
import os

from models.difficulty_engine import AdaptiveDifficultyEngine
from training.metrics import rl_metrics, make_writer
from training.interview_env import InterviewEnv


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Reinforcement Learning training on {device}...")
    print("State space: 6-D (full InterviewEnv observation)")

    # Use 6-D state to match InterviewEnv.observation_space
    model     = AdaptiveDifficultyEngine(state_dim=6).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    writer    = make_writer("difficulty_engine")
    env       = InterviewEnv(max_questions=5)

    epochs = 2000

    # Accumulate episode data for batch logging every 400 epochs
    batch_rewards = []
    batch_scores  = []

    for epoch in range(epochs):
        obs, _ = env.reset()
        score_history = []
        log_probs     = []
        rewards       = []
        entropies     = []

        for step in range(env.max_questions):
            # Use full 6-D observation from InterviewEnv directly
            state = torch.tensor([obs], dtype=torch.float32).to(device)

            logits = model(state)
            probs  = torch.softmax(logits, dim=-1)
            m      = Categorical(probs)
            action = m.sample()

            log_probs.append(m.log_prob(action))
            entropies.append(m.entropy())

            # Use the environment's multi-objective reward directly
            obs, reward, terminated, _, info = env.step(action.item())
            actual_score = info["score"]
            score_history.append(actual_score)
            rewards.append(reward)

            if terminated:
                break

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
    torch.save(model.state_dict(), "models/checkpoints/difficulty_engine_v2.pt")
    print("\nRL Checkpoint saved: models/checkpoints/difficulty_engine_v2.pt")

    # Quick inference test
    print("\n--- Quick Inference Test (6-D state) ---")
    test_history_smart = [95, 92]
    next_diff_smart, _ = model.decide_next_difficulty(
        test_history_smart, 2, engagement=0.9, topic_diversity=0.4,
        questions_remaining_norm=0.4)
    print(f"Candidate acing questions (95, 92) -> Next Difficulty: {next_diff_smart}")

    test_history_struggling = [30, 25]
    next_diff_struggling, _ = model.decide_next_difficulty(
        test_history_struggling, 4, engagement=0.5, topic_diversity=0.2,
        questions_remaining_norm=0.6)
    print(f"Candidate struggling (30, 25) -> Next Difficulty: {next_diff_struggling}")


if __name__ == "__main__":
    main()
