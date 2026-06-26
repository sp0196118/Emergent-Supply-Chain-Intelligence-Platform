"""
Phase 4 tests: NetworkX analytics, independent of the API layer.
"""
from app.analytics.network_metrics import build_graph, compute_network_metrics
from app.simulation.model import SupplyChainModel


def _model(num_suppliers=2, num_distribution_centers=3, num_stores=12, seed=1):
    return SupplyChainModel(
        num_suppliers=num_suppliers,
        num_distribution_centers=num_distribution_centers,
        num_stores=num_stores,
        seed=seed,
    )


def test_graph_has_one_edge_per_upstream_link():
    model = _model(num_suppliers=2, num_distribution_centers=3, num_stores=12)
    graph = build_graph(model)
    # every DC has exactly one upstream edge, every store has exactly one
    assert graph.number_of_edges() == 3 + 12
    assert graph.number_of_nodes() == 2 + 3 + 12


def test_edges_point_in_direction_of_material_flow():
    model = _model(num_suppliers=1, num_distribution_centers=1, num_stores=2)
    graph = build_graph(model)
    assert ("supplier_0", "dc_0") in graph.edges
    assert ("dc_0", "store_0") in graph.edges
    # never the reverse
    assert ("dc_0", "supplier_0") not in graph.edges


def test_metrics_shape_matches_schema_fields():
    model = _model()
    metrics = compute_network_metrics(model)
    assert set(metrics.keys()) == {
        "node_count", "edge_count", "nodes", "edges", "degree_centrality",
        "betweenness_centrality", "articulation_points", "bottlenecks",
    }
    assert metrics["node_count"] == 17
    assert metrics["edge_count"] == 15


def test_bottleneck_catches_single_dc_supplier_invisible_to_articulation_points():
    """
    Pins down the exact gap found while building this: with 2 suppliers
    round-robin-assigned across 3 DCs, supplier_1 ends up feeding only
    dc_1 and is a degree-1 leaf within its own disconnected component —
    so it is NOT a structural articulation point (removing a leaf can
    never increase the undirected component count). But it absolutely IS
    a functional single point of failure for dc_1's stores, and the
    bottleneck score must catch it even though articulation_points won't.
    """
    model = _model(num_suppliers=2, num_distribution_centers=3, num_stores=12)
    metrics = compute_network_metrics(model)

    assert "supplier_1" not in metrics["articulation_points"]

    bottleneck_nodes = {b["node"]: b for b in metrics["bottlenecks"]}
    assert "supplier_1" in bottleneck_nodes
    assert bottleneck_nodes["supplier_1"]["stores_cut_off"] == 4


def test_most_critical_node_is_the_supplier_feeding_the_most_dcs():
    model = _model(num_suppliers=2, num_distribution_centers=3, num_stores=12)
    metrics = compute_network_metrics(model)
    most_critical = metrics["bottlenecks"][0]
    assert most_critical["node"] == "supplier_0"  # feeds 2 of 3 DCs -> 8 of 12 stores
    assert most_critical["stores_cut_off"] == 8


def test_single_chain_topology_has_full_articulation_and_full_cutoff():
    """One supplier, one DC, several stores: removing either internal node
    should cut off every store."""
    model = _model(num_suppliers=1, num_distribution_centers=1, num_stores=4)
    metrics = compute_network_metrics(model)
    assert set(metrics["articulation_points"]) == {"dc_0"}
    bottleneck_nodes = {b["node"]: b["stores_cut_off"] for b in metrics["bottlenecks"]}
    assert bottleneck_nodes["supplier_0"] == 4
    assert bottleneck_nodes["dc_0"] == 4


def test_stores_are_never_flagged_as_bottlenecks():
    model = _model()
    metrics = compute_network_metrics(model)
    bottleneck_node_names = {b["node"] for b in metrics["bottlenecks"]}
    store_names = {s.name for s in model.stores}
    assert bottleneck_node_names.isdisjoint(store_names)


def test_nodes_and_edges_are_exposed_for_frontend_rendering():
    """Phase 7 needs the actual graph structure, not just aggregate
    metrics, to draw a topology diagram without re-deriving Phase 3's
    round-robin assignment client-side."""
    model = _model(num_suppliers=1, num_distribution_centers=1, num_stores=2)
    metrics = compute_network_metrics(model)

    node_ids = {n["id"] for n in metrics["nodes"]}
    assert node_ids == {"supplier_0", "dc_0", "store_0", "store_1"}

    kinds_by_id = {n["id"]: n["kind"] for n in metrics["nodes"]}
    assert kinds_by_id["supplier_0"] == "supplier"
    assert kinds_by_id["dc_0"] == "distribution_center"
    assert kinds_by_id["store_0"] == "store"

    edges = {(e["source"], e["target"]) for e in metrics["edges"]}
    assert edges == {("supplier_0", "dc_0"), ("dc_0", "store_0"), ("dc_0", "store_1")}
    assert len(metrics["edges"]) == metrics["edge_count"]
    assert len(metrics["nodes"]) == metrics["node_count"]
