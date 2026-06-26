"""
NetworkX graph analytics.

Builds a directed graph straight from a SupplyChainModel's existing
topology — edges point in the direction of material flow:
Supplier -> DistributionCenter -> Store. This module only reads the
model's `.upstream` pointers and agent lists; it never rebuilds or
duplicates the network, so Phase 3's model stays the single source of
truth for topology.

Metrics computed:
  - degree / betweenness centrality — which nodes the network leans on most
  - articulation points — nodes whose removal disconnects part of the
    network (computed on the undirected view, the standard definition)
  - bottlenecks — turns each articulation point into a business-meaningful
    number: how many stores actually lose all supplier connectivity if that
    node is removed. A structural articulation point near a single store is
    a very different problem from one upstream of half the network; this is
    what tells the two apart.
"""
from typing import Any, Dict, List

import networkx as nx

from app.simulation.model import SupplyChainModel


def build_graph(model: SupplyChainModel) -> nx.DiGraph:
    graph = nx.DiGraph()

    for supplier in model.suppliers:
        graph.add_node(supplier.name, kind="supplier")
    for dc in model.distribution_centers:
        graph.add_node(dc.name, kind="distribution_center")
    for store in model.stores:
        graph.add_node(store.name, kind="store")

    for dc in model.distribution_centers:
        if dc.upstream is not None:
            graph.add_edge(dc.upstream.name, dc.name)
    for store in model.stores:
        if store.upstream is not None:
            graph.add_edge(store.upstream.name, store.name)

    return graph


def compute_network_metrics(model: SupplyChainModel) -> Dict[str, Any]:
    graph = build_graph(model)
    undirected = graph.to_undirected()

    degree_centrality = {k: round(v, 4) for k, v in nx.degree_centrality(graph).items()}
    betweenness_centrality = {k: round(v, 4) for k, v in nx.betweenness_centrality(graph).items()}
    articulation_points = sorted(nx.articulation_points(undirected)) if graph.number_of_nodes() > 2 else []

    bottlenecks = _identify_bottlenecks(model, graph)

    # Phase 7 needs the actual graph structure (not just aggregate metrics)
    # to render a topology diagram, rather than re-deriving the round-robin
    # assignment client-side and risking it drifting out of sync with
    # whatever Phase 3's model actually does.
    nodes = [{"id": node, "kind": data["kind"]} for node, data in graph.nodes(data=True)]
    edges = [{"source": source, "target": target} for source, target in graph.edges()]

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "nodes": nodes,
        "edges": edges,
        "degree_centrality": degree_centrality,
        "betweenness_centrality": betweenness_centrality,
        "articulation_points": articulation_points,
        "bottlenecks": bottlenecks,
    }


def _identify_bottlenecks(model: SupplyChainModel, graph: nx.DiGraph) -> List[Dict[str, Any]]:
    """
    Functional bottleneck score — deliberately NOT limited to structural
    articulation points. For every supplier and DC, asks: if this node
    failed, how many stores would lose all supplier connectivity?

    This catches a real gap that pure articulation-point analysis misses:
    a supplier feeding only one DC is a single point of failure for every
    store downstream of that DC, but it's a degree-1 leaf within its own
    (possibly disconnected) component, so removing it can never increase
    the undirected component count — the textbook articulation-point
    definition simply doesn't apply to leaves. The business question here
    is directed reachability to a source, not undirected connectivity, so
    it has to be computed separately.
    """
    supplier_names = {s.name for s in model.suppliers}
    store_names = [s.name for s in model.stores]
    if not store_names:
        return []

    candidate_nodes = [s.name for s in model.suppliers] + [d.name for d in model.distribution_centers]
    results = []
    for node in candidate_nodes:
        reduced = graph.copy()
        reduced.remove_node(node)

        cut_off = 0
        for store in store_names:
            if store not in reduced:
                continue
            reachable_suppliers = {n for n in nx.ancestors(reduced, store) if n in supplier_names}
            if not reachable_suppliers:
                cut_off += 1

        if cut_off > 0:
            results.append(
                {
                    "node": node,
                    "stores_cut_off": cut_off,
                    "stores_cut_off_pct": round(100 * cut_off / len(store_names), 1),
                }
            )

    results.sort(key=lambda b: b["stores_cut_off"], reverse=True)
    return results
