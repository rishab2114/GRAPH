"""Typed records following the shared contract proposed in AGENT_DISCUSSION.md (Atom, Combination, Scenario, Run).
IDs are content hashes, so the same content always has the same id across repositories."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

import networkx as nx

SCHEMA_VERSION = "0.1"


def content_id(prefix: str, payload) -> str:
    return prefix + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class Combination:
    atoms: list[str]
    relation: str = "co-constraint"            # all atoms constrain one schedule
    scores: dict = field(default_factory=dict)  # coherence / availability / rarity kept separate (none yet in E01)
    id: str = ""

    def __post_init__(self):
        self.id = self.id or content_id("cmb_", {"atoms": sorted(self.atoms), "relation": self.relation})


@dataclass
class Scenario:
    combination_id: str
    template: str
    seed: int
    spec: dict
    family_hash: str                           # instance fingerprint (dedup / renaming checks)
    target: dict                               # solver output: status, makespan, gap, certificate
    verification: list[str]                    # verifier output on the solver's schedule ([] = valid)
    complexity: dict
    family: str = ""                           # composition family: the split unit (Codex L08)
    hasher: str = f"networkx {nx.__version__} WL-4"
    schema: str = SCHEMA_VERSION
    id: str = ""

    def __post_init__(self):
        self.id = self.id or content_id("scn_", self.spec)


@dataclass
class Run:
    scenario_id: str
    learner: str
    prediction: dict
    outcome: dict
    schema: str = SCHEMA_VERSION
    id: str = ""

    def __post_init__(self):
        self.id = self.id or content_id("run_", {"s": self.scenario_id, "l": self.learner, "p": self.prediction})


def to_json(rec) -> str:
    return json.dumps(asdict(rec), sort_keys=True)
