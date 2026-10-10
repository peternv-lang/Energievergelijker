"""Genereert tests/demo_home.json: een fictief Tibber-huis met 12 maanden verbruik."""

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=2))
EB = 0.11085
OPSLAG = 0.018


def genereer(eind=datetime(2026, 10, 1, tzinfo=TZ), seed=1):
    rnd = random.Random(seed)
    maanden, uren = [], []
    start = datetime(eind.year - 1, eind.month, 1, tzinfo=TZ)
    t = start
    while t < eind:
        seizoen = 1 + 0.35 * math.cos((t.month - 1) / 12 * 2 * math.pi)
        spot = max(-0.02, 0.09 + 0.05 * math.sin((t.hour - 13) / 24 * 2 * math.pi) * -1 + rnd.gauss(0, 0.02))
        prijs = round((spot * 1.21) + EB + OPSLAG, 4)
        piek = 1.8 if 17 <= t.hour <= 21 else (0.6 if t.hour < 7 else 1.0)
        kwh = round(0.32 * seizoen * piek * rnd.uniform(0.7, 1.3), 3)
        uren.append({"from": t.isoformat(), "to": (t + timedelta(hours=1)).isoformat(),
                     "cost": round(kwh * prijs, 4), "unitPrice": prijs, "consumption": kwh})
        t += timedelta(hours=1)
    per_maand = {}
    for u in uren:
        k = u["from"][:7]
        m = per_maand.setdefault(k, {"from": u["from"][:7] + "-01T00:00:00+02:00", "cost": 0, "consumption": 0})
        m["cost"] += u["cost"]
        m["consumption"] += u["consumption"]
    for m in per_maand.values():
        m["to"] = m["from"]
        maanden.append(m)
    return {"id": "demo", "appNickname": "Demo", "maand": {"nodes": maanden},
            "uur": {"nodes": uren[-1500:]}, "productie": {"nodes": []}}


if __name__ == "__main__":
    Path(__file__).with_name("demo_home.json").write_text(json.dumps(genereer()))
