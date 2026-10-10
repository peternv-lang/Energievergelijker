"""Gebruik: python -m energievergelijker [--demo] [--uit rapporten]"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import rapport, solaredge, tarieven, tibber
from .vergelijk import analyseer

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Maandelijkse vergelijking Tibber vs. markt")
    p.add_argument("--config", type=Path, default=ROOT / "config" / "leveranciers.toml")
    p.add_argument("--uit", type=Path, default=ROOT / "rapporten", help="map voor rapporten")
    p.add_argument("--demo", type=Path, help="Tibber-JSON (home-object) i.p.v. live API")
    p.add_argument("--huis", type=int, default=0, help="index van het huis in je Tibber-account")
    args = p.parse_args(argv)

    t = tarieven.laad(args.config)
    if args.demo:
        data = tibber.parse(json.loads(args.demo.read_text()))
    else:
        token = os.environ.get("TIBBER_TOKEN")
        if not token:
            print("Zet TIBBER_TOKEN (aan te maken via https://developer.tibber.com)", file=sys.stderr)
            return 2
        data = tibber.haal_op(token, args.huis)

    opwek = None
    if sleutel := os.environ.get("SOLAREDGE_API_KEY"):
        van = min(m.start for m in data.maanden).date().replace(day=1)
        try:
            opwek = solaredge.haal_op(sleutel, os.environ.get("SOLAREDGE_SITE_ID") or None, van, date.today())
        except Exception as fout:  # rapport gaat door zonder zonnedata
            print(f"SolarEdge niet bereikbaar: {fout}", file=sys.stderr)

    a = analyseer(data, t, date.today(), opwek)
    args.uit.mkdir(parents=True, exist_ok=True)
    naam = f"{a.maand:%Y-%m}"
    (args.uit / f"{naam}.md").write_text(rapport.markdown(a))
    (args.uit / f"{naam}.json").write_text(json.dumps(asdict(a), default=str, indent=2))
    print(rapport.markdown(a))

    if gh_output := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_output, "a") as f:
            f.write(f"melding={'true' if a.melding else 'false'}\n")
            f.write(f"verouderd={'true' if a.tarieven_verouderd else 'false'}\n")
            f.write(f"rapport={args.uit / (naam + '.md')}\n")
            f.write(f"titel={rapport.kop(a)} ({rapport.maandnaam(a)})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
