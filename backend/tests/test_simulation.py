"""
Phase 3 tests: the Mesa model directly, independent of the API layer.
"""
from app.simulation.model import SupplyChainModel


def test_model_creates_correct_agent_counts():
    model = SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=1)
    assert len(model.suppliers) == 2
    assert len(model.distribution_centers) == 3
    assert len(model.stores) == 12


def test_round_robin_topology_assigns_every_node_an_upstream():
    model = SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=1)
    assert all(dc.upstream in model.suppliers for dc in model.distribution_centers)
    assert all(store.upstream in model.distribution_centers for store in model.stores)


def test_inventory_never_goes_negative_over_many_steps():
    model = SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=2)
    for _ in range(50):
        model.step()
        snapshot = model.state_snapshot()
        assert all(v >= 0 for v in snapshot["inventory_levels"].values())


def test_state_snapshot_includes_every_node():
    model = SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=4, seed=3)
    model.step()
    levels = model.state_snapshot()["inventory_levels"]
    assert set(levels.keys()) == {
        "store_0", "store_1", "store_2", "store_3",
        "dc_0", "dc_1", "dc_2",
        "supplier_0", "supplier_1",
    }


def test_supplier_capacity_constraint_produces_stockouts():
    """Proves the scarcity mechanism actually engages: with production
    capacity cut far below aggregate demand, stockouts must appear
    somewhere downstream within a reasonable number of steps."""
    model = SupplyChainModel(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=4)
    for sup in model.suppliers:
        sup.production_capacity = 5.0  # aggregate store demand is ~120/step
    saw_stockout = False
    for _ in range(40):
        model.step()
        if model.state_snapshot()["stockouts"]:
            saw_stockout = True
            break
    assert saw_stockout


def test_same_seed_is_reproducible():
    model_a = SupplyChainModel(num_suppliers=2, num_distribution_centers=2, num_stores=5, seed=99)
    model_b = SupplyChainModel(num_suppliers=2, num_distribution_centers=2, num_stores=5, seed=99)
    for _ in range(10):
        model_a.step()
        model_b.step()
    assert model_a.state_snapshot() == model_b.state_snapshot()
