"""
/rl routes.

Three different jobs, deliberately kept separate:
  - decide():    one-off query -- "what would the trained policy do for
                 this store right now?" -- without changing anything.
  - apply():     assigns the trained policy to control one or more stores'
                 future ordering decisions for the rest of THIS run, via
                 model.rl_policies (see SupplyChainModel.step()). Mirrors
                 how /optimization/{run_id}/solve applies an OR-Tools
                 policy in Phase 5 -- compute once, then let it drive
                 subsequent steps.
  - benchmark():  NOT run-scoped on purpose. It reports the same-seed,
                 same-cost-function, same-decision-timing PPO-vs-OR-Tools
                 comparison from app/rl/benchmark.py, which evaluates the
                 trained policy on its own reference 1-supplier/1-DC/1-store
                 setup -- the network it was trained on -- not on whatever
                 a particular run_id happens to be configured with. Scoping
                 it to a run_id would wrongly imply the comparison depends
                 on that run's specific topology.

The trained policy only covers a single store's decision (Phase 6's scope,
matching the env it was trained in), so decide()/apply() only accept Store
node ids, not DistributionCenter or Supplier.
"""
from fastapi import APIRouter, HTTPException

from app.core import state
from app.rl.benchmark import run_benchmark
from app.rl.policy import get_policy
from app.schemas.models import RLApplyRequest, RLApplyResult, RLBenchmarkResult, RLDecision

router = APIRouter(prefix="/rl", tags=["rl"])


@router.post("/{run_id}/decide", response_model=RLDecision)
async def decide(run_id: str, node_id: str) -> RLDecision:
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    model = state.get_model(run_id)
    if model is None:
        raise HTTPException(status_code=409, detail="Model not yet initialized for this run")

    store = next((s for s in model.stores if s.name == node_id), None)
    if store is None:
        raise HTTPException(
            status_code=404,
            detail=f"'{node_id}' is not a store in this run (the RL policy only supports stores)",
        )

    action = get_policy().decide(store.build_observation())
    return RLDecision(run_id=run_id, node_id=node_id, action=action)


@router.post("/{run_id}/apply", response_model=RLApplyResult)
async def apply(run_id: str, request: RLApplyRequest = RLApplyRequest()) -> RLApplyResult:
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    model = state.get_model(run_id)
    if model is None:
        raise HTTPException(status_code=409, detail="Model not yet initialized for this run")

    valid_names = {s.name for s in model.stores}
    target_names = request.store_ids if request.store_ids is not None else sorted(valid_names)
    unknown = [name for name in target_names if name not in valid_names]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown store id(s): {unknown}")

    policy = get_policy()
    for name in target_names:
        model.rl_policies[name] = policy.decide

    return RLApplyResult(run_id=run_id, stores_assigned=target_names)


@router.post("/benchmark", response_model=RLBenchmarkResult)
async def benchmark(num_episodes: int = 20, service_level: float = 0.95) -> RLBenchmarkResult:
    policy = get_policy()
    result = run_benchmark(policy.decide, num_episodes=num_episodes, service_level=service_level)
    return RLBenchmarkResult(
        num_episodes=result["num_episodes"],
        ppo_avg_cost=round(result["ppo_avg_cost"], 2),
        baseline_avg_cost=round(result["baseline_avg_cost"], 2),
        baseline_service_level=result["baseline_service_level"],
        baseline_reorder_point=round(result["baseline_reorder_point"], 2),
        baseline_order_up_to=round(result["baseline_order_up_to"], 2),
        improvement_pct=round(result["improvement_pct"], 1),
    )
