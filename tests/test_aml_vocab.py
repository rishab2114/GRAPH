from dataclasses import replace

import pytest

from gffs.aml_vocab import Concept, Vocabulary, load, validate


def _c(id, synonyms, elliptic=True):
    return Concept(id=id, label=id, definition="d", synonyms=tuple(synonyms), elliptic=elliptic,
                   motif="m", evidence="")


def _v(*concepts):
    return Vocabulary(version=1, cutoff="2016-12-31", anchor_terms=("money laundering", "bitcoin"),
                      concepts=tuple(concepts))


def test_committed_vocabulary_is_valid():
    v = load()
    assert v.cutoff == "2016-12-31"
    assert len(v.concepts) >= 10
    assert {"fan_in", "fan_out", "peel_chain", "mixing_service"} <= set(v.ids)
    assert any(c.elliptic for c in v.concepts) and any(not c.elliptic for c in v.concepts)


def test_expressible_needs_both_concepts_observable():
    v = _v(_c("a", ["alpha"]), _c("b", ["beta"]), _c("x", ["chi"], elliptic=False))
    assert v.expressible("a", "b")
    assert not v.expressible("a", "x")


@pytest.mark.parametrize("concepts, msg", [
    ((_c("a", ["fan-in"]), _c("a", ["other"])), "duplicate concept ids"),
    ((_c("a", ["fan in"]), _c("b", ["Fan-In"])), "used by a and b"),
    ((_c("a", ["mixer"]), _c("b", ["coin mixer"])), "is contained in"),
    ((_c("a", ["bitcoin mixer"]),), "overlaps a scope anchor"),
    ((_c("a", []),), "no synonyms"),
])
def test_invalid_vocabularies_are_rejected(concepts, msg):
    with pytest.raises(ValueError, match=msg):
        validate(_v(*concepts))


def test_missing_motif_is_rejected():
    with pytest.raises(ValueError, match="no motif"):
        validate(_v(replace(_c("a", ["alpha"]), motif=" ")))
