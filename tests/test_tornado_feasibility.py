from datetime import date

from gffs.tornado_feasibility import as_of_relayers, classify_as_of, prospective_labels

ZERO = "0x" + "0" * 40


def test_prospective_labels_use_first_participation_after_cutoff_only():
    deps = [{"day": "2022-04-01", "depositor": "a"}, {"day": "2022-05-10", "depositor": "a"},   # a participated before c
            {"day": "2022-05-20", "depositor": "b"},                                               # b: first after c
            {"day": "2022-08-01", "depositor": "c"},                                               # beyond the horizon
            {"day": "2022-05-12", "depositor": "z"}]                                               # z not in the frame
    wds = [{"day": "2022-05-15", "recipient": "d"}]
    lab = prospective_labels(deps, wds, frame={"a", "b", "c", "d"}, cutoff=date(2022, 5, 8), horizon_days=56)
    assert lab["depositor"]["positives"] == {"b"} and lab["depositor"]["prior_participants_excluded"] == {"a"}
    assert lab["depositor"]["participants_outside_frame"] == 1
    assert lab["recipient"]["positives"] == {"d"}


def test_relayers_are_only_those_seen_before_the_cutoff():
    wds = [{"day": "2022-05-01", "relayer": "r1"}, {"day": "2022-05-09", "relayer": "r2"}, {"day": "2022-05-02", "relayer": ZERO}]
    assert as_of_relayers(wds, date(2022, 5, 8)) == {"r1"}


def test_classification_as_of_date_keeps_unknown():
    reg = {"k1": "2021-01-01 00:00:00", "k2": "2022-06-01 00:00:00"}   # k2 created after the cutoff
    c = classify_as_of(["k1", "k2", "e1", "u1"], registry=reg, eoa_evidence={"e1"}, cutoff=date(2022, 5, 8))
    assert c == {"k1": "contract", "k2": "unknown", "e1": "eoa", "u1": "unknown"}
