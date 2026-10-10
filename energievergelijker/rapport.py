"""Markdown-rapport en korte melding op basis van een Analyse."""

from __future__ import annotations

from .vergelijk import Analyse

MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()


def euro(x: float) -> str:
    teken = "-" if x < 0 else ""
    return f"{teken}€ {abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float) -> str:
    return f"{x:.1%}".replace(".", ",")


def maandnaam(a: Analyse) -> str:
    return f"{MAANDEN[a.maand.month - 1]} {a.maand.year}"


def kop(a: Analyse) -> str:
    if a.melding:
        return (
            f"{a.beste.naam} is naar verwachting {euro(a.beste.verschil_jaar)} per jaar goedkoper dan "
            f"{a.huidig.naam}"
        )
    return f"{a.huidig.naam} is nog steeds een van de voordeligste opties"


def markdown(a: Analyse) -> str:
    r = []
    r.append(f"# Energierapport {maandnaam(a)}\n")
    r.append(f"**Conclusie: {kop(a)}.**\n")
    if a.melding:
        r.append(
            f"Overstappen naar **{a.beste.naam}** ({a.beste.soort}) levert op basis van jouw verbruik van "
            f"de afgelopen {a.aantal_maanden} maanden circa **{euro(a.beste.verschil_jaar)} per jaar** "
            f"({euro(a.beste.verschil_jaar / 12)} per maand) op.\n"
        )
    if a.tarieven_verouderd:
        r.append(
            f"> ⚠️ De leverancierstarieven zijn {a.tarieven_leeftijd_dagen} dagen oud. "
            "Werk `config/leveranciers.toml` bij voor een betrouwbare vergelijking.\n"
        )

    r.append(f"## Jouw verbruik — {maandnaam(a)}\n")
    r.append("| | |\n|---|---|")
    r.append(f"| Verbruik | {a.kwh_maand:,.0f} kWh |".replace(",", "."))
    r.append(f"| Kosten Tibber (energie + vaste kosten) | {euro(a.kosten_maand_tibber)} |")
    if a.gem_prijs_maand is not None:
        r.append(f"| Jouw gemiddelde prijs | {euro(a.gem_prijs_maand)}/kWh |")
    if a.gem_marktprijs_maand is not None:
        r.append(f"| Gemiddelde uurprijs die maand | {euro(a.gem_marktprijs_maand)}/kWh |")
    r.append(
        f"| Aandeel daluren | {a.dalfractie:.0%}{'' if a.dalfractie_gemeten else ' (aanname)'} |"
    )
    r.append("")
    if a.gem_prijs_maand is not None and a.gem_marktprijs_maand:
        verschil = (a.gem_marktprijs_maand - a.gem_prijs_maand) / a.gem_marktprijs_maand
        if verschil > 0:
            r.append(
                f"Je verbruikt slim: je betaalt gemiddeld {pct(verschil)} minder dan de gemiddelde uurprijs.\n"
            )
        else:
            r.append(
                f"Je verbruik valt vaker in dure uren: je betaalt {pct(-verschil)} meer dan de gemiddelde "
                "uurprijs. Verschuif wassen, laden en verwarmen naar goedkope uren.\n"
            )

    if a.zon:
        r.extend(zonnepanelen(a))

    r.append("## Vergelijking leveranciers\n")
    r.append(
        f"Basis: {a.kwh_jaar:,.0f} kWh/jaar".replace(",", ".")
        + (f", {a.teruglevering_jaar:,.0f} kWh teruglevering".replace(",", ".") if a.teruglevering_jaar else "")
        + (f" (opgeschaald uit {a.aantal_maanden} maanden)" if a.aantal_maanden < 12 else "")
        + ".\n"
    )
    r.append("| # | Leverancier | Type | Kosten vorige maand | Kosten per jaar | Voordeel per jaar |")
    r.append("|---|---|---|---:|---:|---:|")
    for i, x in enumerate(a.resultaten, 1):
        naam = f"**{x.naam}** (huidig)" if x.huidig else x.naam
        voordeel = "—" if x.huidig else euro(x.verschil_jaar)
        r.append(
            f"| {i} | {naam} | {x.soort} | {euro(x.kosten_maand)} | {euro(x.kosten_jaar)} | {voordeel} |"
        )
    r.append("")
    if a.resultaten[0].kosten_jaar_zonder_saldering is not None:
        r.extend(scenario_2027(a))
    bonussen = [x for x in a.resultaten if x.welkomstbonus]
    if bonussen:
        r.append("Eenmalige welkomstbonussen (niet in de jaarkosten verwerkt): "
                 + ", ".join(f"{x.naam} {euro(x.welkomstbonus)}" for x in bonussen) + ".\n")

    r.append("## Toelichting\n")
    r.append(
        "- Alle bedragen incl. btw. Netbeheerkosten en vermindering energiebelasting zijn bij elke "
        "leverancier gelijk en zijn weggelaten.\n"
        "- Dynamische alternatieven: dezelfde uurprijzen als Tibber; alleen inkoopvergoeding, vaste kosten "
        "en terugleverkosten verschillen. Dit verschil is exact.\n"
        "- Vaste contracten: terugkijkende vergelijking. Of vast in de komende periode goedkoper is, hangt "
        "af van de toekomstige marktprijzen.\n"
        "- De salderingsregeling stopt per 1 januari 2027; zet dan `saldering = false` in de configuratie.\n"
        "- Controleer tarieven altijd op de site van de leverancier vóór je overstapt. Tibber heeft geen "
        "opzegtermijn of opzegboete.\n"
    )
    r.append("### Bronnen tarieven\n")
    for x in a.resultaten:
        if x.bron:
            r.append(f"- {x.naam}: {x.bron}")
    r.append("")
    return "\n".join(r)


def kwh(x: float) -> str:
    return f"{x:,.0f} kWh".replace(",", ".")


def zonnepanelen(a: Analyse) -> list[str]:
    opwek = sum(z.opwek for z in a.zon)
    terug = sum(z.teruglevering for z in a.zon)
    eigen = sum(z.eigen_verbruik for z in a.zon)
    totaal = sum(z.totaal_verbruik for z in a.zon)
    r = [f"## Zonnepanelen (SolarEdge) — laatste {len(a.zon)} maanden\n"]
    r.append(
        f"Opwek {kwh(opwek)}, waarvan {kwh(eigen)} direct zelf verbruikt "
        f"(**zelfconsumptie {pct(eigen / opwek if opwek else 0)}**) en {kwh(terug)} teruggeleverd. "
        f"Je panelen dekken {pct(eigen / totaal if totaal else 0)} van je totale stroomverbruik "
        f"({kwh(totaal)}).\n"
    )
    r.append("| Maand | Opwek | Eigen verbruik | Teruglevering | Afname net | Zelfconsumptie |")
    r.append("|---|---:|---:|---:|---:|---:|")
    for z in a.zon:
        jaar, mnd = z.maand.split("-")
        r.append(
            f"| {MAANDEN[int(mnd) - 1][:3]} {jaar} | {kwh(z.opwek)} | {kwh(z.eigen_verbruik)} | "
            f"{kwh(z.teruglevering)} | {kwh(z.afname_net)} | {pct(z.zelfconsumptie)} |"
        )
    r.append("")
    r.append(
        "Vanaf 2027 (einde saldering) is elke kWh die je zelf verbruikt in plaats van teruglevert circa "
        "€ 0,20–0,25 waard. Verschuif verbruik (wassen, laden, boiler) naar zonnige uren om de "
        "zelfconsumptie te verhogen.\n"
    )
    return r


def scenario_2027(a: Analyse) -> list[str]:
    r = ["### Scenario vanaf 2027 (zonder salderingsregeling)\n"]
    r.append("| Leverancier | Kosten per jaar | Voordeel t.o.v. huidig |")
    r.append("|---|---:|---:|")
    for x in sorted(a.resultaten, key=lambda x: x.kosten_jaar_zonder_saldering):
        naam = f"**{x.naam}** (huidig)" if x.huidig else x.naam
        voordeel = "—" if x.huidig else euro(x.verschil_jaar_zonder_saldering)
        r.append(f"| {naam} | {euro(x.kosten_jaar_zonder_saldering)} | {voordeel} |")
    r.append("")
    return r
