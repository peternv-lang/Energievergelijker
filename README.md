# Energievergelijker

Maandelijkse monitor van een **Tibber dynamisch stroomcontract**. Haalt je werkelijke verbruik en kosten op
via de Tibber API, rekent dat door tegen andere dynamische en vaste contracten, en maakt een GitHub-issue
(= e-mailmelding) zodra een alternatief meer dan de ingestelde drempel per jaar oplevert.

## Wat het rapport laat zien

- Verbruik, kosten en gemiddelde kWh-prijs van de afgelopen maand
- Of je slim verbruikt: jouw gewogen prijs vs. de gemiddelde uurprijs
- Ranglijst van leveranciers op jaarkosten (laatste 12 maanden), met verwacht voordeel t.o.v. Tibber
- Met SolarEdge: opwek, eigen verbruik, teruglevering en zelfconsumptie per maand
- Scenario vanaf 2027 (einde salderingsregeling) per leverancier
- Waarschuwing als de tarieventabel verouderd is

Rapporten komen in `rapporten/JJJJ-MM.md` (+ `.json`).

## Installatie (eenmalig, ±5 minuten)

1. Maak een Tibber API-token aan op <https://developer.tibber.com/settings/access-token>.
2. Zet het token in GitHub: *Settings → Secrets and variables → Actions → New repository secret*,
   naam `TIBBER_TOKEN`.
3. Optioneel, voor zonnepanelen: maak op <https://monitoring.solaredge.com> via *Admin → Site Access →
   API Access* een API-sleutel aan en zet die als secret `SOLAREDGE_API_KEY`. `SOLAREDGE_SITE_ID` is
   optioneel; zonder wordt je eerste installatie gebruikt.
4. Zorg dat je e-mailmeldingen voor issues in deze repository aan hebt (*Watch → Custom → Issues*).
5. Start de eerste run handmatig: *Actions → Maandelijkse energievergelijking → Run workflow*.

Daarna draait hij automatisch op de 3e van elke maand.

## Lokaal draaien

```bash
export TIBBER_TOKEN=...
python -m energievergelijker            # live data
python tests/maak_demo.py && python -m energievergelijker --demo tests/demo_home.json
PYTHONPATH=.:tests python -m unittest discover -s tests
```

Geen externe packages nodig (Python ≥ 3.11).

## Tarieven bijhouden

Er bestaat geen openbare API met leverancierstarieven; die staan in `config/leveranciers.toml`.
Werk ze elke 1–2 maanden bij (het rapport en een issue waarschuwen na 60 dagen). Instelbaar:

| Instelling | Betekenis |
|---|---|
| `drempel_besparing_per_jaar` | Minimale besparing voor een melding (standaard € 50) |
| `saldering` | Zet op `false` per 1-1-2027 (einde salderingsregeling) |
| `energiebelasting_per_kwh` | Jaarlijks bijwerken |

## Rekenmethode

- Alle bedragen incl. btw. Netbeheerkosten en vermindering energiebelasting zijn bij elke leverancier gelijk
  en worden weggelaten.
- **Dynamisch**: de uurprijs is bij iedereen gelijk, dus het verschil met Tibber is exact
  `kWh × Δinkoopvergoeding + maanden × Δvaste kosten + teruglevering × Δterugleverkosten − zonnebonus`.
  Tibber-tarieven zijn gecontroleerd tegen de eigen factuur (sep 2026).
- **Vast**: jouw werkelijke kWh, gesplitst in normaal/dal op basis van je uurverbruik, × het all-in tarief.
  Dit is terugkijkend; toekomstige marktprijzen bepalen of vast dan echt goedkoper is.
- Minder dan 12 maanden historie wordt lineair opgeschaald naar een jaar.
