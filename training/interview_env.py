"""
Gymnasium-compliant interview simulation environment for adaptive difficulty RL.

State (6 floats, all in [0, 1]):
    [avg_score_norm, trend, current_diff_norm, engagement, topic_diversity, questions_remaining_norm]

Action (int 0-4):
    Maps to difficulty level 1-5.

Reward (multi-objective):
    score_reward     = -|score - 65| / 100        (keep candidate near 65%)
    engagement_reward = (engagement - 0.5) * 0.3  (maintain engagement)
    variety_bonus     = 0.05 if more than one difficulty was used

Candidate model:
    base_score = 65 + (skill - difficulty) * 12
    engagement decays with fatigue; hard questions increase fatigue faster.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces


class InterviewEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, max_questions: int = 5):
        super().__init__()
        self.max_questions = max_questions

        # Action: difficulty level 0 → level 1, ..., 4 → level 5
        self.action_space = spaces.Discrete(5)

        # Observation: 6 continuous values in [0, 1]
        self.observation_space = spaces.Box(
            low=np.zeros(6,  dtype=np.float32),
            high=np.ones(6,  dtype=np.float32),
            dtype=np.float32,
        )

        # Episode state (reset on each episode)
        self.candidate_skill    = 3.0
        self.engagement         = 1.0
        self.fatigue            = 0.0
        self.scores             = []
        self.difficulties_used  = set()
        self.step_count         = 0

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Random candidate with hidden skill level [1, 5]
        self.candidate_skill   = float(self.np_random.uniform(1.0, 5.0))
        self.engagement        = 1.0
        self.fatigue           = 0.0
        self.scores            = []
        self.difficulties_used = set()
        self.step_count        = 0

        return self._get_obs(), {}

    def step(self, action: int):
        difficulty = int(action) + 1  # 0-4 → 1-5

        # Simulate candidate response
        skill_gap  = self.candidate_skill - difficulty
        base_score = 65.0 + skill_gap * 12.0

        # Engagement decays each step, amplified by accumulated fatigue
        self.engagement = max(0.3, self.engagement - 0.05 - self.fatigue * 0.02)
        base_score *= self.engagement

        # Fatigue dynamics: hard questions tire the candidate faster
        if difficulty >= 4:
            self.fatigue = min(1.0, self.fatigue + 0.15)
        else:
            self.fatigue = max(0.0, self.fatigue - 0.05)

        # Final score with noise
        score = float(np.clip(
            base_score + self.np_random.normal(0, 8), 0.0, 100.0
        ))

        self.scores.append(score)
        self.difficulties_used.add(difficulty)
        self.step_count += 1

        # Multi-objective reward
        score_reward      = -abs(score - 65.0) / 100.0
        engagement_reward = (self.engagement - 0.5) * 0.3
        variety_bonus     = 0.05 if len(self.difficulties_used) > 1 else 0.0

        reward = score_reward + engagement_reward + variety_bonus

        terminated = self.step_count >= self.max_questions
        truncated  = False
        info       = {
            "score":      score,
            "difficulty": difficulty,
            "engagement": self.engagement,
            "fatigue":    self.fatigue,
        }

        return self._get_obs(), reward, terminated, truncated, info

    def render(self):
        if self.scores:
            print(
                f"Step {self.step_count} | "
                f"Last score: {self.scores[-1]:.1f} | "
                f"Engagement: {self.engagement:.2f} | "
                f"Difficulties used: {sorted(self.difficulties_used)}"
            )

    # ------------------------------------------------------------------
    # Observation construction
    # ------------------------------------------------------------------

    def _get_obs(self) -> np.ndarray:
        # avg_score_norm
        avg_score_norm = float(np.mean(self.scores) / 100.0) if self.scores else 0.5

        # trend — normalised change between last two scores
        if len(self.scores) >= 2:
            raw_trend = (self.scores[-1] - self.scores[-2]) / 100.0
            trend     = float(np.clip((raw_trend + 1.0) / 2.0, 0.0, 1.0))
        else:
            trend = 0.5

        # current difficulty norm (based on last action taken)
        if self.difficulties_used:
            current_diff_norm = float(max(self.difficulties_used)) / 5.0
        else:
            current_diff_norm = 0.5

        topic_diversity         = len(self.difficulties_used) / 5.0
        questions_remaining_norm = 1.0 - (self.step_count / self.max_questions)

        return np.array(
            [
                avg_score_norm,
                trend,
                current_diff_norm,
                float(self.engagement),
                float(topic_diversity),
                float(questions_remaining_norm),
            ],
            dtype=np.float32,
        )


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from gymnasium.utils.env_checker import check_env

    env = InterviewEnv()
    print("Running Gymnasium env_checker...")
    check_env(env, warn=True)
    print("env_checker passed!\n")

    obs, _ = env.reset(seed=42)
    print(f"Initial obs shape: {obs.shape}  dtype: {obs.dtype}")
    print(f"Initial obs: {obs}\n")

    total_reward = 0.0
    for step in range(5):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        print(
            f"Step {step+1}: action={action+1} (diff {info['difficulty']})  "
            f"score={info['score']:.1f}  reward={reward:.4f}  "
            f"engagement={info['engagement']:.3f}"
        )
        if terminated:
            break

    print(f"\nTotal reward: {total_reward:.4f}")
    print(f"Final obs: {obs}")
