"""Load and validate the frozen AML red-flag vocabulary (config/aml_vocabulary.toml).

The vocabulary defines the nodes of the literature graph (docs/design-option1.md, source A). It is
committed before any counting; this module only reads it and refuses a file that breaks the rules.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path("config/aml_vocabulary.toml")


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    definition: str
    synonyms: tuple[str, ...]
    elliptic: bool       # expressible as a motif on the Elliptic edge list
    motif: str
    evidence: str


@dataclass(frozen=True)
class Vocabulary:
    version: int
    cutoff: str
    anchor_terms: tuple[str, ...]
    concepts: tuple[Concept, ...]

    @property
    def ids(self) -> list[str]:
        return [c.id for c in self.concepts]

    def expressible(self, a: str, b: str) -> bool:
        """A forecast pair is expressible on Elliptic only if both concepts are."""
        by_id = {c.id: c for c in self.concepts}
        return by_id[a].elliptic and by_id[b].elliptic


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("-", " ").split())


def validate(v: Vocabulary) -> None:
    errors: list[str] = []
    ids = v.ids
    if len(ids) != len(set(ids)):
        errors.append("duplicate concept ids")
    if not v.anchor_terms:
        errors.append("scope.anchor_terms is empty")
    anchors = {_norm(a) for a in v.anchor_terms}
    owner: dict[str, str] = {}
    for c in v.concepts:
        if not c.synonyms:
            errors.append(f"{c.id}: no synonyms")
        if not c.motif.strip():
            errors.append(f"{c.id}: no motif")
        for s in c.synonyms:
            n = _norm(s)
            if n in owner and owner[n] != c.id:
                errors.append(f"synonym {s!r} used by {owner[n]} and {c.id}")
            owner.setdefault(n, c.id)
            if any(n in a or a in n for a in anchors):
                errors.append(f"{c.id}: synonym {s!r} overlaps a scope anchor term")
    # A synonym nested inside another concept's synonym would credit one work to both concepts.
    for n, cid in owner.items():
        for m, did in owner.items():
            if cid != did and n != m and f" {n} " in f" {m} ":
                errors.append(f"synonym {n!r} ({cid}) is contained in {m!r} ({did})")
    if errors:
        raise ValueError("invalid vocabulary:\n  " + "\n  ".join(errors))


def load(path: Path = DEFAULT_PATH) -> Vocabulary:
    raw = tomllib.loads(Path(path).read_text())
    concepts = tuple(
        Concept(id=c["id"], label=c["label"], definition=c["definition"], synonyms=tuple(c["synonyms"]),
                elliptic=bool(c["elliptic"]), motif=c["motif"], evidence=c.get("evidence", ""))
        for c in raw["concept"]
    )
    v = Vocabulary(version=int(raw["version"]), cutoff=raw["cutoff"],
                   anchor_terms=tuple(raw["scope"]["anchor_terms"]), concepts=concepts)
    validate(v)
    return v
