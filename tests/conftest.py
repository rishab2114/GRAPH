import pytest


def _bundle(uses, *, revoked=frozenset(), deprecated_rels=frozenset()):
    """Minimal STIX bundle: each key of `uses` is an intrusion-set name,
    each value a list of ATT&CK technique external IDs it uses."""
    objects = []
    tech_ids = sorted({t for ts in uses.values() for t in ts})
    for tid in tech_ids:
        obj = {
            "type": "attack-pattern",
            "id": f"attack-pattern--{tid}",
            "external_references": [{"source_name": "mitre-attack", "external_id": tid}],
        }
        if tid in revoked:
            obj["revoked"] = True
        objects.append(obj)
    for name, ts in uses.items():
        objects.append({"type": "intrusion-set", "id": f"intrusion-set--{name}", "name": name})
        for tid in ts:
            rel = {
                "type": "relationship",
                "id": f"relationship--{name}-{tid}",
                "relationship_type": "uses",
                "source_ref": f"intrusion-set--{name}",
                "target_ref": f"attack-pattern--{tid}",
            }
            if (name, tid) in deprecated_rels:
                rel["x_mitre_deprecated"] = True
            objects.append(rel)
    return {"type": "bundle", "id": "bundle--test", "objects": objects}


@pytest.fixture
def make_bundle():
    return _bundle
