"""
In-memory run + model store.

RUNS holds the lightweight SimulationRun records the API returns.
MODELS holds the live Mesa SupplyChainModel object for each run (added in
Phase 3), so Phase 4 (NetworkX) and Phase 5 (OR-Tools) can read real
agent/topology state directly instead of re-deriving it from config numbers.
Both are good enough for local dev / a live demo; swapping for Redis or
Postgres later only touches this file.
"""
from typing import TYPE_CHECKING, Dict, Optional

from app.schemas.models import SimulationRun

if TYPE_CHECKING:
    from app.simulation.model import SupplyChainModel

RUNS: Dict[str, SimulationRun] = {}
MODELS: Dict[str, "SupplyChainModel"] = {}


def create_run(run: SimulationRun) -> None:
    RUNS[run.run_id] = run


def get_run(run_id: str) -> Optional[SimulationRun]:
    return RUNS.get(run_id)


def update_run(run: SimulationRun) -> None:
    RUNS[run.run_id] = run


def set_model(run_id: str, model: "SupplyChainModel") -> None:
    MODELS[run_id] = model


def get_model(run_id: str) -> Optional["SupplyChainModel"]:
    return MODELS.get(run_id)
