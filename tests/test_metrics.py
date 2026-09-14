import unittest
from analysis import metrics as m

LOG = [
    {"seq": 1, "viewSource": "nick", "verdict": "Confirmed",
     "sizing": "Size normal", "mathSource": "derivdesk"},
    {"seq": 2, "viewSource": "nick", "verdict": "Contradicted",
     "sizing": "Stand down", "mathSource": "derivdesk"},
    {"seq": 3, "viewSource": "desk", "verdict": "Already priced",
     "sizing": "Limit exposure", "mathSource": "manual"},
    {"seq": 4, "viewSource": "desk", "verdict": "Confirmed",
     "sizing": "Leverage up", "mathSource": "derivdesk"},
    {"seq": 5, "viewSource": "nick", "findings": "no view today"},
]

SNAPS = [
    {"date": "2026-10-12", "equity": 100_000},
    {"date": "2026-10-13", "equity": 102_000},
    {"date": "2026-10-14", "equity": 96_900},
    {"date": "2026-10-15", "equity": 101_000},
]


class TestProcess(unittest.TestCase):
    def test_only_entries_with_verdicts_count_as_decisions(self):
        self.assertEqual(len(m.decisions(LOG)), 4)

    def test_verdict_mix_sums_to_one(self):
        self.assertAlmostEqual(sum(m.verdict_mix(LOG).values()), 1.0, delta=1e-12)

    def test_confirmation_rate(self):
        self.assertAlmostEqual(m.confirmation_rate(LOG), 0.5, delta=1e-12)

    def test_stand_down_rate(self):
        self.assertAlmostEqual(m.stand_down_rate(LOG), 0.25, delta=1e-12)

    def test_view_source_split(self):
        s = m.split_by_view_source(LOG)
        self.assertEqual(len(s["nick"]), 3)
        self.assertEqual(len(s["desk"]), 2)

    def test_math_source_mix(self):
        mix = m.math_source_mix(LOG)
        self.assertAlmostEqual(mix["derivdesk"], 0.75, delta=1e-12)
        self.assertAlmostEqual(mix["manual"], 0.25, delta=1e-12)

    def test_empty_log_is_not_a_crash(self):
        self.assertEqual(m.verdict_mix([]), {})
        self.assertIsNone(m.confirmation_rate([]))
        self.assertIsNone(m.stand_down_rate([]))


class TestPerformance(unittest.TestCase):
    def test_curve_is_sorted_by_date(self):
        c = m.equity_curve(list(reversed(SNAPS)))
        self.assertEqual([d for d, _ in c], sorted(d for d, _ in c))

    def test_total_return(self):
        self.assertAlmostEqual(m.total_return(m.equity_curve(SNAPS)), 0.01, delta=1e-12)

    def test_max_drawdown(self):
        # peak 102,000 -> trough 96,900 is exactly 5%
        self.assertAlmostEqual(m.max_drawdown(m.equity_curve(SNAPS)), 0.05, delta=1e-12)

    def test_monotonic_curve_has_no_drawdown(self):
        up = [{"date": f"2026-10-{d:02d}", "equity": 100 + d} for d in range(1, 6)]
        self.assertAlmostEqual(m.max_drawdown(m.equity_curve(up)), 0.0, delta=1e-12)

    def test_daily_returns_count(self):
        self.assertEqual(len(m.daily_returns(m.equity_curve(SNAPS))), 3)

    def test_sharpe_needs_dispersion(self):
        self.assertIsNone(m.sharpe([0.01, 0.01, 0.01]))
        self.assertIsNone(m.sharpe([0.01]))
        self.assertIsNotNone(m.sharpe([0.01, -0.02, 0.03]))

    def test_sharpe_sign_follows_mean_return(self):
        self.assertGreater(m.sharpe([0.02, 0.01, 0.03, -0.005]), 0)
        self.assertLess(m.sharpe([-0.02, -0.01, -0.03, 0.005]), 0)

    def test_return_over_drawdown(self):
        c = m.equity_curve(SNAPS)
        self.assertAlmostEqual(m.return_over_drawdown(c), 0.01 / 0.05, delta=1e-12)

    def test_flat_curve_has_no_ratio(self):
        flat = [{"date": "2026-10-01", "equity": 100},
                {"date": "2026-10-02", "equity": 100}]
        self.assertIsNone(m.return_over_drawdown(m.equity_curve(flat)))

    def test_empty_inputs(self):
        self.assertIsNone(m.total_return([]))
        self.assertIsNone(m.max_drawdown([]))


class TestReport(unittest.TestCase):
    def test_report_builds(self):
        r = m.build_report(LOG, SNAPS)
        self.assertEqual(r.decisions, 4)
        self.assertAlmostEqual(r.total_return, 0.01, delta=1e-12)
        self.assertAlmostEqual(r.confirmation_rate, 0.5, delta=1e-12)

    def test_comparison_splits_both_ways(self):
        c = m.compare_view_sources(LOG, SNAPS)
        self.assertEqual(set(c), {"nick", "desk"})
        self.assertEqual(c["nick"]["decisions"], 2)
        self.assertEqual(c["desk"]["decisions"], 2)

    def test_report_serialises(self):
        self.assertIn("sharpe", m.build_report(LOG, SNAPS).as_dict())


if __name__ == "__main__":
    unittest.main()
