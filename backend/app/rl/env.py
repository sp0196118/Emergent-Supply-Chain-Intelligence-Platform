"""
Gym-style environment wrapping the Mesa simulation.

Scope, deliberately narrow: PPO controls ONE store's order quantity per
step, directly (bypassing the (reorder_point, order_up_to) rule entirely),
embedded in a minimal 1-supplier/1-DC/1-store network. That isolates the
single-store replenishment decision cleanly and trains fast; since every
store in the default network shares the same demand profile (Phase 3), a
policy learned here generalizes to any of them without retraining.

Observation: Store.build_observation() — [inventory, inventory_position,
demand_mean, demand_std, last_demand]. Defined on Store itself (Phase 3/6),
not duplicated here, so training and live inference can never drift apart.

Action: discrete index into ORDER_QUANTITY_BINS — "how many units to order
this step", a direct, fully adaptive policy (no separate (s, S) concept).

Reward: -holding_cost - stockout_cost - ordering_cost, using the EXACT SAME
cost constants as Phase 5's solver (imported, not re-declared), so PPO and
OR-Tools are judged on an identical cost function. That comparability is
the entire point of this phase, and Phase 5's postmortem on baseline
fairness is exactly the lesson being applied here.
"""
from typing import List, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.optimization.solver import (
    DEFAULT_HOLDING_COST_PER_UNIT,
    DEFAULT_ORDERING_COST,
    DEFAULT_STOCKOUT_COST_PER_UNIT,
)
from app.simulation.model import SupplyChainModel

ORDER_QUANTITY_BINS: List[float] = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
EPISODE_LENGTH = 60

# Observation bounds, generous enough to never clip in practice but tight
# enough to actually help PPO's input normalization.
OBS_LOW = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
OBS_HIGH = np.array([500.0, 500.0, 50.0, 20.0, 100.0], dtype=np.float32)


class SupplyChainEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, seed: Optional[int] = None):
        super().__init__()
        self.action_space = spaces.Discrete(len(ORDER_QUANTITY_BINS))
        self.observation_space = spaces.Box(low=OBS_LOW, high=OBS_HIGH, dtype=np.float32)
        self._episode_seed = seed
        self._rng_counter = 0
        self.model: Optional[SupplyChainModel] = None
        self.store = None
        self._step_count = 0

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        # Vary the model seed across episodes (unless the caller pinned one)
        # so PPO doesn't overfit a single demand trajectory.
        model_seed = seed if seed is not None else self._episode_seed
        if model_seed is None:
            model_seed = self._rng_counter
            self._rng_counter += 1

        self.model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=model_seed)
        self.store = self.model.stores[0]
        self._step_count = 0

        return self._observation(), {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        assert self.model is not None, "call reset() before step()"
        order_qty = ORDER_QUANTITY_BINS[int(action)]
        self.store.external_order_override = order_qty

        self.model.step()
        self._step_count += 1

        reward = self._reward(order_placed=order_qty > 0)
        terminated = False
        truncated = self._step_count >= EPISODE_LENGTH

        return self._observation(), reward, terminated, truncated, {}

    def _observation(self) -> np.ndarray:
        return np.array(self.store.build_observation(), dtype=np.float32)

    def _reward(self, order_placed: bool) -> float:
        holding_cost = DEFAULT_HOLDING_COST_PER_UNIT * self.store.inventory
        stockout_cost = DEFAULT_STOCKOUT_COST_PER_UNIT * self.store.last_unmet_demand
        ordering_cost = DEFAULT_ORDERING_COST if order_placed else 0.0
        return -(holding_cost + stockout_cost + ordering_cost)
