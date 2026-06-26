"""
/optimization routes.

Phase 5 update: solve() runs a real OR-Tools CP-SAT solver
(app/optimization/solver.py) that allocates a safety-stock budget across
every Store and DistributionCenter, weighted by Phase 4's network-criticality
score, then APPLIES the result to the live model's agents — any simulation
steps run after this call use the optimized (reorder_point, order_up_to)
policy. A naive uniform-tier baseline (same budget, simplest possible
policy) is computed alongside it purely for comparison; Phase 6's PPO
policy will be benchmarked against this same kind of baseline.
"""
from fastapi import APIRouter, HTTPException

from app.core import state
from app.optimization.solver import apply_policy_to_model, solve_safety_stock_allocation
from app.schemas.models import NodePolicy, OptimizationRequest, OptimizationResult

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/{run_id}/solve", response_model=OptimizationResult)
async def solve(run_id: str, request: OptimizationRequest = OptimizationRequest()) -> OptimizationResult:
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    model = state.get_model(run_id)
    if model is None:
        raise HTTPException(status_code=409, detail="Model not yet initialized for this run")

    result = solve_safety_stock_allocation(
        model,
        total_budget=request.total_budget,
        stockout_cost_per_unit=request.stockout_cost_per_unit,
    )

    apply_policy_to_model(model, result["policies"])

    policies_out = [
        NodePolicy(
            node=name,
            service_level=p.service_level,
            reorder_point=round(p.reorder_point, 2),
            order_up_to=round(p.order_up_to, 2),
            safety_stock_units=round(p.safety_stock_units, 2),
            expected_stockout_cost=round(
                p.expected_shortage_units * request.stockout_cost_per_unit * result["cost_weight_by_node"][name], 2
            ),
        )
        for name, p in result["policies"].items()
    ]

    return OptimizationResult(
        run_id=run_id,
        solver_status=result["status"],
        total_budget=round(result["total_budget"], 2),
        budget_used=round(result["budget_used"], 2),
        total_expected_stockout_cost=round(result["total_expected_stockout_cost"], 4),
        naive_baseline_service_level=result["naive_baseline_service_level"],
        naive_baseline_cost=round(result["naive_baseline_cost"], 4),
        naive_baseline_budget_used=round(result["naive_baseline_budget_used"], 2),
        policies=policies_out,
    )
