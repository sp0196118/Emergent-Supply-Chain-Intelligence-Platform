"""
Phase 6 tests: PPOStorePolicy loading and inference. Requires the trained
model artifacts to exist (app/rl/models/), produced by `python -m app.rl.train`.
"""
import pytest

from app.rl.env import ORDER_QUANTITY_BINS
from app.rl.policy import PPOStorePolicy, get_policy


def test_get_policy_returns_a_singleton():
    a = get_policy()
    b = get_policy()
    assert a is b


def test_decide_returns_a_value_from_the_action_bins():
    policy = get_policy()
    decision = policy.decide([80.0, 80.0, 10.0, 3.0, 0.0])
    assert decision in ORDER_QUANTITY_BINS


def test_decide_is_deterministic_for_the_same_observation():
    policy = get_policy()
    obs = [15.0, 15.0, 10.0, 3.0, 11.0]
    assert policy.decide(obs) == policy.decide(obs)


def test_missing_model_files_raise_clear_error():
    with pytest.raises(FileNotFoundError):
        PPOStorePolicy(model_path="/tmp/does_not_exist.zip", vecnorm_path="/tmp/also_missing.pkl")


def test_decide_is_directly_usable_as_an_rl_policies_callable():
    """policy.decide must match the Callable[[List[float]], float] shape
    SupplyChainModel.rl_policies expects -- this is the whole point of the
    interface, so a live run can do model.rl_policies[name] = policy.decide
    with no wrapper needed."""
    from app.simulation.model import SupplyChainModel

    policy = get_policy()
    model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=0)
    store = model.stores[0]
    model.rl_policies[store.name] = policy.decide

    for _ in range(5):
        model.step()  # must not raise
    assert store.last_order_placed in ORDER_QUANTITY_BINS
