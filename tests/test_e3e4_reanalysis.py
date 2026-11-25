import numpy as np

from gffs.e3e4_reanalysis import cluster_recall, strict_threshold


def test_strict_threshold_never_exceeds_target_even_with_ties():
    s = np.array([0.0] * 90 + [0.5] * 6 + [0.9] * 4)          # ties at 0.5: ">= quantile" would flag 10%
    t, rate = strict_threshold(s, 0.05)
    assert t == 0.5 and rate == 0.04 and (s > t).mean() <= 0.05
    t, rate = strict_threshold(np.zeros(10), 0.05)            # all equal: flags nobody
    assert rate == 0.0


def test_cluster_recall_resamples_whole_instances_and_supports_both_weightings():
    flags = np.array([1, 1, 1, 1, 0, 0])                       # instance 0 has 4 nodes, instance 1 has 2
    inst = np.array([0, 0, 0, 0, 1, 1])
    assert cluster_recall(flags, inst, np.array([0, 1])) == 4 / 6                       # node-weighted
    assert cluster_recall(flags, inst, np.array([0, 1]), equal_instances=True) == 0.5   # instance-weighted
    assert cluster_recall(flags, inst, np.array([1, 1])) == 0.0                          # a draw of instance 1 twice
