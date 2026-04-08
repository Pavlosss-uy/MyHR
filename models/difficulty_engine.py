import torch
import torch.nn as nn
import torch.nn.functional as F

class AdaptiveDifficultyEngine(nn.Module):
    def __init__(self):
        super(AdaptiveDifficultyEngine, self).__init__()
        
        # Policy Network: 3 inputs -> 16 hidden -> 5 difficulty levels
        # Inputs: [avg_score_normalized, score_trend, current_difficulty_normalized]
        self.policy_net = nn.Sequential(
            nn.Linear(3, 16),
            nn.ReLU(),
            nn.Linear(16, 5) 
            # We don't use Softmax here directly because PyTorch's CrossEntropyLoss/Gumbel-Softmax handles it better
        )

    def forward(self, state_features):
        """Passes the state through the policy network to get difficulty logits."""
        return self.policy_net(state_features)

    def decide_next_difficulty(self, score_history, current_difficulty):
        """
        Calculates the next optimal difficulty (1 to 5) based on the interview history.
        """
        self.eval()
        
        # 1. Handle edge case: First question of the interview
        if not score_history:
            return 3 # Start at medium difficulty
            
        # 2. Calculate state features
        # Normalize score (0-100 to 0.0-1.0)
        avg_score = sum(score_history) / len(score_history)
        avg_score_norm = avg_score / 100.0
        
        # Calculate trend (-1.0 to 1.0). Are they getting better or worse?
        if len(score_history) >= 2:
            trend = (score_history[-1] - score_history[-2]) / 100.0
        else:
            trend = 0.0
            
        # Normalize current difficulty (1-5 to 0.0-1.0)
        current_diff_norm = (current_difficulty - 1) / 4.0
        
        # 3. Create the input state tensor
        state = torch.tensor([[avg_score_norm, trend, current_diff_norm]], dtype=torch.float32)
        
        # 4. Predict the next difficulty
        with torch.no_grad():
            logits = self.forward(state)
            probabilities = F.softmax(logits, dim=-1)
            
            # Get the index with the highest probability (0 to 4) and map to levels 1 to 5
            next_difficulty = torch.argmax(probabilities, dim=-1).item() + 1
            
        return next_difficulty, probabilities.squeeze().tolist()