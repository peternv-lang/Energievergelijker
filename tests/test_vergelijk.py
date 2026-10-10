import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from energievergelijker import rapport, tarieven, tibber
from energievergelijker.tarieven import Dynamisch, Tarieven, Vast
from energievergelijker.tibber import Periode, TibberData
from energievergelijker.vergelijk import analyseer, is_dal

from maak_demo import genereer

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=2))


def tarieven_basis(**kw):
    t = Tarieven(
        peildatum=date(2026, 10, 1), energiebelasting_per_kwh=0.11085, saldering=True,
        drempel_besparing_per_jaar=50, max_leeftijd_tarieven_dagen=60, huidig="Tibber",
        dynamisch=[
            Dynamisch("Tibber", 0.018, 6.99),
            Dynamisch("Goedkoop", 0.010, 4.99),
        ],
        vast=[Vast("Vast", 0.30, 0.30, 7.0)],
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def data(maanden=12, kwh=250.0, prijs=0.25, prod=0.0):
    return TibberData("x", [
        Periode(datetime(2025, 10, 1, tzinfo=TZ) + timedelta(days=31 * i), kwh, kwh * prijs, prod)
        for i in range(maanden)
    ])


class TestVergelijk(unittest.TestCase):
    def test_dynamisch_verschil_is_opslag_plus_vaste_kosten(self):
        a = analyseer(data(), tarieven_basis(drempel_besparing_per_jaar=40), date(2026, 10, 10))
        goedkoop = next(r for r in a.resultaten if r.naam == "Goedkoop")
        verwacht = 3000 * (0.018 - 0.010) + 12 * (6.99 - 4.99)
        self.assertAlmostEqual(goedkoop.verschil_jaar, verwacht, places=6)
        self.assertEqual(a.beste.naam, "Goedkoop")
        self.assertTrue(a.melding)  # 48 >= 40

    def test_geen_melding_onder_drempel(self):
        a = analyseer(data(), tarieven_basis(drempel_besparing_per_jaar=100), date(2026, 10, 10))
        self.assertFalse(a.melding)

    def test_vast_contract(self):
        a = analyseer(data(), tarieven_basis(), date(2026, 10, 10))
        vast = next(r for r in a.resultaten if r.naam == "Vast")
        self.assertAlmostEqual(vast.kosten_jaar, 3000 * 0.30 + 84, places=6)
        tibber_ = a.huidig
        self.assertAlmostEqual(tibber_.kosten_jaar, 3000 * 0.25 + 12 * 6.99, places=6)

    def test_opschalen_bij_minder_maanden(self):
        a = analyseer(data(maanden=6), tarieven_basis(), date(2026, 10, 10))
        self.assertAlmostEqual(a.kwh_jaar, 3000)
        self.assertEqual(a.aantal_maanden, 6)

    def test_saldering_vast(self):
        a = analyseer(data(prod=100), tarieven_basis(), date(2026, 10, 10))
        vast = next(r for r in a.resultaten if r.naam == "Vast")
        self.assertAlmostEqual(vast.kosten_jaar, 12 * (150 * 0.30 + 7.0), places=6)

    def test_lopende_maand_telt_niet_mee(self):
        a = analyseer(data(maanden=13), tarieven_basis(), date(2026, 10, 10))
        self.assertEqual(a.maand, date(2026, 9, 1))
        self.assertEqual(a.aantal_maanden, 12)

    def test_dal(self):
        self.assertTrue(is_dal(datetime(2026, 10, 10, 12)))  # zaterdag
        self.assertTrue(is_dal(datetime(2026, 10, 12, 23)))
        self.assertFalse(is_dal(datetime(2026, 10, 12, 12)))

    def test_eind_tot_eind_met_demo_en_config(self):
        t = tarieven.laad(ROOT / "config" / "leveranciers.toml")
        a = analyseer(tibber.parse(genereer()), t, date(2026, 10, 10))
        self.assertEqual(a.maand, date(2026, 9, 1))
        self.assertTrue(a.dalfractie_gemeten)
        md = rapport.markdown(a)
        self.assertIn("Energierapport september 2026", md)
        self.assertIn("Tibber", md)


if __name__ == "__main__":
    unittest.main()
