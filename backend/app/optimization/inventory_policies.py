"""
Classical inventory policy formulas: EOQ, lead-time demand, safety stock,
and the standard-normal "loss function" used to price out expected
shortage at any given safety-stock level.

These are the closed-form building blocks. app/optimization/solver.py is
where OR-Tools actually decides HOW MUCH safety stock each node gets,
subject to a shared budget — these functions just price out any candidate
choice it considers, given a demand profile and a lead time.
"""
import math
from dataclasses import dataclass
from typing import Tuple

from scipy.stats import norm


def economic_order_quantity(demand_rate: float, ordering_cost: float, holding_cost_per_unit: float) -> float:
    """Classic EOQ: sqrt(2 * D * K / h). `demand_rate` must be in the same
    time unit as ordering_cost/holding_cost_per_unit — here, that's "per
    simulation step", matching every other rate in this model. (An earlier
    version of this function annualized demand_mean by x365, which silently
    assumed a step == a day; that produced an EOQ ~10x too large relative to
    Phase 3's tuned defaults. There's no calendar concept in this model, so
    there's no principled "annual" framing to begin with — per-step is the
    only unit that's actually consistent with the rest of the simulation.)"""
    if holding_cost_per_unit <= 0 or demand_rate <= 0:
        return 0.0
    return math.sqrt(2 * demand_rate * ordering_cost / holding_cost_per_unit)


def lead_time_demand_stats(demand_mean: float, demand_std: float, lead_time: int) -> Tuple[float, float]:
    """Demand accumulated over `lead_time` steps, assuming iid per-step
    demand: mean scales linearly, std scales with sqrt(lead_time)."""
    lt_mean = demand_mean * lead_time
    lt_std = demand_std * math.sqrt(lead_time)
    return lt_mean, lt_std


def _standard_normal_loss(z: float) -> float:
    """L(z) = phi(z) - z * (1 - Phi(z)) — expected shortfall, in units of
    standard deviations, for a safety factor z. Standard result for normal
    demand; used to convert a safety-stock level into expected shortage."""
    return max(0.0, norm.pdf(z) - z * (1 - norm.cdf(z)))


def safety_stock(lead_time_demand_std: float, service_level: float) -> float:
    """z * sigma_L, where z is the inverse normal CDF at the target service level."""
    z = norm.ppf(service_level)
    return max(0.0, z * lead_time_demand_std)


def expected_shortage_units(lead_time_demand_std: float, service_level: float) -> float:
    """Expected units short per replenishment cycle, at the safety-stock
    level implied by `service_level`."""
    if lead_time_demand_std <= 0:
        return 0.0
    z = norm.ppf(service_level)
    return _standard_normal_loss(z) * lead_time_demand_std


def expected_shortage_from_buffer(buffer_units: float, lead_time_demand_std: float) -> float:
    """Same as expected_shortage_units, but driven directly by a safety-stock
    quantity instead of a target service level — used by the solver to score
    a continuous (non-tiered) allocation, e.g. for baseline comparisons."""
    if lead_time_demand_std <= 0:
        return 0.0
    z = buffer_units / lead_time_demand_std
    return _standard_normal_loss(z) * lead_time_demand_std


@dataclass
class PolicyParams:
    service_level: float
    reorder_point: float
    order_up_to: float
    safety_stock_units: float
    expected_shortage_units: float


def compute_policy(
    demand_mean: float,
    demand_std: float,
    lead_time: int,
    service_level: float,
    ordering_cost: float,
    holding_cost_per_unit: float,
) -> PolicyParams:
    """Full (reorder_point, order_up_to) policy for one node at one
    candidate service level. order_up_to = reorder_point + EOQ, i.e. the
    standard (s, S) approximation where S = s + Q*."""
    lt_mean, lt_std = lead_time_demand_stats(demand_mean, demand_std, lead_time)
    ss = safety_stock(lt_std, service_level)
    reorder_point = lt_mean + ss

    eoq = economic_order_quantity(demand_mean, ordering_cost, holding_cost_per_unit)
    order_up_to = reorder_point + eoq

    shortage = expected_shortage_units(lt_std, service_level)

    return PolicyParams(
        service_level=service_level,
        reorder_point=reorder_point,
        order_up_to=order_up_to,
        safety_stock_units=ss,
        expected_shortage_units=shortage,
    )
