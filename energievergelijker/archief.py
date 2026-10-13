"""Bewaart Tibber-historie als CSV in de repository, zodat die na opzeggen beschikbaar blijft."""

from __future__ import annotations

import csv
from pathlib import Path

from .tibber import TibberData


def _schrijf(pad: Path, kolommen: list[str], nieuw: dict[str, dict]) -> None:
    rijen: dict[str, dict] = {}
    if pad.exists():
        with open(pad, newline="") as f:
            rijen = {r[kolommen[0]]: r for r in csv.DictReader(f)}
    rijen.update(nieuw)  # nieuwe API-data overschrijft eerdere (onvolledige) waarden
    pad.parent.mkdir(parents=True, exist_ok=True)
    with open(pad, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=kolommen)
        w.writeheader()
        w.writerows(rijen[k] for k in sorted(rijen))


def bewaar(data: TibberData, map_: Path) -> None:
    _schrijf(
        map_ / "tibber_maanden.csv",
        ["maand", "afname_kwh", "kosten_eur", "teruglevering_kwh", "opbrengst_eur"],
        {
            f"{m.start:%Y-%m}": {
                "maand": f"{m.start:%Y-%m}",
                "afname_kwh": round(m.kwh, 3),
                "kosten_eur": round(m.kosten, 2),
                "teruglevering_kwh": round(m.teruglevering_kwh, 3),
                "opbrengst_eur": round(m.opbrengst, 2),
            }
            for m in data.maanden
        },
    )
    _schrijf(
        map_ / "tibber_dagen.csv",
        ["datum", "afname_kwh", "teruglevering_kwh"],
        {
            d.datum.isoformat(): {
                "datum": d.datum.isoformat(),
                "afname_kwh": round(d.afname, 3),
                "teruglevering_kwh": round(d.teruglevering, 3),
            }
            for d in data.dagen
        },
    )
