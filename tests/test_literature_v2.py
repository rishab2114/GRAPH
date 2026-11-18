import json

import pytest

from gffs import literature as lit
from gffs import literature_v2 as v2
from tests.test_literature import FakeResp


def _cw(i, y, concepts=None, topics=None):
    w = {"id": f"https://openalex.org/W{i}", "publication_year": y}
    if concepts is not None:
        w["concepts"] = [{"id": f"https://openalex.org/C{c}", "display_name": f"c{c}", "level": lvl, "score": s}
                         for c, lvl, s in concepts]
    if topics is not None:
        w["topics"] = [{"id": f"https://openalex.org/T{t}", "display_name": f"t{t}", "score": s} for t, s in topics]
    return w


def test_choose_source_prefers_concepts_when_present():
    assert v2.choose_source([_cw(1, 2010, concepts=[(1, 2, 0.9)], topics=[(5, 0.9)])], ["concepts", "topics"]) == "concepts"
    assert v2.choose_source([_cw(1, 2010, concepts=[], topics=[(5, 0.9)])], ["concepts", "topics"]) == "topics"
    with pytest.raises(ValueError):
        v2.choose_source([_cw(1, 2010)], ["concepts", "topics"])


def test_work_tags_filters_by_score_and_level():
    w = _cw(1, 2010, concepts=[(1, 2, 0.9), (2, 1, 0.9), (3, 3, 0.2)], topics=[(5, 0.95), (6, 0.1)])
    assert v2.work_tags(w, "concepts", min_score=0.3, min_level=2) == ["C1"]
    assert v2.work_tags(w, "topics", min_score=0.3, min_level=2) == ["T5"]


def test_context_nodes_threshold_cap_and_cutoff():
    corpus = {f"W{i}": {"year": 2015, "tags": ["C1", "C2"]} for i in range(5)}
    corpus |= {f"W{i}": {"year": 2015, "tags": ["C3"]} for i in range(5, 8)}
    corpus |= {f"W{i}": {"year": 2018, "tags": ["C4"]} for i in range(8, 20)}   # after cutoff: ignored
    assert v2.context_nodes(corpus, min_works=3, max_nodes=10, cutoff_year=2016) == ["C1", "C2", "C3"]
    assert v2.context_nodes(corpus, min_works=3, max_nodes=2, cutoff_year=2016) == ["C1", "C2"]   # tie -> id order
    assert v2.context_nodes(corpus, min_works=4, max_nodes=10, cutoff_year=2016) == ["C1", "C2"]


def test_merge_works_unions_v1_concepts_and_context_nodes():
    v1_works = {"W1": {"year": 2012, "concepts": ["fan_in"]}}
    corpus = {"W1": {"year": 2012, "tags": ["C1", "C9"]}, "W2": {"year": 2013, "tags": ["C1"]}}
    w = v2.merge_works(v1_works, corpus, nodes=["C1"], prefix="oa:")
    assert w == {"W1": {"year": 2012, "concepts": ["fan_in", "oa:C1"]}, "W2": {"year": 2013, "concepts": ["oa:C1"]}}


class CorpusSession:
    """Serves corpus pages by cursor; can be told to run out of budget at a given page."""
    def __init__(self, pages, fail_at=None):
        self.pages, self.fail_at, self.headers, self.calls = pages, fail_at, {}, []

    def get(self, url, params, timeout):
        i = 0 if params["cursor"] == "*" else int(params["cursor"])
        self.calls.append(i)
        if self.fail_at is not None and i == self.fail_at:
            return FakeResp({"error": "Rate limit exceeded", "message": "Insufficient budget"}, status=429)
        nxt = str(i + 1) if i + 1 < len(self.pages) else None
        return FakeResp({"meta": {"count": 6, "next_cursor": nxt}, "results": self.pages[i]})


def test_fetch_corpus_resumes_after_budget_runs_out(tmp_path):
    pages = [[_cw(1, 2010, concepts=[(1, 2, 0.9)])], [_cw(2, 2011, concepts=[(1, 2, 0.9)])], [_cw(3, 2012, concepts=[])]]
    s1 = CorpusSession(pages, fail_at=1)
    with pytest.raises(RuntimeError, match="budget"):
        v2.fetch_corpus(lit.Client(None, session=s1, pause=0), "F", tmp_path)
    s2 = CorpusSession(pages)
    raw = v2.fetch_corpus(lit.Client(None, session=s2, pause=0), "F", tmp_path)
    assert s2.calls == [1, 2]                      # page 0 was not fetched again
    assert [w["id"].rsplit("/", 1)[-1] for w in raw] == ["W1", "W2", "W3"]
    s3 = CorpusSession(pages)
    assert len(v2.fetch_corpus(lit.Client(None, session=s3, pause=0), "F", tmp_path)) == 3 and s3.calls == []


def test_fetch_corpus_refuses_cache_from_another_query(tmp_path):
    s = CorpusSession([[_cw(1, 2010)]])
    v2.fetch_corpus(lit.Client(None, session=s, pause=0), "F", tmp_path)
    with pytest.raises(RuntimeError, match="different query"):
        v2.fetch_corpus(lit.Client(None, session=s, pause=0), "G", tmp_path)


def test_rank_scenarios_only_ranks_unlinked_expressible_target_pairs():
    from tests.test_literature import _vocab
    v = _vocab()                       # targets a, b (Elliptic-expressible) and x (not expressible)
    works = {"W1": {"year": 2014, "concepts": ["a", "oa:C1"]}, "W2": {"year": 2015, "concepts": ["b", "oa:C1"]},
             "W3": {"year": 2015, "concepts": ["x", "a"]}}
    r = v2.rank_scenarios(works, v, "frequency", (2013, 2016), 2016)
    assert [s["pair"] for s in r] == [["a", "b"]] and r[0]["rank"] == 1
    works["W4"] = {"year": 2016, "concepts": ["a", "b"]}
    assert v2.rank_scenarios(works, v, "frequency", (2013, 2016), 2016) == []   # already linked
