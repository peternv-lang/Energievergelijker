"""Ophalen van zonne-opwek per maand via de SolarEdge Monitoring API."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

API_URL = "https://monitoringapi.solaredge.com"


def _get(pad: str, sleutel: str, **params) -> dict:
    query = urllib.parse.urlencode({**params, "api_key": sleutel})
    with urllib.request.urlopen(f"{API_URL}{pad}?{query}", timeout=60) as antwoord:
        return json.load(antwoord)


def eerste_site(sleutel: str) -> str:
    sites = _get("/sites/list", sleutel)["sites"]["site"]
    if not sites:
        raise RuntimeError("Geen SolarEdge-installatie gevonden bij deze API-sleutel")
    return str(sites[0]["id"])


def haal_op(sleutel: str, site_id: str | None, van: date, tot: date) -> dict[str, float]:
    """Opwek in kWh per maand ("JJJJ-MM") van `van` t/m `tot`."""
    site_id = site_id or eerste_site(sleutel)
    antwoord = _get(
        f"/site/{site_id}/energy", sleutel, timeUnit="MONTH", startDate=van.isoformat(), endDate=tot.isoformat()
    )
    return parse(antwoord)


def parse(antwoord: dict) -> dict[str, float]:
    energie = antwoord["energy"]
    factor = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}[energie.get("unit", "Wh")]
    return {v["date"][:7]: v["value"] * factor for v in energie["values"] if v.get("value") is not None}
