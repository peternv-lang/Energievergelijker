"""Herberekening van het Tibber-verbruik tegen de tarieven van andere leveranciers.

Uitgangspunten (alle bedragen incl. btw):
- Netbeheerkosten en vermindering energiebelasting zijn overal gelijk en blijven buiten beschouwing.
- Bij dynamische contracten is de kale uurprijs overal gelijk. Het verschil met Tibber is dus
  alleen (inkoopvergoeding, vaste kosten, terugleverkosten) — exact te berekenen uit jouw kWh.
- Vaste contracten worden doorgerekend met het werkelijke verbruik, gesplitst in normaal/dal.
- Jaarbedragen zijn gebaseerd op de laatste (max.) 12 volledige maanden; minder maanden wordt
  lineair opgeschaald en in het rapport gemeld.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime

from .tarieven import Dynamisch, Tarieven, Vast
from .tibber import Periode, TibberData, Uur

STANDAARD_DALFRACTIE = 0.45


@dataclass
class Resultaat:
    naam: str
    soort: str  # "dynamisch" of "vast"
    kosten_maand: float  # vorige volledige maand
    kosten_jaar: float  # (opgeschaalde) laatste 12 maanden
    verschil_jaar: float = 0.0  # positief = goedkoper dan huidig
    welkomstbonus: float = 0.0
    bron: str = ""
    huidig: bool = False
    kosten_jaar_zonder_saldering: float | None = None
    verschil_jaar_zonder_saldering: float | None = None


@dataclass
class Analyse:
    maand: date
    kwh_maand: float
    kosten_maand_tibber: float
    gem_prijs_maand: float | None
    gem_marktprijs_maand: float | None
    kwh_jaar: float
    teruglevering_jaar: float
    aantal_maanden: int
    dalfractie: float
    dalfractie_gemeten: bool
    resultaten: list[Resultaat]
    beste: Resultaat
    huidig: Resultaat
    melding: bool
    tarieven_verouderd: bool
    tarieven_leeftijd_dagen: int
    zon: list[ZonMaand] = field(default_factory=list)


@dataclass
class ZonMaand:
    maand: str  # "JJJJ-MM"
    opwek: float  # kWh volgens SolarEdge
    teruglevering: float  # kWh volgens Tibber
    eigen_verbruik: float  # opwek die direct in huis is gebruikt
    afname_net: float  # kWh volgens Tibber

    @property
    def zelfconsumptie(self) -> float:
        return self.eigen_verbruik / self.opwek if self.opwek else 0.0

    @property
    def totaal_verbruik(self) -> float:
        return self.afname_net + self.eigen_verbruik


def is_dal(t: datetime) -> bool:
    return t.weekday() >= 5 or t.hour >= 23 or t.hour < 7


def dalfractie(uren: list[Uur]) -> tuple[float, bool]:
    totaal = sum(u.kwh for u in uren)
    if totaal <= 0:
        return STANDAARD_DALFRACTIE, False
    return sum(u.kwh for u in uren if is_dal(u.start)) / totaal, True


def _dynamisch(d: Dynamisch, ref: Dynamisch, maanden: list[Periode], t: Tarieven) -> float:
    kwh = sum(m.kwh for m in maanden)
    prod = sum(m.teruglevering_kwh for m in maanden)
    basis = sum(m.kosten for m in maanden) - sum(m.opbrengst for m in maanden)
    if t.saldering:
        basis -= min(prod, kwh) * t.energiebelasting_per_kwh
    return (
        basis
        + kwh * (d.inkoopvergoeding_per_kwh - ref.inkoopvergoeding_per_kwh)
        + prod * d.terugleverkosten_per_kwh
        + len(maanden) * d.vaste_kosten_per_maand
    )


def _vast(v: Vast, maanden: list[Periode], dal: float, t: Tarieven) -> float:
    kwh = sum(m.kwh for m in maanden)
    prod = sum(m.teruglevering_kwh for m in maanden)
    tarief = (1 - dal) * v.tarief_normaal + dal * v.tarief_dal
    if t.saldering:
        energie = max(kwh - prod, 0) * tarief - max(prod - kwh, 0) * v.terugleververgoeding_per_kwh
    else:
        energie = kwh * tarief - prod * v.terugleververgoeding_per_kwh
    return energie + prod * v.terugleverkosten_per_kwh + len(maanden) * v.vaste_kosten_per_maand


def analyseer(
    data: TibberData, t: Tarieven, vandaag: date, opwek: dict[str, float] | None = None
) -> Analyse:
    begin_huidige_maand = date(vandaag.year, vandaag.month, 1)
    volledig = sorted(
        (m for m in data.maanden if m.start.date() < begin_huidige_maand), key=lambda m: m.start
    )[-12:]
    if not volledig:
        raise ValueError("Geen volledige maanden verbruik gevonden in de Tibber-data")
    laatste = volledig[-1]
    maand = laatste.start.date().replace(day=1)
    uren_maand = [u for u in data.uren if u.start.year == maand.year and u.start.month == maand.month]
    dal, gemeten = dalfractie(uren_maand or data.uren)

    schaal = 12 / len(volledig)
    ref = t.huidig_contract
    resultaten = [
        Resultaat(
            naam=d.naam,
            soort="dynamisch",
            kosten_maand=_dynamisch(d, ref, [laatste], t),
            kosten_jaar=_dynamisch(d, ref, volledig, t) * schaal,
            bron=d.bron,
            huidig=d.naam == t.huidig,
        )
        for d in t.dynamisch
    ] + [
        Resultaat(
            naam=v.naam,
            soort="vast",
            kosten_maand=_vast(v, [laatste], dal, t),
            kosten_jaar=_vast(v, volledig, dal, t) * schaal,
            welkomstbonus=v.welkomstbonus,
            bron=v.bron,
        )
        for v in t.vast
    ]
    huidig = next(r for r in resultaten if r.huidig)
    for r in resultaten:
        r.verschil_jaar = huidig.kosten_jaar - r.kosten_jaar

    # Scenario vanaf 2027: geen salderingsregeling meer.
    if t.saldering and any(m.teruglevering_kwh for m in volledig):
        t2 = replace(t, saldering=False)
        per_naam = {d.naam: _dynamisch(d, ref, volledig, t2) * schaal for d in t.dynamisch}
        per_naam |= {v.naam: _vast(v, volledig, dal, t2) * schaal for v in t.vast}
        for r in resultaten:
            r.kosten_jaar_zonder_saldering = per_naam[r.naam]
            r.verschil_jaar_zonder_saldering = per_naam[huidig.naam] - per_naam[r.naam]
    resultaten.sort(key=lambda r: r.kosten_jaar)
    beste = resultaten[0]

    gem_prijs = laatste.kosten / laatste.kwh if laatste.kwh else None
    prijzen = [u.prijs for u in uren_maand if u.prijs]
    leeftijd = (vandaag - t.peildatum).days

    return Analyse(
        maand=maand,
        kwh_maand=laatste.kwh,
        kosten_maand_tibber=huidig.kosten_maand,
        gem_prijs_maand=gem_prijs,
        gem_marktprijs_maand=sum(prijzen) / len(prijzen) if prijzen else None,
        kwh_jaar=sum(m.kwh for m in volledig) * schaal,
        teruglevering_jaar=sum(m.teruglevering_kwh for m in volledig) * schaal,
        aantal_maanden=len(volledig),
        dalfractie=dal,
        dalfractie_gemeten=gemeten,
        resultaten=resultaten,
        beste=beste,
        huidig=huidig,
        melding=not beste.huidig and beste.verschil_jaar >= t.drempel_besparing_per_jaar,
        tarieven_verouderd=leeftijd > t.max_leeftijd_tarieven_dagen,
        tarieven_leeftijd_dagen=leeftijd,
        zon=[
            ZonMaand(
                maand=f"{m.start:%Y-%m}",
                opwek=opwek[f"{m.start:%Y-%m}"],
                teruglevering=m.teruglevering_kwh,
                eigen_verbruik=max(opwek[f"{m.start:%Y-%m}"] - m.teruglevering_kwh, 0.0),
                afname_net=m.kwh,
            )
            for m in volledig
            if opwek and f"{m.start:%Y-%m}" in opwek
        ],
    )
