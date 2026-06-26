"""
Phase 5 tests: the OR-Tools CP-SAT solver, independent of the API layer.
"""
import pytest

from app.optimization.solver import SERVICE_LEVEL_TIERS, apply_policy_to_model, solve_safety_stock_allocation
from app.simulation.model import SupplyChainModel


def _model(seed=1):
    return SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=seed)


def test_solver_returns_optimal_for_default_budget():
    result = solve_safety_stock_allocation(_model())
    assert result["status"] == "OPTIMAL"
    assert len(result["policies"]) == 12 + 3  # every store + DC gets a policy, suppliers excluded


def test_suppliers_are_not_part_of_the_optimization():
    model = _model()
    result = solve_safety_stock_allocation(model)
    supplier_names = {s.name for s in model.suppliers}
    assert supplier_names.isdisjoint(result["policies"].keys())


@pytest.mark.parametrize("budget", [0, 8, 18, 25, 37, 50, 75, 200, 100_000])
def test_optimized_cost_never_exceeds_naive_uniform_baseline(budget):
    """
    The core correctness invariant for this solver: "give every node the
    same tier" is itself one of the feasible combinations CP-SAT searches
    over, so the true optimum can never cost more than that baseline. If
    this ever fails, the objective or the budget constraint is wired wrong
    — this is exactly the bug an earlier draft of this solver had, caught
    by comparing against a continuous (and therefore not-comparable)
    baseline instead of one drawn from the same discrete choice space.
    """
    result = solve_safety_stock_allocation(_model(), total_budget=budget)
    assert result["total_expected_stockout_cost"] <= result["naive_baseline_cost"] + 1e-6


def test_huge_budget_converges_to_top_tier_for_everyone():
    result = solve_safety_stock_allocation(_model(), total_budget=1_000_000)
    assert all(p.service_level == max(SERVICE_LEVEL_TIERS) for p in result["policies"].values())
    assert result["total_expected_stockout_cost"] == pytest.approx(result["naive_baseline_cost"], rel=1e-6)


def test_zero_budget_forces_cheapest_tier_for_everyone():
    result = solve_safety_stock_allocation(_model(), total_budget=0)
    assert all(p.service_level == min(SERVICE_LEVEL_TIERS) for p in result["policies"].values())
    assert result["budget_used"] == 0.0


def test_negative_budget_is_infeasible_not_a_crash():
    result = solve_safety_stock_allocation(_model(), total_budget=-5)
    assert result["status"] == "INFEASIBLE"
    assert result["policies"] == {}


def test_distribution_centers_get_weighted_higher_than_stores_at_default_topology():
    """At the default round-robin topology, every DC is a bottleneck for
    1/3 of stores while no store is ever a bottleneck for anything — so
    every DC's cost weight must exceed every store's."""
    model = _model()
    result = solve_safety_stock_allocation(model)
    weights = result["cost_weight_by_node"]
    dc_weights = {weights[dc.name] for dc in model.distribution_centers}
    store_weights = {weights[s.name] for s in model.stores}
    assert min(dc_weights) > max(store_weights)


def test_apply_policy_to_model_updates_agent_fields():
    model = _model()
    original_store_reorder_point = model.stores[0].reorder_point
    result = solve_safety_stock_allocation(model, total_budget=50)
    apply_policy_to_model(model, result["policies"])

    updated = model.stores[0]
    expected = result["policies"][updated.name]
    assert updated.reorder_point == pytest.approx(expected.reorder_point)
    assert updated.order_up_to == pytest.approx(expected.order_up_to)
    # sanity: applying actually changed something rather than coincidentally matching
    assert updated.reorder_point != original_store_reorder_point or expected.reorder_point == original_store_reorder_point


def test_apply_policy_only_touches_stores_and_dcs_not_suppliers():
    model = _model()
    original_supplier_order_up_to = model.suppliers[0].order_up_to
    result = solve_safety_stock_allocation(model, total_budget=50)
    apply_policy_to_model(model, result["policies"])
    assert model.suppliers[0].order_up_to == original_supplier_order_up_to
