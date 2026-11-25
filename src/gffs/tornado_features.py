"""Stage 2 account features (docs/tornado-design.md section 4), identical for real and synthetic accounts.

Edges are one feature week's successful top-level transactions, typed S (simple_transfer), V (value_call) and
K (call), with every edge touching the infrastructure set I(t) already removed. W = S u V. Counts are distinct
counterparties. Iterative quantities are capped, because account graphs have cycles.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

LAYERS = {"simple_transfer": "S", "value_call": "V", "call": "K"}
PEEL_CAP, DEPTH_CAP, SUCC_CAP = 10, 3, 50
FEATURES = (["in_S", "out_S", "in_V", "out_V", "in_K", "out_K", "in_W", "out_W", "peel_run_W", "depth_W",
             "max_neighbour_min_io_W", "reconverges_W"]
            + [f"{side}_{d}_W_{agg}" for side in ("pred", "succ") for d in ("in", "out") for agg in ("mean", "max")]
            + ["share_contract", "share_unknown"])


def _h(a: str) -> str:
    return hashlib.sha1(a.encode()).hexdigest()


def _capped(pairs: pd.DataFrame, key: str, val: str, cap: int) -> pd.DataFrame:
    """Keep at most `cap` values per key: those with the lowest address hash (deterministic, design section 4)."""
    sizes = pairs.groupby(key)[val].transform("size")
    small, big = pairs[sizes <= cap], pairs[sizes > cap]
    if big.empty:
        return small
    big = big.assign(_h=big[val].map(_h)).sort_values([key, "_h"]).groupby(key).head(cap).drop(columns="_h")
    return pd.concat([small, big])


def _reconverges(succ: pd.DataFrame, targets: pd.Index, chunk: int = 20000) -> set:
    """Accounts in `targets` with two distinct successors reaching a common account (the successor itself or one hop
    on). Integer codes and chunks keep memory bounded on real weeks (hub successors make the join large)."""
    codes = pd.Index(pd.unique(pd.concat([succ["src"], succ["dst"]])))
    s = pd.DataFrame({"src": codes.get_indexer(succ["src"]), "dst": codes.get_indexer(succ["dst"])})
    by_src = s.sort_values("src")
    t = codes.get_indexer(targets[targets.isin(codes)])
    out = set()
    for i in range(0, len(t), chunk):
        part = s[s["src"].isin(t[i:i + chunk])]
        h2 = part.merge(by_src, left_on="dst", right_on="src", suffixes=("", "_2"))[["src", "dst", "dst_2"]]
        reach = pd.concat([part.assign(r=part["dst"]), h2.rename(columns={"dst_2": "r"})])
        reach = reach[reach["r"] != reach["src"]]
        m = reach.groupby(["src", "r"])["dst"].nunique()
        out.update(codes[m[m >= 2].reset_index()["src"].unique()])
    return out


def account_features(edges: pd.DataFrame, classes: dict[str, str], targets=None) -> pd.DataFrame:
    """Features for `targets` (default: every account in the edges). Degrees, depth and peel runs use the whole week."""
    e = edges[edges["category"].isin(LAYERS)].dropna(subset=["dst"])
    e = e.assign(layer=e["category"].map(LAYERS))[["src", "dst", "layer"]].drop_duplicates()
    nodes = pd.Index(pd.unique(pd.concat([e["src"], e["dst"]])), name="address")
    f = pd.DataFrame(index=nodes)
    for L in ("S", "V", "K"):
        x = e[e["layer"] == L]
        f[f"out_{L}"] = x.groupby("src")["dst"].nunique().reindex(nodes, fill_value=0)
        f[f"in_{L}"] = x.groupby("dst")["src"].nunique().reindex(nodes, fill_value=0)
    w = e[e["layer"].isin(["S", "V"])][["src", "dst"]].drop_duplicates()
    f["out_W"] = w.groupby("src")["dst"].nunique().reindex(nodes, fill_value=0)
    f["in_W"] = w.groupby("dst")["src"].nunique().reindex(nodes, fill_value=0)

    # depth: longest chain of W-predecessors, capped
    depth = pd.Series(0, index=nodes)
    for _ in range(DEPTH_CAP):
        nxt = (depth.reindex(w["src"]).to_numpy() + 1)
        cand = pd.Series(nxt, index=w["dst"].to_numpy()).groupby(level=0).max()
        depth = np.minimum(np.maximum(depth, cand.reindex(nodes, fill_value=0)), DEPTH_CAP)
    f["depth_W"] = depth.astype(int)

    # peel runs: peel accounts have in_W == 1 and out_W <= 2; longest path through the account inside them, capped
    peel = set(f.index[(f["in_W"] == 1) & (f["out_W"] <= 2)])
    pw = w[w["src"].isin(peel) & w["dst"].isin(peel)]
    up = pd.Series(0, index=pd.Index(sorted(peel))); down = up.copy()
    for _ in range(PEEL_CAP):
        up = np.minimum(np.maximum(up, (pd.Series(up.reindex(pw["src"]).to_numpy() + 1, index=pw["dst"].to_numpy())
                                         .groupby(level=0).max().reindex(up.index, fill_value=0))), PEEL_CAP)
        down = np.minimum(np.maximum(down, (pd.Series(down.reindex(pw["dst"]).to_numpy() + 1, index=pw["src"].to_numpy())
                                             .groupby(level=0).max().reindex(down.index, fill_value=0))), PEEL_CAP)
    f["peel_run_W"] = (up + down + 1).reindex(nodes, fill_value=0).clip(upper=PEEL_CAP).astype(int)

    # max over W-neighbours of min(in_W, out_W)
    mio = np.minimum(f["in_W"], f["out_W"])
    nb = pd.concat([w.rename(columns={"src": "a", "dst": "b"}), w.rename(columns={"dst": "a", "src": "b"})])
    f["max_neighbour_min_io_W"] = (pd.Series(mio.reindex(nb["b"]).to_numpy(), index=nb["a"].to_numpy())
                                   .groupby(level=0).max().reindex(nodes, fill_value=0).astype(int))

    # reconvergence: two distinct W-successors s1 != s2 of n reach a common account r, where r is s itself or one hop on
    tg = nodes if targets is None else pd.Index(targets).intersection(nodes)
    rec = _reconverges(_capped(w, "src", "dst", SUCC_CAP), tg)
    f["reconverges_W"] = f.index.isin(list(rec)).astype(int)

    # neighbour aggregates over W-predecessors and W-successors
    for side, (a, b) in {"pred": ("dst", "src"), "succ": ("src", "dst")}.items():
        for d in ("in", "out"):
            vals = pd.Series(f[f"{d}_W"].reindex(w[b]).to_numpy(), index=w[a].to_numpy()).groupby(level=0)
            f[f"{side}_{d}_W_mean"] = vals.mean().reindex(nodes, fill_value=0.0)
            f[f"{side}_{d}_W_max"] = vals.max().reindex(nodes, fill_value=0).astype(float)

    # share of all distinct counterparties (any layer, either direction) by as-of class
    cp = pd.concat([e[["src", "dst"]].rename(columns={"src": "a", "dst": "b"}),
                    e[["dst", "src"]].rename(columns={"dst": "a", "src": "b"})]).drop_duplicates()
    cls = cp["b"].map(lambda x: classes.get(x, "unknown"))
    tot = cp.groupby("a").size()
    for k in ("contract", "unknown"):
        f[f"share_{k}"] = (cp[cls.to_numpy() == k].groupby("a").size().reindex(nodes, fill_value=0) / tot.reindex(nodes)).fillna(0.0)
    return f[FEATURES] if targets is None else f.loc[tg, FEATURES]
