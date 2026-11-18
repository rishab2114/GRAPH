import networkx as nx
import numpy as np
import pytest

from gffs.motifs import MOTIFS, motif_flags, node_features
from gffs.scenarios import graph_features, inject, motif_subgraph, scenario


@pytest.mark.parametrize("name", MOTIFS)
def test_each_motif_subgraph_triggers_its_own_motif(name):
    k, L = 3, 5
    nodes, edges, entry, exit_ = motif_subgraph(name, k, L, prefix="x")
    g = nx.DiGraph(); g.add_nodes_from(nodes); g.add_edges_from(edges)
    assert entry in g and exit_ in g and nx.is_directed_acyclic_graph(g)
    flags = motif_flags(node_features(g), k=k, length=L)
    assert flags[name].any(), f"{name} subgraph does not show motif {name}"


def test_scenario_links_motif_a_exit_to_motif_b_entry():
    nodes, edges, entry = scenario(("peel_chain", "fan_in"), k=3, L=4, prefix="s")
    g = nx.DiGraph(); g.add_nodes_from(nodes); g.add_edges_from(edges)
    assert nx.is_weakly_connected(g)
    flags = motif_flags(node_features(g), k=3, length=4)
    assert flags["peel_chain"].any() and flags["fan_in"].any()


def test_inject_attaches_each_instance_by_one_edge_and_marks_synthetic():
    base = nx.DiGraph([(1, 2), (2, 3), (3, 4)])
    rng = np.random.default_rng(0)
    g, synthetic = inject(base, [("fan_out", "pass_through")] * 3, rng, size_sampler=lambda r: (2, 3))
    assert set(base.nodes) <= set(g.nodes) and len(synthetic) > 0
    assert not (set(synthetic) & set(base.nodes))
    cross = [(u, v) for u, v in g.edges if (u in base) != (v in base)]
    assert len(cross) == 3 and all(u in base for u, v in cross)    # one edge per instance, from a real node


def test_graph_features_include_neighbour_aggregates():
    g = nx.DiGraph([("a", "c"), ("b", "c"), ("c", "d")])
    f = graph_features(g)
    assert f.loc["c", "pred_mean_out_deg"] == 1 and f.loc["c", "succ_max_in_deg"] == 1
    assert f.loc["a", "pred_mean_out_deg"] == 0                        # no predecessors -> 0
