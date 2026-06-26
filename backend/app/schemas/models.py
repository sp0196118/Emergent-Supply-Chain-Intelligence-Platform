"""
Pydantic request/response models shared across routes.

These shapes are the contract the React frontend (Phase 7-8) will be built
against. Phases 3-6 now populate real data through these schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DemandSource(str, Enum):
    synthetic = "synthetic"
    m5 = "m5"


class PolicyType(str, Enum):
    or_tools = "or_tools"
    ppo = "ppo"


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class SimulationConfig(BaseModel):
    num_suppliers: int = Field(2, ge=1, le=10)
    num_distribution_centers: int = Field(3, ge=1, le=10)
    num_stores: int = Field(12, ge=1, le=50)
    num_steps: int = Field(30, ge=1, le=365)
    demand_source: DemandSource = DemandSource.synthetic
    policy_type: PolicyType = PolicyType.or_tools


class SimulationRun(BaseModel):
    run_id: str
    status: RunStatus
    config: SimulationConfig
    created_at: datetime
    current_step: int = 0


class SimulationStepUpdate(BaseModel):
    run_id: str
    step: int
    inventory_levels: Dict[str, float]
    stockouts: List[str] = []
    status: RunStatus


class NodeBottleneck(BaseModel):
    node: str
    stores_cut_off: int
    stores_cut_off_pct: float


class NodeInfo(BaseModel):
    id: str
    kind: str  # "supplier" | "distribution_center" | "store"


class EdgeInfo(BaseModel):
    source: str
    target: str


class NetworkMetrics(BaseModel):
    run_id: str
    node_count: int
    edge_count: int
    nodes: List[NodeInfo] = []
    edges: List[EdgeInfo] = []
    degree_centrality: Dict[str, float] = {}
    betweenness_centrality: Dict[str, float] = {}
    articulation_points: List[str] = []
    bottlenecks: List[NodeBottleneck] = []


class NodePolicy(BaseModel):
    node: str
    service_level: float
    reorder_point: float
    order_up_to: float
    safety_stock_units: float
    expected_stockout_cost: float


class OptimizationRequest(BaseModel):
    total_budget: Optional[float] = Field(None, ge=0)  # None -> solver picks a sensible default
    stockout_cost_per_unit: float = Field(8.0, gt=0)


class OptimizationResult(BaseModel):
    run_id: str
    solver_status: str
    total_budget: float
    budget_used: float
    total_expected_stockout_cost: float
    naive_baseline_service_level: float
    naive_baseline_cost: float
    naive_baseline_budget_used: float
    policies: List[NodePolicy] = []


class RLDecision(BaseModel):
    run_id: str
    node_id: str
    action: float


class RLApplyRequest(BaseModel):
    store_ids: Optional[List[str]] = None  # None -> apply to every store in the run


class RLApplyResult(BaseModel):
    run_id: str
    stores_assigned: List[str]


class RLBenchmarkResult(BaseModel):
    num_episodes: int
    ppo_avg_cost: float
    baseline_avg_cost: float
    baseline_service_level: float
    baseline_reorder_point: float
    baseline_order_up_to: float
    improvement_pct: float
