"""
/simulation routes.

start_run kicks off a run and returns immediately; the actual stepping
happens in the background task `_drive_run` so the request doesn't block.

Phase 4 update: the SupplyChainModel is now constructed synchronously inside
start_run (model construction is cheap — it's just creating agents, no
stepping) rather than inside the background task. That means topology-only
endpoints like /analytics/{run_id}/network-metrics work immediately after a
run is created, instead of racing the background task for `state.set_model`
to be called. `_drive_run` now takes the already-built model directly.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.websockets import manager
from app.core import state
from app.schemas.models import (
    RunStatus,
    SimulationConfig,
    SimulationRun,
    SimulationStepUpdate,
)
from app.simulation.model import SupplyChainModel

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationRun)
async def start_run(config: SimulationConfig) -> SimulationRun:
    run_id = str(uuid.uuid4())[:8]
    run = SimulationRun(
        run_id=run_id,
        status=RunStatus.queued,
        config=config,
        created_at=datetime.now(timezone.utc),
    )
    state.create_run(run)

    model = SupplyChainModel(
        num_suppliers=config.num_suppliers,
        num_distribution_centers=config.num_distribution_centers,
        num_stores=config.num_stores,
    )
    state.set_model(run_id, model)

    asyncio.create_task(_drive_run(run_id, model, config.num_steps))
    return run


@router.get("/{run_id}", response_model=SimulationRun)
async def get_run_status(run_id: str) -> SimulationRun:
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/state", response_model=SimulationStepUpdate)
async def get_run_state(run_id: str) -> SimulationStepUpdate:
    """
    Phase 7 addition: a REST snapshot of current inventory levels, for the
    frontend to poll. Deliberately NOT real-time push — that's Phase 8's
    job via the existing WebSocket broadcast in _drive_run below. This
    endpoint reuses the exact same SimulationStepUpdate shape the
    WebSocket sends, so swapping polling for a live subscription later
    doesn't require the frontend to change what shape it reads.
    """
    run = state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    model = state.get_model(run_id)
    if model is None:
        raise HTTPException(status_code=409, detail="Model not yet initialized for this run")

    snapshot = model.state_snapshot()
    return SimulationStepUpdate(
        run_id=run_id,
        step=run.current_step,
        inventory_levels=snapshot["inventory_levels"],
        stockouts=snapshot["stockouts"],
        status=run.status,
    )


async def _drive_run(run_id: str, model: SupplyChainModel, num_steps: int) -> None:
    run = state.get_run(run_id)
    if run is None:
        return
    run.status = RunStatus.running
    state.update_run(run)

    for step in range(1, num_steps + 1):
        model.step()
        snapshot = model.state_snapshot()

        run.current_step = step
        state.update_run(run)

        update = SimulationStepUpdate(
            run_id=run_id,
            step=step,
            inventory_levels=snapshot["inventory_levels"],
            stockouts=snapshot["stockouts"],
            status=RunStatus.running,
        )
        await manager.broadcast(run_id, update.model_dump_json())
        await asyncio.sleep(0.3)

    run.status = RunStatus.completed
    state.update_run(run)
    final_snapshot = model.state_snapshot()
    await manager.broadcast(
        run_id,
        SimulationStepUpdate(
            run_id=run_id,
            step=num_steps,
            inventory_levels=final_snapshot["inventory_levels"],
            stockouts=final_snapshot["stockouts"],
            status=RunStatus.completed,
        ).model_dump_json(),
    )
