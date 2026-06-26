"""
SupplyChainModel: wires Supplier -> DistributionCenter -> Store agents into
a 3-echelon network and steps them forward in a fixed stage order each tick.

Topology for the MVP: round-robin assignment — each DC is assigned exactly
one upstream Supplier, each Store exactly one upstream DistributionCenter.
That's deliberately the simplest topology that still produces real
bottlenecks once a Supplier's production_capacity binds. Phase 4 (NetworkX)
reads this topology straight off `model.suppliers/distribution_centers/stores`
and each agent's `.upstream` pointer — this is the single source of truth
for the network graph, nothing gets rebuilt or duplicated for analytics.
"""
from typing import Any, Callable, Dict, List, Optional

import mesa
from mesa.datacollection import DataCollector

from app.simulation.agents import DistributionCenter, Store, Supplier

DEFAULT_STORE_DEMAND_MEAN = 10.0
DEFAULT_STORE_DEMAND_STD = 3.0


class SupplyChainModel(mesa.Model):
    def __init__(
        self,
        num_suppliers: int = 2,
        num_distribution_centers: int = 3,
        num_stores: int = 12,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(rng=seed)

        self.suppliers: List[Supplier] = [
            Supplier(
                self,
                name=f"supplier_{i}",
                initial_inventory=500.0,
                order_up_to=600.0,
                lead_time=2,
                production_capacity=150.0,
            )
            for i in range(num_suppliers)
        ]

        self.distribution_centers: List[DistributionCenter] = [
            DistributionCenter(
                self,
                name=f"dc_{i}",
                initial_inventory=300.0,
                reorder_point=150.0,
                order_up_to=400.0,
                lead_time=2,
            )
            for i in range(num_distribution_centers)
        ]

        self.stores: List[Store] = [
            Store(
                self,
                name=f"store_{i}",
                initial_inventory=80.0,
                reorder_point=40.0,
                order_up_to=100.0,
                demand_mean=DEFAULT_STORE_DEMAND_MEAN,
                demand_std=DEFAULT_STORE_DEMAND_STD,
            )
            for i in range(num_stores)
        ]

        for i, dc in enumerate(self.distribution_centers):
            dc.upstream = self.suppliers[i % num_suppliers]
        for i, store in enumerate(self.stores):
            store.upstream = self.distribution_centers[i % num_distribution_centers]

        # Phase 6: store_name -> callable(observation) -> order_qty. Populated
        # by routes/rl.py for live inference. Empty by default, so existing
        # behavior (and every Phase 1-5 test) is completely unchanged.
        self.rl_policies: Dict[str, Callable[[List[float]], float]] = {}

        self.datacollector = DataCollector(
            model_reporters={
                "total_store_inventory": lambda m: sum(s.inventory for s in m.stores),
                "total_dc_inventory": lambda m: sum(d.inventory for d in m.distribution_centers),
                "total_supplier_inventory": lambda m: sum(s.inventory for s in m.suppliers),
                "total_unmet_store_demand": lambda m: sum(s.last_unmet_demand for s in m.stores),
                "stockout_count": lambda m: sum(1 for s in m.stores if s.last_unmet_demand > 0),
            },
            agent_reporters={
                "inventory": "inventory",
                "last_unmet_demand": "last_unmet_demand",
            },
        )

    def step(self) -> None:
        # Phase 6: resolve any RL-controlled stores' actions BEFORE the
        # staged loop runs, using each store's state as of the end of the
        # previous step (the same timing a live policy would have to use --
        # it can't see this step's demand before deciding).
        for store in self.stores:
            policy_fn = self.rl_policies.get(store.name)
            if policy_fn is not None:
                store.external_order_override = policy_fn(store.build_observation())

        # Stage order matters: a node must produce/fulfill before its
        # downstream nodes check what arrived, and every node must see this
        # step's deliveries and demand before deciding whether to reorder.
        for supplier in self.suppliers:
            supplier.produce()
        for supplier in self.suppliers:
            supplier.fulfill_pending_orders()

        for dc in self.distribution_centers:
            dc.receive_shipments()
        for dc in self.distribution_centers:
            dc.fulfill_pending_orders()

        for store in self.stores:
            store.receive_shipments()
        for store in self.stores:
            store.experience_demand()

        for store in self.stores:
            store.place_order_if_needed()
        for dc in self.distribution_centers:
            dc.place_order_if_needed()

        self.datacollector.collect(self)

    def state_snapshot(self) -> Dict[str, Any]:
        """Flat dict of current inventory levels + stockouts, in the same
        shape the Phase 2 fake stepper produced — that's what let
        routes/simulation.py swap to real Mesa steps with almost no change
        to the route logic itself."""
        inventory_levels: Dict[str, float] = {}
        inventory_levels.update({s.name: float(s.inventory) for s in self.stores})
        inventory_levels.update({d.name: float(d.inventory) for d in self.distribution_centers})
        inventory_levels.update({sup.name: float(sup.inventory) for sup in self.suppliers})

        stockouts = [s.name for s in self.stores if s.last_unmet_demand > 0]
        return {"inventory_levels": inventory_levels, "stockouts": stockouts}
