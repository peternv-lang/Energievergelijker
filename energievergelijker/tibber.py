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
    geschat: bool = False  # kosten/opbrengst geschat (handmatig ingevoerde kWh, geen Tibber-data)


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


# De API geeft per verzoek maximaal ~1 maand aan dagwaarden; daarom terugbladeren met `before`.
DAG_QUERY = """
query($id: ID!, $voor: String) {
  viewer {
    home(id: $id) {
      %s(resolution: DAILY, last: 31, before: $voor) {
        pageInfo { startCursor hasPreviousPage }
        nodes { from %s }
      }
    }
  }
}
"""


def _vraag(token: str, query: str, variabelen: dict | None = None) -> dict:
    verzoek = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query, "variables": variabelen or {}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(verzoek, timeout=60) as antwoord:
        resultaat = json.load(antwoord)
    if resultaat.get("errors"):
        raise RuntimeError(f"Tibber API fout: {resultaat['errors']}")
    return resultaat["data"]


def _dagen(token: str, huis_id: str, veld: str, waarde: str, max_paginas: int = 13) -> list[dict]:
    nodes, voor = [], None
    for _ in range(max_paginas):
        verbinding = _vraag(token, DAG_QUERY % (veld, waarde), {"id": huis_id, "voor": voor})["viewer"]["home"][veld]
        nodes = verbinding["nodes"] + nodes
        if not verbinding["pageInfo"]["hasPreviousPage"] or not verbinding["nodes"]:
            break
        voor = verbinding["pageInfo"]["startCursor"]
    return nodes


def haal_op(token: str, huis_index: int = 0) -> TibberData:
    home = _vraag(token, QUERY)["viewer"]["homes"][huis_index]
    home["dag"] = {"nodes": _dagen(token, home["id"], "consumption", "consumption")}
    home["dagproductie"] = {"nodes": _dagen(token, home["id"], "production", "production")}
    return parse(home)


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
