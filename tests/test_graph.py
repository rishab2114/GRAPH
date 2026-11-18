from gffs.graph import build_graph, candidate_pairs, new_edges

SETS = {"a": frozenset({"T1", "T2"}), "b": frozenset({"T2", "T3"}), "c": frozenset({"T2", "T3"})}


def test_build_graph_weights_and_freq():
    g = build_graph(SETS)
    assert g["T2"]["T3"]["weight"] == 2 and g.nodes["T2"]["freq"] == 3
    assert not g.has_edge("T1", "T3")


def test_candidate_pairs_are_canonical():
    assert candidate_pairs(build_graph(SETS)) == [("T1", "T3")]


def test_new_edges_excludes_nodes_absent_at_t():
    later = build_graph({**SETS, "d": frozenset({"T1", "T3", "T9"})})
    assert new_edges(build_graph(SETS), later) == {("T1", "T3")}


def test_single_technique_entity_still_adds_node():
    g = build_graph({"a": frozenset({"T1", "T2"}), "z": frozenset({"T5"})})
    assert g.nodes["T5"]["freq"] == 1 and g.degree("T5") == 0
