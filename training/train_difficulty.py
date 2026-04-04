import torch
import torch.optim as optim
from torch.distributions import Categorical
import os
import random

from models.difficulty_engine import AdaptiveDifficultyEngine

def simulate_candidate_answer(difficulty, candidate_skill):
    """
    Simulates candidate score based on the GAP between their hidden skill and the difficulty.
    If skill == difficulty, they score around 65.
    If skill > difficulty, they score higher.
    If skill < difficulty, they score lower.
    """
    diff_gap = candidate_skill - difficulty
    # Each gap point shifts the score by ~15 points
    base_score = 65 + (diff_gap * 15)
    
    # Add some randomness
    actual_score = base_score + random.uniform(-10, 10)
    
    # Clamp to strictly between 0 and 100
    return max(0, min(100, actual_score))

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Reinforcement Learning training on {device}...")

    model = AdaptiveDifficultyEngine().to(device)
    # Lowered learning rate slightly for smoother learning
    optimizer = optim.Adam(model.parameters(), lr=0.005) 

    epochs = 2000 
    target_score = 65.0 

    for epoch in range(epochs):
        score_history = []
        log_probs = []
        rewards = []
        entropies = [] 
        current_difficulty = 3
        
        # FIX: Randomly assign the candidate a hidden skill level (1 to 5) for this interview
        candidate_skill = random.choice([1, 2, 3, 4, 5])

        for step in range(5):
            avg_score = sum(score_history) / len(score_history) if score_history else target_score
            avg_score_norm = avg_score / 100.0
            
            trend = (score_history[-1] - score_history[-2]) / 100.0 if len(score_history) >= 2 else 0.0
            current_diff_norm = (current_difficulty - 1) / 4.0
            
            state = torch.tensor([[avg_score_norm, trend, current_diff_norm]], dtype=torch.float32).to(device)
            
            logits = model(state)
            probs = torch.softmax(logits, dim=-1)
            
            m = Categorical(probs)
            action_index = m.sample()
            current_difficulty = action_index.item() + 1
            
            log_probs.append(m.log_prob(action_index))
            entropies.append(m.entropy())
            
            # Pass BOTH the difficulty and the candidate's actual skill to the simulation
            actual_score = simulate_candidate_answer(current_difficulty, candidate_skill)
            score_history.append(actual_score)
            
            reward = -abs(actual_score - target_score)
            rewards.append(reward)

        optimizer.zero_grad()
        
        # Standardize Rewards
        returns = torch.tensor(rewards)
        returns = (returns - returns.mean()) / (returns.std() + 1e-9)

        policy_loss = []
        for log_prob, R, entropy in zip(log_probs, returns, entropies):
            # Entropy bonus to encourage exploration
            policy_loss.append(-log_prob * R - 0.1 * entropy)
            
        loss = torch.cat(policy_loss).sum()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 400 == 0:
            avg_reward = sum(rewards)/len(rewards)
            print(f"Epoch {epoch+1}/{epochs} | Avg Reward: {avg_reward:.2f} (closer to 0 is better)")

    os.makedirs("models/checkpoints", exist_ok=True)
    torch.save(model.state_dict(), "models/checkpoints/difficulty_engine_v1.pt")
    print("\n--> RL Checkpoint saved: models/checkpoints/difficulty_engine_v1.pt")
    
    print("\n--- Quick Inference Test ---")
    
    test_history_smart = [95, 92] 
    next_diff_smart, _ = model.decide_next_difficulty(test_history_smart, current_difficulty=2)
    print(f"Candidate is acing the questions (95, 92). Engine selected Next Difficulty: Level {next_diff_smart}")
    
    test_history_struggling = [30, 25] 
    next_diff_struggling, _ = model.decide_next_difficulty(test_history_struggling, current_difficulty=4)
    print(f"Candidate is struggling (30, 25). Engine selected Next Difficulty: Level {next_diff_struggling}")

if __name__ == "__main__":
    main()