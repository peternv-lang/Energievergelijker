"""Verbruiksdata samenstellen uit Tibber-archief en handmatige invoer (na de overstap).

Handmatige maanden hebben alleen kWh. Kosten en opbrengst worden geschat met de Tibber-prijzen
(per kWh) van dezelfde kalendermaand in een eerder jaar; de vergelijking tussen dynamische
leveranciers hangt alleen van de kWh af en blijft dus exact.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

from .tibber import Dag, Periode, TibberData


def _lees(pad: Path) -> list[dict]:
    if not pad.exists():
        return []
    with open(pad, newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def _maandstart(maand: str) -> datetime:
    j, m = maand.split("-")
    return datetime(int(j), int(m), 1, tzinfo=timezone.utc)


def laad_archief(map_: Path) -> TibberData:
    data = TibberData(huis="archief")
    for r in _lees(map_ / "tibber_maanden.csv"):
        data.maanden.append(
            Periode(
                start=_maandstart(r["maand"]),
                kwh=float(r["afname_kwh"]),
                kosten=float(r["kosten_eur"]),
                teruglevering_kwh=float(r["teruglevering_kwh"]),
                opbrengst=float(r["opbrengst_eur"]),
            )
        )
    for r in _lees(map_ / "tibber_dagen.csv"):
        data.dagen.append(
            Dag(date.fromisoformat(r["datum"]), float(r["afname_kwh"]), float(r["teruglevering_kwh"]))
        )
    return data


def _prijzen(maanden: list[Periode], kalendermaand: int) -> tuple[float, float]:
    """(kosten per kWh afname, opbrengst per kWh teruglevering) uit gemeten Tibber-maanden."""
    gemeten = [m for m in maanden if not m.geschat]
    zelfde = [m for m in gemeten if m.start.month == kalendermaand] or gemeten
    kwh = sum(m.kwh for m in zelfde)
    prod = sum(m.teruglevering_kwh for m in zelfde)
    return (
        sum(m.kosten for m in zelfde) / kwh if kwh else 0.0,
        sum(m.opbrengst for m in zelfde) / prod if prod else 0.0,
    )


def vul_aan(data: TibberData, handmatig: Path) -> TibberData:
    """Voegt handmatig ingevoerde maanden toe die niet (of leeg) in de Tibber-data zitten."""
    bekend = {f"{m.start:%Y-%m}" for m in data.maanden if m.kwh > 0}
    for r in _lees(handmatig):
        maand = r["maand"].strip()
        if maand in bekend:
            continue
        start = _maandstart(maand)
        kwh = float(r["afname_kwh"])
        prod = float(r.get("teruglevering_kwh") or 0)
        prijs, vergoeding = _prijzen(data.maanden, start.month)
        data.maanden = [m for m in data.maanden if f"{m.start:%Y-%m}" != maand]
        data.maanden.append(Periode(start, kwh, kwh * prijs, prod, prod * vergoeding, geschat=True))
    data.maanden.sort(key=lambda m: m.start)
    return data
