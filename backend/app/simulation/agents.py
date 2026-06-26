"""
Mesa agent definitions: Store, DistributionCenter, Supplier.

All three share inventory-position / order-fulfillment bookkeeping
(SupplyChainAgent base class). What differs is where their "demand" comes
from:
  - Store:               external customer demand (stochastic, sampled each step)
  - DistributionCenter:   aggregated orders placed by its stores
  - Supplier:             aggregated orders placed by its distribution centers,
                          plus a per-step production cap instead of an upstream

Reorder policy is currently a fixed (reorder_point, order_up_to) policy set at
construction time in model.py. Phase 5 (OR-Tools) will compute those two
numbers properly per node; Phase 6 (PPO) will replace the decision inside
`place_order_if_needed` with a learned action. Both later phases only need to
touch that one method — the shipment/fulfillment machinery below doesn't change.

Known MVP simplification: unfulfilled demand (a stockout at any node) is lost,
not backordered. Flagged here and in docs/ARCHITECTURE.md as a candidate
refinement once OR-Tools/PPO are comparing policies on cost, since backorder
cost and lost-sales cost are usually modeled differently.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import mesa


@dataclass
class Shipment:
    quantity: float
    arrival_step: int


class SupplyChainAgent(mesa.Agent):
    """Shared inventory position / order-fulfillment logic."""

    def __init__(
        self,
        model: mesa.Model,
        name: str,
        initial_inventory: float,
        reorder_point: float,
        order_up_to: float,
        lead_time: int,
    ) -> None:
        super().__init__(model)
        self.name = name
        self.inventory = initial_inventory
        self.reorder_point = reorder_point
        self.order_up_to = order_up_to
        self.lead_time = lead_time

        self.upstream: Optional["SupplyChainAgent"] = None
        self.in_transit: List[Shipment] = []
        self.pending_orders: List[Tuple["SupplyChainAgent", float]] = []

        self.last_unmet_demand: float = 0.0
        self.last_order_placed: float = 0.0

    @property
    def inventory_position(self) -> float:
        """On-hand inventory plus anything already in transit to this node."""
        return self.inventory + sum(s.quantity for s in self.in_transit)

    def receive_shipments(self) -> None:
        """Move any shipments that have arrived by this step into inventory."""
        current_step = self.model.steps
        arrived = [s for s in self.in_transit if s.arrival_step <= current_step]
        if arrived:
            self.inventory += sum(s.quantity for s in arrived)
            self.in_transit = [s for s in self.in_transit if s.arrival_step > current_step]

    def receive_order(self, orderer: "SupplyChainAgent", quantity: float) -> None:
        """Called by a downstream agent placing a replenishment order. The
        order is queued and fulfilled on this agent's NEXT call to
        fulfill_pending_orders (i.e. there's a one-step processing delay,
        on top of the shipping lead time itself — a deliberate, realistic
        simplification rather than instant fulfillment)."""
        if quantity > 0:
            self.pending_orders.append((orderer, quantity))

    def fulfill_pending_orders(self) -> None:
        """Ship as much of this step's queued orders as inventory allows,
        splitting pro-rata across orderers if inventory can't cover all of
        them. Unfulfilled quantity is lost demand for this node this step."""
        orders = self.pending_orders
        self.pending_orders = []

        total_requested = sum(qty for _, qty in orders)
        if total_requested <= 0:
            self.last_unmet_demand = 0.0
            return

        fulfillment_ratio = min(1.0, self.inventory / total_requested)
        arrival_step = self.model.steps + self.lead_time
        shipped_total = 0.0
        for orderer, qty in orders:
            ship_qty = qty * fulfillment_ratio
            if ship_qty > 0:
                orderer.in_transit.append(Shipment(quantity=ship_qty, arrival_step=arrival_step))
                shipped_total += ship_qty

        self.inventory -= shipped_total
        self.last_unmet_demand = total_requested - shipped_total

    def place_order_if_needed(self) -> None:
        """Standard (reorder_point, order_up_to) policy: if inventory
        position has dropped to or below the reorder point, order enough
        to bring position back up to order_up_to."""
        if self.upstream is None:
            self.last_order_placed = 0.0
            return

        position = self.inventory_position
        order_qty = max(self.order_up_to - position, 0.0) if position <= self.reorder_point else 0.0
        self.last_order_placed = order_qty
        if order_qty > 0:
            self.upstream.receive_order(self, order_qty)


class Store(SupplyChainAgent):
    """Leaf node: sells to end customers, reorders from a DistributionCenter."""

    def __init__(
        self,
        model: mesa.Model,
        name: str,
        initial_inventory: float,
        reorder_point: float,
        order_up_to: float,
        demand_mean: float,
        demand_std: float,
    ) -> None:
        # lead_time=0: stores never ship to anyone, so it's unused, but kept
        # for a consistent base-class signature.
        super().__init__(model, name, initial_inventory, reorder_point, order_up_to, lead_time=0)
        self.demand_mean = demand_mean
        self.demand_std = demand_std
        self.last_demand: float = 0.0

        # Phase 6 hook: if set, place_order_if_needed uses this value INSTEAD
        # of the (reorder_point, order_up_to) rule for exactly one step, then
        # clears it. Two callers use this, deliberately differently:
        #   - app/rl/env.py (training) sets it directly each env.step(action)
        #   - SupplyChainModel.step() (live inference) sets it by querying a
        #     loaded policy via model.rl_policies, once per step, for any
        #     store that's been assigned one
        # Both paths go through the exact same fulfillment/shipment code below
        # them, so there's no behavioral difference between a "trained" order
        # and a "ruled" order once it's placed.
        self.external_order_override: Optional[float] = None

    def experience_demand(self) -> None:
        demand = max(0.0, float(self.model.rng.normal(self.demand_mean, self.demand_std)))
        self.last_demand = demand
        shipped = min(demand, self.inventory)
        self.inventory -= shipped
        self.last_unmet_demand = demand - shipped

    def build_observation(self) -> List[float]:
        """Compact state vector. Defined here (not duplicated in
        app/rl/env.py) so training and live inference can never drift out
        of sync with what Store actually has."""
        return [
            float(self.inventory),
            float(self.inventory_position),
            float(self.demand_mean),
            float(self.demand_std),
            float(self.last_demand),
        ]

    def place_order_if_needed(self) -> None:
        if self.external_order_override is not None:
            order_qty = max(0.0, self.external_order_override)
            self.external_order_override = None  # one-shot; must be re-set every step
            self.last_order_placed = order_qty
            if order_qty > 0 and self.upstream is not None:
                self.upstream.receive_order(self, order_qty)
            return
        super().place_order_if_needed()


class DistributionCenter(SupplyChainAgent):
    """Aggregates orders from its stores; reorders from a Supplier.
    All behavior is inherited from SupplyChainAgent — this subclass exists
    so the network has a distinct, type-checkable node for analytics/UI."""


class Supplier(SupplyChainAgent):
    """Top of the chain: no upstream. Instead of ordering, it manufactures
    up to `production_capacity` units per step — that cap is what creates
    real scarcity (and therefore interesting bottlenecks) downstream."""

    def __init__(
        self,
        model: mesa.Model,
        name: str,
        initial_inventory: float,
        order_up_to: float,
        lead_time: int,
        production_capacity: float,
    ) -> None:
        super().__init__(model, name, initial_inventory, reorder_point=0.0, order_up_to=order_up_to, lead_time=lead_time)
        self.production_capacity = production_capacity
        self.last_production: float = 0.0

    def produce(self) -> None:
        target = max(0.0, self.order_up_to - self.inventory_position)
        produced = min(target, self.production_capacity)
        self.inventory += produced
        self.last_production = produced
