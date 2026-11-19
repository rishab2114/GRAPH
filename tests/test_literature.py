import json

import pytest

from gffs import literature as lit
from gffs.aml_vocab import Concept, Vocabulary


def _vocab():
    def c(id, syn, ell=True):
        return Concept(id, id, "d", (syn,), ell, "m", "")
    return Vocabulary(1, "2016-12-31", ("bitcoin",), (c("a", "alpha"), c("b", "beta"), c("x", "chi", False)))


def test_concept_filter_shape():
    f = lit.concept_filter(["fan-in", "funnel account"], ["bitcoin"], "2016-12-31")
    assert f == ('title_and_abstract.search:(("fan-in" OR "funnel account") AND ("bitcoin")),'
                 'to_publication_date:2016-12-31')


def test_filter_rejects_breaking_characters():
    with pytest.raises(ValueError):
        lit.concept_filter(["a, b"], ["bitcoin"], "2016-12-31")


class FakeResp:
    def __init__(self, payload, status=200):
        self.status_code, self._p, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._p


class FakeSession:
    """Serves pages keyed by the concept's first synonym; records headers and params."""
    def __init__(self, pages):
        self.pages, self.headers, self.calls = pages, {}, []

    def get(self, url, params, timeout):
        self.calls.append(params)
        key = next(k for k in self.pages if f'"{k}"' in params["filter"])
        seq = self.pages[key]
        if params.get("per_page") == 1:
            return FakeResp({"meta": {"count": 99}, "results": []})
        i = 0 if params["cursor"] == "*" else int(params["cursor"])
        results = seq[i] if i < len(seq) else []
        nxt = str(i + 1) if i + 1 <= len(seq) else None
        return FakeResp({"meta": {"count": sum(map(len, seq)), "next_cursor": nxt}, "results": results})


def _w(i, y):
    return {"id": f"https://openalex.org/W{i}", "publication_year": y}


def test_fetch_build_and_summarise(tmp_path):
    pages = {"alpha": [[_w(1, 2010), _w(2, 2012)], [_w(3, 2015)]],
             "beta": [[_w(2, 2012), _w(3, 2015), _w(4, 2016)]],
             "chi": [[_w(4, 2016)]]}
    sess = FakeSession(pages)
    client = lit.Client("SECRET", session=sess, pause=0)
    assert sess.headers["Authorization"] == "Bearer SECRET"
    v = _vocab()
    records = lit.fetch_vocabulary(v, client, tmp_path)
    assert all("SECRET" not in p.read_text() for p in tmp_path.iterdir())
    assert all("SECRET" not in json.dumps(c) for c in sess.calls)
    assert set(records["a"]["works"]) == {"W1", "W2", "W3"}

    works = lit.works_from_records(records)
    assert works["W2"]["concepts"] == ["a", "b"] and works["W4"]["concepts"] == ["b", "x"]
    assert lit.first_link_year(works) == {("a", "b"): 2012, ("b", "x"): 2016}

    g2011 = lit.graph_at(works, 2011, v.ids)
    assert set(g2011.nodes) == {"a", "b", "x"} and g2011.number_of_edges() == 0
    assert g2011.nodes["b"]["freq"] == 0
    g = lit.graph_at(works, 2016, v.ids)
    assert g.edges["a", "b"]["weight"] == 2 and g.has_edge("b", "x")

    s = lit.summarise(v, works, [2011, 2016])
    assert s["by_year"][0] == {"year": 2011, "n_works": 1, "n_edges": 0, "n_missing": 3, "n_missing_expressible": 1}
    assert s["by_year"][1]["n_missing"] == 1 and s["by_year"][1]["n_missing_expressible"] == 0

    # Second run reads the cache and makes no requests.
    n = len(sess.calls)
    lit.fetch_vocabulary(v, client, tmp_path)
    assert len(sess.calls) == n


def test_cache_with_different_query_is_refused(tmp_path):
    v = _vocab()
    (tmp_path / "a.json").write_text(json.dumps({"filter": "old", "works": {}, "reported_count": 0}))
    with pytest.raises(RuntimeError, match="different query"):
        lit.fetch_vocabulary(v, lit.Client(None, session=FakeSession({}), pause=0), tmp_path)


def test_budget_exhausted_is_reported_clearly():
    class S(FakeSession):
        def get(self, url, params, timeout):
            return FakeResp({"error": "Rate limit exceeded", "message": "Insufficient budget"}, 429)
    with pytest.raises(RuntimeError, match="OPENALEX_API_KEY"):
        lit.Client(None, session=S({}), pause=0).count("x")


def test_temporary_outage_is_retried_patiently(monkeypatch):
    waits = []
    monkeypatch.setattr(lit.time, "sleep", lambda s: waits.append(s))

    class Flaky:
        headers = {}
        def __init__(self): self.n = 0
        def get(self, url, params, timeout):
            self.n += 1
            if self.n <= 7:
                return FakeResp({"error": "Search temporarily unavailable", "message": "Anonymous search is paused"}, status=503)
            return FakeResp({"meta": {"count": 5}, "results": []})

    assert lit.Client(None, session=Flaky(), pause=0).count("F") == 5
    assert sum(waits) >= 300          # waited minutes, not seconds, for the cluster to recover
