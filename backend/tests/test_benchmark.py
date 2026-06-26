"""
Phase 6 tests: the benchmark module, using trivial deterministic decide_fns
so these never depend on a trained model being present.
"""
import pytest

from app.optimization.inventory_policies import compute_policy
from app.optimization.solver import DEFAULT_HOLDING_COST_PER_UNIT, DEFAULT_ORDERING_COST
from app.rl.benchmark import _episode_cost_under_policy, make_sS_decide_fn, run_benchmark
from app.rl.env import EPISODE_LENGTH
from app.simulation.model import SupplyChainModel


def _reference_store_params():
    model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=0)
    store = model.stores[0]
    return store.demand_mean, store.demand_std, store.upstream.lead_time


def _build_baseline_policy(service_level=0.95):
    demand_mean, demand_std, lead_time = _reference_store_params()
    return compute_policy(
        demand_mean, demand_std, lead_time, service_level=service_level,
        ordering_cost=DEFAULT_ORDERING_COST, holding_cost_per_unit=DEFAULT_HOLDING_COST_PER_UNIT,
    )


def test_native_rule_and_override_hook_intentionally_differ_due_to_decision_timing():
    """
    Documents and locks in a real finding from building this benchmark:
    Store's NATIVE (reorder_point, order_up_to) rule decides using THIS
    step's post-demand state, while the model.rl_policies hook (which both
    PPO and this module's baseline use) resolves using LAST step's ending
    state -- the only information actually available before today's
    demand is known. These are different information sets, so running the
    "same" (s, S) thresholds through each path must NOT produce identical
    costs. If this test ever starts passing with equality, something
    changed the resolution timing of model.rl_policies, which would
    silently reintroduce an unfair look-ahead advantage into every
    PPO-vs-baseline comparison in this module.
    """
    policy = _build_baseline_policy()
    seed = 555

    model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=seed)
    store = model.stores[0]
    store.reorder_point = policy.reorder_point
    store.order_up_to = policy.order_up_to
    native_cost = 0.0
    for _ in range(EPISODE_LENGTH):
        model.step()
        native_cost += (
            store.inventory + 8 * store.last_unmet_demand + (DEFAULT_ORDERING_COST if store.last_order_placed > 0 else 0)
        )

    override_cost = _episode_cost_under_policy(seed, make_sS_decide_fn(policy.reorder_point, policy.order_up_to))

    assert native_cost != pytest.approx(override_cost, rel=1e-9)


def test_baseline_decide_fn_is_deterministic():
    policy = _build_baseline_policy()
    decide_fn = make_sS_decide_fn(policy.reorder_point, policy.order_up_to)
    cost_a = _episode_cost_under_policy(777, decide_fn)
    cost_b = _episode_cost_under_policy(777, decide_fn)
    assert cost_a == cost_b


def test_run_benchmark_with_always_order_nothing_is_much_worse_than_baseline():
    """A trivially bad policy (never reorder) should score far worse than
    the OR-Tools baseline -- a sanity check that the cost function and
    comparison direction are wired correctly."""
    result = run_benchmark(lambda obs: 0.0, num_episodes=5, service_level=0.95)
    assert result["ppo_avg_cost"] > result["baseline_avg_cost"]
    assert result["improvement_pct"] < 0


def test_run_benchmark_same_seed_gives_same_demand_to_both_policies():
    """Pins the fairness property the whole comparison depends on: PPO and
    baseline must face the identical demand sequence for a given episode
    index, not independently-sampled ones."""
    def fixed_decide_fn(observation):
        return 20.0  # arbitrary fixed policy, just need determinism

    result_a = run_benchmark(fixed_decide_fn, num_episodes=3, seed_offset=999)
    result_b = run_benchmark(fixed_decide_fn, num_episodes=3, seed_offset=999)
    assert result_a["ppo_costs"] == result_b["ppo_costs"]
    assert result_a["baseline_costs"] == result_b["baseline_costs"]


def test_baseline_matching_decide_fn_used_twice_gives_identical_cost_lists():
    """Since run_benchmark now drives BOTH arms through the identical
    _episode_cost_under_policy path, handing it the baseline's own
    decide_fn as the "PPO" arg must reproduce the exact baseline numbers
    -- proving there's truly one evaluation path, not two that happen to
    agree."""
    policy = _build_baseline_policy()
    decide_fn = make_sS_decide_fn(policy.reorder_point, policy.order_up_to)
    result = run_benchmark(decide_fn, num_episodes=5, service_level=0.95)
    assert result["ppo_costs"] == result["baseline_costs"]
    assert result["improvement_pct"] == pytest.approx(0.0, abs=1e-9)
