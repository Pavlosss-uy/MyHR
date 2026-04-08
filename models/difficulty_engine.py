import torch
import torch.nn as nn
import torch.nn.functional as F


class AdaptiveDifficultyEngine(nn.Module):
    def __init__(self, state_dim: int = 6):
        """
        Policy network for adaptive interview difficulty selection.

        Args:
            state_dim: Observation dimension. Use 6 (full InterviewEnv obs)
                       or 3 (legacy: avg_score, trend, current_diff only).
                       Default is 6 to match InterviewEnv.observation_space.

        State vector (6-D, from InterviewEnv._get_obs):
          [0] avg_score_norm          - running mean score / 100
          [1] trend                   - score change (clipped, normalised)
          [2] current_diff_norm       - last difficulty used / 5
          [3] engagement              - candidate engagement [0.3, 1.0]
          [4] topic_diversity         - unique difficulties tried / 5
          [5] questions_remaining_norm- fraction of questions left
        """
        super(AdaptiveDifficultyEngine, self).__init__()
        self.state_dim = state_dim

        # Policy Network: state_dim -> 16 -> 5 difficulty levels
        self.policy_net = nn.Sequential(
            nn.Linear(state_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 5),
        )

    def forward(self, state_features):
        """Return difficulty logits given state tensor."""
        return self.policy_net(state_features)

    def decide_next_difficulty(self, score_history, current_difficulty,
                               engagement: float = 0.8,
                               topic_diversity: float = 0.2,
                               questions_remaining_norm: float = 0.5):
        """
        Select next difficulty level (1-5) from state.

        For backward compatibility the method still works with 3 scalar
        inputs (score_history, current_difficulty) and optional extras.
        Internally it builds the full 6-D state if state_dim == 6.

        Returns:
            (next_difficulty: int, probabilities: list[float])
            On the very first call (empty score_history) returns (3, uniform).
        """
        self.eval()

        if not score_history:
            return 3, [0.2, 0.2, 0.2, 0.2, 0.2]

        avg_score      = sum(score_history) / len(score_history)
        avg_score_norm = avg_score / 100.0

        trend = ((score_history[-1] - score_history[-2]) / 100.0
                 if len(score_history) >= 2 else 0.0)

        current_diff_norm = (current_difficulty - 1) / 4.0

        if self.state_dim == 6:
            state_vec = [
                avg_score_norm,
                float((trend + 1.0) / 2.0),   # normalise to [0, 1]
                current_diff_norm,
                float(engagement),
                float(topic_diversity),
                float(questions_remaining_norm),
            ]
        else:
            # Legacy 3-D mode
            state_vec = [avg_score_norm, trend, current_diff_norm]

        state = torch.tensor([state_vec], dtype=torch.float32)

        with torch.no_grad():
            logits        = self.forward(state)
            probabilities = F.softmax(logits, dim=-1)
            next_difficulty = torch.argmax(probabilities, dim=-1).item() + 1

        return next_difficulty, probabilities.squeeze().tolist()