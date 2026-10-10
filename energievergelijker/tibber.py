"""Ophalen van verbruik en kosten via de Tibber GraphQL API."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime

API_URL = "https://api.tibber.com/v1-beta/gql"

QUERY = """
{
  viewer {
    homes {
      id
      appNickname
      maand: consumption(resolution: MONTHLY, last: 12) {
        nodes { from to cost consumption }
      }
      uur: consumption(resolution: HOURLY, last: 1500) {
        nodes { from to cost unitPrice consumption }
      }
      productie: production(resolution: MONTHLY, last: 12) {
        nodes { from to profit production }
      }
      dag: consumption(resolution: DAILY, last: 366) {
        nodes { from consumption }
      }
      dagproductie: production(resolution: DAILY, last: 366) {
        nodes { from production }
      }
    }
  }
}
"""


@dataclass
class Periode:
    start: datetime
    kwh: float
    kosten: float  # Tibber-energiekosten incl. belasting en btw, excl. vaste kosten
    teruglevering_kwh: float = 0.0
    opbrengst: float = 0.0  # Tibber-vergoeding voor teruglevering


@dataclass
class Uur:
    start: datetime
    kwh: float
    kosten: float
    prijs: float


@dataclass
class Dag:
    datum: date
    afname: float
    teruglevering: float


@dataclass
class TibberData:
    huis: str
    maanden: list[Periode] = field(default_factory=list)
    uren: list[Uur] = field(default_factory=list)
    dagen: list[Dag] = field(default_factory=list)


def _dt(waarde: str) -> datetime:
    return datetime.fromisoformat(waarde)


def haal_op(token: str, huis_index: int = 0) -> TibberData:
    verzoek = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": QUERY}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(verzoek, timeout=60) as antwoord:
        resultaat = json.load(antwoord)
    if resultaat.get("errors"):
        raise RuntimeError(f"Tibber API fout: {resultaat['errors']}")
    return parse(resultaat["data"]["viewer"]["homes"][huis_index])


def parse(home: dict) -> TibberData:
    productie = {
        n["from"][:7]: n for n in (home.get("productie") or {}).get("nodes", []) if n.get("production") is not None
    }
    data = TibberData(huis=home.get("appNickname") or home["id"])
    for n in home["maand"]["nodes"]:
        if n.get("consumption") is None:
            continue
        p = productie.get(n["from"][:7], {})
        data.maanden.append(
            Periode(
                start=_dt(n["from"]),
                kwh=n["consumption"],
                kosten=n.get("cost") or 0.0,
                teruglevering_kwh=p.get("production") or 0.0,
                opbrengst=p.get("profit") or 0.0,
            )
        )
    dagprod = {
        n["from"][:10]: n["production"]
        for n in (home.get("dagproductie") or {}).get("nodes", [])
        if n.get("production") is not None
    }
    for n in (home.get("dag") or {}).get("nodes", []):
        if n.get("consumption") is not None:
            d = n["from"][:10]
            data.dagen.append(Dag(date.fromisoformat(d), n["consumption"], dagprod.get(d, 0.0)))
    for n in home["uur"]["nodes"]:
        if n.get("consumption") is None:
            continue
        data.uren.append(Uur(_dt(n["from"]), n["consumption"], n.get("cost") or 0.0, n.get("unitPrice") or 0.0))
    return data
