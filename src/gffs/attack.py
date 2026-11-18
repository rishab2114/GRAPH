"""Turn one ATT&CK STIX release into entity -> technique-set mappings."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ENTITY_TYPES = ("intrusion-set", "malware", "tool", "campaign")


def parent_id(external_id: str) -> str:
    """Collapse a sub-technique ID to its parent: T1059.001 -> T1059."""
    return external_id.split(".", 1)[0]


def _inactive(obj: dict) -> bool:
    return bool(obj.get("revoked") or obj.get("x_mitre_deprecated"))


def _attack_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
            return ref["external_id"]
    return None


def technique_sets(bundle: dict) -> dict[str, frozenset[str]]:
    """Map each active entity's STIX id to the parent technique IDs it `uses`.

    Revoked/deprecated techniques, entities and relationships are ignored.
    Entities that end up with no techniques are left out.
    """
    objects = bundle.get("objects", [])
    techniques: dict[str, str] = {}
    entities: set[str] = set()
    for obj in objects:
        if _inactive(obj):
            continue
        if obj.get("type") == "attack-pattern":
            tid = _attack_id(obj)
            if tid:
                techniques[obj["id"]] = parent_id(tid)
        elif obj.get("type") in ENTITY_TYPES:
            entities.add(obj["id"])

    uses: dict[str, set[str]] = defaultdict(set)
    for obj in objects:
        if obj.get("type") != "relationship" or obj.get("relationship_type") != "uses":
            continue
        if _inactive(obj):
            continue
        src, tgt = obj.get("source_ref"), obj.get("target_ref")
        if src in entities and tgt in techniques:
            uses[src].add(techniques[tgt])
    return {e: frozenset(ts) for e, ts in uses.items() if ts}


def load_bundle(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
