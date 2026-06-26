"""
Benchmark: a trained PPO policy vs. Phase 5's OR-Tools-style fixed (s, S)
rule, on the SAME store, SAME network, SAME demand draws (matched seeds).

This directly applies the lesson from Phase 5's baseline-fairness
postmortem: PPO's policy is genuinely richer (it can react every step,
not just at fixed thresholds), so the comparison only means something if
everything else — network, demand sequence, cost function — is held
identical between the two runs.

The fixed-policy baseline's (reorder_point, order_up_to) is computed from
the SAME store's actual demand_mean/demand_std/lead_time (read off a live
model instance, not hardcoded), via the exact compute_policy function
Phase 5 uses — so this is a genuine same-cost-function, same-formula
baseline, not an approximation of one.
"""
from typing import Callable, Dict, List

from app.optimization.inventory_policies import compute_policy
from app.optimization.solver import (
    DEFAULT_HOLDING_COST_PER_UNIT,
    DEFAULT_ORDERING_COST,
    DEFAULT_STOCKOUT_COST_PER_UNIT,
)
from app.rl.env import EPISODE_LENGTH
from app.simulation.model import SupplyChainModel

DecideFn = Callable[[List[float]], float]


def make_sS_decide_fn(reorder_point: float, order_up_to: float) -> DecideFn:
    """An (s, S) rule expressed as a decide_fn, so it can be driven through
    the exact same model.rl_policies hook PPO uses. This matters: Store's
    NATIVE (reorder_point, order_up_to) rule decides using THIS step's
    post-demand state (it runs after experience_demand in the staged
    loop), while the rl_policies hook resolves using LAST step's ending
    state (before this step's events) -- the only information a real
    decision-maker actually has before today's demand is known. Those are
    genuinely different information sets, not the same rule expressed two
    ways; comparing PPO against the native rule directly would silently
    give the native rule a one-step look-ahead PPO never gets. Routing
    both through this same hook removes that asymmetry by construction.
    (Found via tests/test_benchmark.py while building this -- the first
    version of this module compared against the native rule directly and
    the two costs didn't match, which is what surfaced the timing gap.)
    """

    def decide_fn(observation: List[float]) -> float:
        _, position, _, _, _ = observation
        return max(order_up_to - position, 0.0) if position <= reorder_point else 0.0

    return decide_fn


def _episode_cost_under_policy(seed: int, decide_fn: DecideFn) -> float:
    """Drives the SAME model class through the SAME model.rl_policies hook
    live inference uses (see SupplyChainModel.step()) for whichever
    decide_fn is supplied -- PPO's or the (s, S) rule's. Using the actual
    serving path here means this benchmark result is what production
    would actually produce, not an approximation of it, and guarantees
    both policies are compared under identical decision timing."""
    model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=seed)
    store = model.stores[0]
    model.rl_policies[store.name] = decide_fn

    total_cost = 0.0
    for _ in range(EPISODE_LENGTH):
        model.step()
        order_placed = store.last_order_placed > 0
        total_cost += (
            DEFAULT_HOLDING_COST_PER_UNIT * store.inventory
            + DEFAULT_STOCKOUT_COST_PER_UNIT * store.last_unmet_demand
            + (DEFAULT_ORDERING_COST if order_placed else 0.0)
        )
    return total_cost


def run_benchmark(
    decide_fn: DecideFn,
    num_episodes: int = 20,
    service_level: float = 0.95,
    seed_offset: int = 10_000,
) -> Dict:
    # Read the store's real parameters off a live model instance instead of
    # hardcoding Phase 3's constants a second time here.
    reference_model = SupplyChainModel(num_suppliers=1, num_distribution_centers=1, num_stores=1, seed=0)
    reference_store = reference_model.stores[0]
    lead_time = reference_store.upstream.lead_time

    baseline_policy = compute_policy(
        demand_mean=reference_store.demand_mean,
        demand_std=reference_store.demand_std,
        lead_time=lead_time,
        service_level=service_level,
        ordering_cost=DEFAULT_ORDERING_COST,
        holding_cost_per_unit=DEFAULT_HOLDING_COST_PER_UNIT,
    )
    baseline_decide_fn = make_sS_decide_fn(baseline_policy.reorder_point, baseline_policy.order_up_to)

    ppo_costs: List[float] = []
    baseline_costs: List[float] = []
    for i in range(num_episodes):
        seed = seed_offset + i  # same seed for both -> identical demand draw
        ppo_costs.append(_episode_cost_under_policy(seed, decide_fn))
        baseline_costs.append(_episode_cost_under_policy(seed, baseline_decide_fn))

    ppo_avg = sum(ppo_costs) / len(ppo_costs)
    baseline_avg = sum(baseline_costs) / len(baseline_costs)
    improvement_pct = 100 * (1 - ppo_avg / baseline_avg) if baseline_avg > 0 else 0.0

    return {
        "num_episodes": num_episodes,
        "ppo_avg_cost": ppo_avg,
        "baseline_avg_cost": baseline_avg,
        "baseline_service_level": service_level,
        "baseline_reorder_point": baseline_policy.reorder_point,
        "baseline_order_up_to": baseline_policy.order_up_to,
        "improvement_pct": improvement_pct,
        "ppo_costs": ppo_costs,
        "baseline_costs": baseline_costs,
    }
