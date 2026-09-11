import unittest
from derivdesk import contracts
from derivdesk.sizing import RiskLimits, size_position, downsize_to_micro

EQUITY = 100_000.0


class TestLimits(unittest.TestCase):
    def test_budgets(self):
        lim = RiskLimits()
        self.assertEqual(lim.risk_budget(EQUITY), 5_000)
        self.assertEqual(lim.margin_budget(EQUITY), 40_000)
        self.assertEqual(lim.halt_level(EQUITY), 10_000)


class TestSizing(unittest.TestCase):
    def test_risk_is_the_binding_constraint_on_a_wide_stop(self):
        s = size_position(EQUITY, 6142, 6082, "ES")
        self.assertEqual(s.contracts, 1)
        self.assertAlmostEqual(s.risk_per_contract, 3_000, delta=1e-9)
        self.assertLessEqual(s.total_risk, 5_000)
        self.assertEqual(s.binding_constraint, "per-trade risk")

    def test_margin_binds_when_the_stop_is_tight(self):
        s = size_position(EQUITY, 6142, 6137, "ES", margin_per_contract=17_600)
        self.assertEqual(s.contracts, 2)
        self.assertEqual(s.binding_constraint, "margin budget")
        self.assertLessEqual(s.margin_required, 40_000)

    def test_platform_cap_binds_on_a_cheap_contract(self):
        s = size_position(EQUITY, 6142, 6132, "MES")
        self.assertEqual(s.contracts, 10)
        self.assertEqual(s.binding_constraint, "platform contract cap")

    def test_rejects_a_trade_that_cannot_fit_the_risk_budget(self):
        s = size_position(EQUITY, 6142, 5942, "ES")
        self.assertEqual(s.contracts, 0)
        self.assertFalse(s.ok)
        self.assertIn("Tighten the stop", s.rejected_reason)

    def test_total_risk_never_exceeds_the_budget(self):
        for stop in range(6050, 6142, 7):
            with self.subTest(stop=stop):
                s = size_position(EQUITY, 6142, float(stop), "ES")
                self.assertLessEqual(s.total_risk, 5_000 + 1e-9)

    def test_margin_never_exceeds_the_budget(self):
        for stop in range(6050, 6142, 7):
            with self.subTest(stop=stop):
                s = size_position(EQUITY, 6142, float(stop), "ES")
                self.assertLessEqual(s.margin_required, 40_000 + 1e-9)

    def test_short_side_sizes_identically(self):
        long_ = size_position(EQUITY, 6142, 6082, "ES")
        short = size_position(EQUITY, 6142, 6202, "ES")
        self.assertEqual(long_.contracts, short.contracts)
        self.assertEqual(long_.points_at_risk, short.points_at_risk)

    def test_zero_stop_distance_is_rejected(self):
        s = size_position(EQUITY, 6142, 6142, "ES")
        self.assertEqual(s.contracts, 0)
        self.assertIn("no defined risk", s.rejected_reason)

    def test_notional_is_reported(self):
        s = size_position(EQUITY, 6142, 6082, "ES")
        self.assertAlmostEqual(s.notional, 6142 * 50 * s.contracts, delta=1e-9)
        self.assertAlmostEqual(s.notional_pct_equity, s.notional / EQUITY * 100, delta=1e-9)

    def test_custom_limits_are_respected(self):
        s = size_position(EQUITY, 6142, 6132, "ES", limits=RiskLimits(risk_frac=0.01))
        self.assertLessEqual(s.total_risk, 1_000)

    def test_rejects_bad_equity(self):
        with self.assertRaises(ValueError):
            size_position(0, 6142, 6082, "ES")


class TestMicroFallback(unittest.TestCase):
    def test_falls_back_when_full_size_is_rejected(self):
        self.assertEqual(size_position(EQUITY, 6142, 5942, "ES").contracts, 0)
        micro = downsize_to_micro(EQUITY, 6142, 5942, "ES")
        self.assertEqual(micro.symbol, "MES")
        self.assertGreater(micro.contracts, 0)
        self.assertLessEqual(micro.total_risk, 5_000)

    def test_leaves_a_viable_full_size_trade_alone(self):
        self.assertEqual(downsize_to_micro(EQUITY, 6142, 6082, "ES").symbol, "ES")

    def test_no_micro_equivalent_returns_the_original(self):
        self.assertEqual(downsize_to_micro(EQUITY, 70.0, 50.0, "CL").symbol, "CL")


class TestContracts(unittest.TestCase):
    def test_tick_values_match_published_specs(self):
        expected = {"ES": 12.50, "MES": 1.25, "NQ": 5.00, "MNQ": 0.50,
                    "CL": 10.00, "GC": 10.00, "ZN": 15.625, "ZC": 12.50,
                    "6E": 6.25}
        for sym, tv in expected.items():
            with self.subTest(sym=sym):
                self.assertAlmostEqual(contracts.get(sym).tick_value, tv, delta=1e-9)

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(contracts.get("es").symbol, "ES")

    def test_unknown_symbol_lists_the_alternatives(self):
        with self.assertRaises(KeyError) as e:
            contracts.get("TSLA")
        self.assertIn("ES", str(e.exception))

    def test_pnl_scales_with_multiplier(self):
        self.assertAlmostEqual(contracts.get("ES").pnl(10, qty=2), 1_000, delta=1e-9)

    def test_micros_are_a_tenth_of_their_parent(self):
        for full, micro in (("ES", "MES"), ("NQ", "MNQ")):
            with self.subTest(full=full):
                self.assertAlmostEqual(contracts.get(micro).multiplier * 10,
                                       contracts.get(full).multiplier, delta=1e-9)


if __name__ == "__main__":
    unittest.main()
