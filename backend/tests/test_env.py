"""
Phase 6 tests: the Gym environment, independent of any trained model.
"""
import numpy as np
from stable_baselines3.common.env_checker import check_env

from app.rl.env import EPISODE_LENGTH, ORDER_QUANTITY_BINS, SupplyChainEnv


def test_env_passes_sb3_check_env():
    """Permanent regression test for the manual check_env pass done while
    building this — catches API/shape mismatches automatically."""
    check_env(SupplyChainEnv(seed=0), warn=True)


def test_reset_returns_expected_observation_shape():
    env = SupplyChainEnv(seed=0)
    obs, info = env.reset(seed=0)
    assert obs.shape == (5,)
    assert obs.dtype == np.float32


def test_zero_action_places_no_order():
    env = SupplyChainEnv(seed=1)
    env.reset(seed=1)
    zero_action_index = ORDER_QUANTITY_BINS.index(0.0)
    env.step(zero_action_index)
    assert env.store.last_order_placed == 0.0


def test_nonzero_action_places_an_order_of_that_quantity():
    env = SupplyChainEnv(seed=1)
    env.reset(seed=1)
    action_index = ORDER_QUANTITY_BINS.index(30.0)
    env.step(action_index)
    assert env.store.last_order_placed == 30.0


def test_episode_truncates_at_episode_length():
    env = SupplyChainEnv(seed=2)
    env.reset(seed=2)
    truncated = False
    steps = 0
    while not truncated and steps < EPISODE_LENGTH + 5:
        _, _, terminated, truncated, _ = env.step(0)
        steps += 1
    assert truncated
    assert steps == EPISODE_LENGTH
    assert not terminated  # this env never "terminates" early, only truncates on length


def test_reward_is_never_positive():
    """Reward is a pure cost (holding + stockout + ordering), so it should
    never reward the agent for anything -- only penalize it less."""
    env = SupplyChainEnv(seed=3)
    env.reset(seed=3)
    for _ in range(20):
        _, reward, _, _, _ = env.step(env.action_space.sample())
        assert reward <= 0
