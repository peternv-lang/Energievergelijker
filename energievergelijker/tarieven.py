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
    zonnebonus_pct: float = 0.0  # bonus over (marktprijs + vergoeding) op teruglevering
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
    batterij_kwh: float = 0.0
    huidig_vanaf: date | None = None
    vorige: str | None = None
    prijsbasis: str = "Tibber"  # leverancier waarvan de (historische) kosten/prijzen komen
    dynamisch: list[Dynamisch] = field(default_factory=list)
    vast: list[Vast] = field(default_factory=list)

    def contract(self, naam: str) -> Dynamisch:
        for d in self.dynamisch:
            if d.naam == naam:
                return d
        raise ValueError(f"Contract '{naam}' staat niet onder [[dynamisch]]")

    def huidig_op(self, maand: date) -> str:
        """Leverancier die in `maand` leverde (rekening houdend met een overstap)."""
        if self.huidig_vanaf and self.vorige and maand < self.huidig_vanaf:
            return self.vorige
        return self.huidig


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
        batterij_kwh=alg.get("batterij_kwh", 0.0),
        huidig_vanaf=cfg["huidig"].get("vanaf"),
        vorige=cfg["huidig"].get("vorige"),
        prijsbasis=cfg["huidig"].get("prijsbasis", "Tibber"),
        dynamisch=[Dynamisch(**d) for d in cfg.get("dynamisch", [])],
        vast=[Vast(**v) for v in cfg.get("vast", [])],
    )
