"""
Loads the trained PPO policy for inference and exposes a simple
`decide(observation) -> order_qty` interface — used both by
SupplyChainModel.step() (via model.rl_policies, for live simulation) and
by routes/rl.py (for one-off decisions via the API).

Must load and apply the SAME VecNormalize observation statistics that were
used during training (app/rl/train.py) — the policy network was trained on
normalized inputs, so handing it raw inventory/demand numbers directly
would silently feed it a different input distribution than it learned on.
"""
import os
from typing import List, Optional

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from app.rl.env import ORDER_QUANTITY_BINS, SupplyChainEnv
from app.rl.train import MODEL_PATH, VECNORM_PATH


class PPOStorePolicy:
    def __init__(self, model_path: str = MODEL_PATH, vecnorm_path: str = VECNORM_PATH):
        if not os.path.exists(model_path) or not os.path.exists(vecnorm_path):
            raise FileNotFoundError(
                f"No trained policy found at {model_path}. Run `python -m app.rl.train` first."
            )
        dummy_env = DummyVecEnv([lambda: SupplyChainEnv()])
        self._vec_normalize = VecNormalize.load(vecnorm_path, dummy_env)
        self._vec_normalize.training = False
        self._vec_normalize.norm_reward = False
        self.model = PPO.load(model_path)

    def decide(self, observation: List[float]) -> float:
        obs = np.array(observation, dtype=np.float32).reshape(1, -1)
        norm_obs = self._vec_normalize.normalize_obs(obs)
        action, _ = self.model.predict(norm_obs, deterministic=True)
        return ORDER_QUANTITY_BINS[int(action[0])]


_singleton: Optional[PPOStorePolicy] = None


def get_policy() -> PPOStorePolicy:
    """Lazy singleton — loading the model/normalization stats from disk is
    not free, and routes/rl.py may be called many times per run."""
    global _singleton
    if _singleton is None:
        _singleton = PPOStorePolicy()
    return _singleton
