from gffs.attack import parent_id, technique_sets


def test_parent_id():
    assert parent_id("T1059.001") == "T1059"
    assert parent_id("T1059") == "T1059"


def test_technique_sets_basic(make_bundle):
    b = make_bundle({"APT-A": ["T1059", "T1078"], "APT-B": ["T1078"]})
    sets = technique_sets(b)
    assert sorted(sets.values(), key=len) == [frozenset({"T1078"}), frozenset({"T1059", "T1078"})]


def test_subtechniques_collapse_to_parent_once(make_bundle):
    b = make_bundle({"APT-A": ["T1059.001", "T1059.003", "T1078"]})
    assert list(technique_sets(b).values()) == [frozenset({"T1059", "T1078"})]


def test_ignores_revoked_and_deprecated(make_bundle):
    b = make_bundle({"APT-A": ["T1059", "T1078", "T1003"]},
                    revoked={"T1003"}, deprecated_rels={("APT-A", "T1078")})
    assert list(technique_sets(b).values()) == [frozenset({"T1059"})]


def test_entity_type_filter(make_bundle):
    b = make_bundle({"APT-A": ["T1059", "T1078"]})
    b["objects"].append({"type": "malware", "id": "malware--m1"})
    b["objects"].append({"type": "relationship", "id": "relationship--m1", "relationship_type": "uses",
                         "source_ref": "malware--m1", "target_ref": "attack-pattern--T1059"})
    assert set(technique_sets(b, entity_types=("malware",))) == {"malware--m1"}
    assert set(technique_sets(b, entity_types=("intrusion-set",))) == {"intrusion-set--APT-A"}
