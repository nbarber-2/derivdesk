import unittest
from derivdesk.mtm import mark_to_market, stop_breached, rolled, direction


class TestDirection(unittest.TestCase):
    def test_parses_both_sides(self):
        for word in ("long", "BUY", "l"):
            self.assertEqual(direction(word), 1)
        for word in ("short", "Sell", "s"):
            self.assertEqual(direction(word), -1)

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            direction("sideways")


class TestMarkToMarket(unittest.TestCase):
    def test_long_gains_when_price_rises(self):
        m = mark_to_market("ES", "long", 2, entry=6100, mark=6120, prior_mark=6110)
        self.assertAlmostEqual(m.daily_pnl, 10 * 2 * 50, delta=1e-9)
        self.assertAlmostEqual(m.open_pnl, 20 * 2 * 50, delta=1e-9)

    def test_short_gains_when_price_falls(self):
        m = mark_to_market("ES", "short", 1, entry=6100, mark=6080, prior_mark=6090)
        self.assertAlmostEqual(m.daily_pnl, 500, delta=1e-9)
        self.assertAlmostEqual(m.open_pnl, 1_000, delta=1e-9)

    def test_short_loses_when_price_rises(self):
        m = mark_to_market("ES", "short", 1, entry=6100, mark=6120, prior_mark=6110)
        self.assertLess(m.daily_pnl, 0)
        self.assertLess(m.open_pnl, 0)

    def test_first_day_defaults_prior_to_entry(self):
        m = mark_to_market("ES", "long", 1, entry=6100, mark=6130)
        self.assertEqual(m.prior_mark, 6100)
        self.assertAlmostEqual(m.daily_pnl, m.open_pnl, delta=1e-9)

    def test_daily_marks_sum_to_open_pnl(self):
        entry, marks = 6100.0, [6110.0, 6095.0, 6140.0, 6132.0]
        prior, total = entry, 0.0
        for mk in marks:
            total += mark_to_market("ES", "long", 3, entry, mk, prior).daily_pnl
            prior = mk
        final = mark_to_market("ES", "long", 3, entry, marks[-1], marks[-2])
        self.assertAlmostEqual(total, final.open_pnl, delta=1e-9)

    def test_short_daily_marks_also_reconcile(self):
        entry, marks = 70.0, [69.2, 71.1, 68.4]
        prior, total = entry, 0.0
        for mk in marks:
            total += mark_to_market("CL", "short", 2, entry, mk, prior).daily_pnl
            prior = mk
        final = mark_to_market("CL", "short", 2, entry, marks[-1], marks[-2])
        self.assertAlmostEqual(total, final.open_pnl, delta=1e-9)

    def test_multiplier_comes_from_the_spec(self):
        self.assertAlmostEqual(mark_to_market("MES", "long", 1, 6100, 6110).daily_pnl,
                               50, delta=1e-9)
        self.assertAlmostEqual(mark_to_market("CL", "long", 1, 70.0, 71.0).daily_pnl,
                               1_000, delta=1e-9)

    def test_contract_month_is_carried(self):
        m = mark_to_market("ES", "long", 1, 6100, 6110, contract_month="DEC26")
        self.assertEqual(m.contract_month, "DEC26")


class TestStops(unittest.TestCase):
    def test_long_stop_triggers_below(self):
        self.assertTrue(stop_breached("long", mark=6080, stop=6082))
        self.assertFalse(stop_breached("long", mark=6090, stop=6082))

    def test_short_stop_triggers_above(self):
        self.assertTrue(stop_breached("short", mark=6205, stop=6202))
        self.assertFalse(stop_breached("short", mark=6190, stop=6202))

    def test_touching_the_stop_counts(self):
        self.assertTrue(stop_breached("long", mark=6082, stop=6082))


class TestRolls(unittest.TestCase):
    def test_detects_a_roll(self):
        self.assertTrue(rolled("SEP26", "DEC26"))

    def test_no_roll_when_months_match(self):
        self.assertFalse(rolled("DEC26", "DEC26"))
        self.assertFalse(rolled("dec26", "DEC26"))

    def test_missing_data_is_not_a_roll(self):
        self.assertFalse(rolled("", "DEC26"))
        self.assertFalse(rolled("DEC26", ""))


if __name__ == "__main__":
    unittest.main()
