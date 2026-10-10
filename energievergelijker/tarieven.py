"""Inlezen van leverancierstarieven uit config/leveranciers.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Dynamisch:
    naam: str
    inkoopvergoeding_per_kwh: float
    vaste_kosten_per_maand: float
    terugleverkosten_per_kwh: float = 0.0
    bron: str = ""


@dataclass
class Vast:
    naam: str
    tarief_normaal: float
    tarief_dal: float
    vaste_kosten_per_maand: float
    terugleverkosten_per_kwh: float = 0.0
    terugleververgoeding_per_kwh: float = 0.0
    welkomstbonus: float = 0.0
    bron: str = ""


@dataclass
class Tarieven:
    peildatum: date
    energiebelasting_per_kwh: float
    saldering: bool
    drempel_besparing_per_jaar: float
    max_leeftijd_tarieven_dagen: int
    huidig: str
    dynamisch: list[Dynamisch] = field(default_factory=list)
    vast: list[Vast] = field(default_factory=list)

    @property
    def huidig_contract(self) -> Dynamisch:
        for d in self.dynamisch:
            if d.naam == self.huidig:
                return d
        raise ValueError(f"Huidig contract '{self.huidig}' staat niet onder [[dynamisch]]")


def laad(pad: Path) -> Tarieven:
    with open(pad, "rb") as f:
        cfg = tomllib.load(f)
    alg = cfg["algemeen"]
    return Tarieven(
        peildatum=alg["peildatum"],
        energiebelasting_per_kwh=alg["energiebelasting_per_kwh"],
        saldering=alg.get("saldering", True),
        drempel_besparing_per_jaar=alg.get("drempel_besparing_per_jaar", 50.0),
        max_leeftijd_tarieven_dagen=alg.get("max_leeftijd_tarieven_dagen", 60),
        huidig=cfg["huidig"]["naam"],
        dynamisch=[Dynamisch(**d) for d in cfg.get("dynamisch", [])],
        vast=[Vast(**v) for v in cfg.get("vast", [])],
    )
