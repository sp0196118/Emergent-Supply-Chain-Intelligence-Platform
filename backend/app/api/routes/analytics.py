"""
/analytics routes.

Phase 4 update: network_metrics now computes real NetworkX graph metrics
from the live model's topology — degree/betweenness centrality, structural
articulation points, and a functional bottleneck score (how many stores
lose all supplier connectivity if a given node fails) — instead of
returning a config-derived node count.

The model is available immediately after a run is created (see Phase 4
refactor in routes/simulation.py), so this works even before any
simulation step has executed — topology doesn't depend on runtime state.
"""
from fastapi import APIRouter, HTTPException

from app.analytics.network_metrics import compute_network_metrics
from app.core import state
from app.schemas.models import NetworkMetrics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{run_id}/network-metrics", response_model=NetworkMetrics)
async def network_metrics(run_id: str) -> NetworkMetrics:
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    model = state.get_model(run_id)
    if model is None:
        raise HTTPException(status_code=409, detail="Model not yet initialized for this run")

    metrics = compute_network_metrics(model)
    return NetworkMetrics(run_id=run_id, **metrics)
