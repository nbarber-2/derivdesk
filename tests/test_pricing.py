import math
import unittest
from derivdesk import pricing as p


class TestNormal(unittest.TestCase):
    def test_cdf_symmetry(self):
        for x in (0.1, 0.5, 1.0, 2.5):
            with self.subTest(x=x):
                self.assertAlmostEqual(p.norm_cdf(x) + p.norm_cdf(-x), 1.0, delta=1e-12)

    def test_cdf_known_values(self):
        self.assertAlmostEqual(p.norm_cdf(0.0), 0.5, delta=1e-12)
        self.assertAlmostEqual(p.norm_cdf(1.96), 0.975, delta=1e-4)
        self.assertAlmostEqual(p.norm_cdf(-1.645), 0.05, delta=1e-4)

    def test_pdf_peak(self):
        self.assertAlmostEqual(p.norm_pdf(0.0), 1 / math.sqrt(2 * math.pi), delta=1e-12)


class TestForward(unittest.TestCase):
    def test_positive_carry_lifts_the_forward(self):
        f = p.forward_price(6120, r=0.0383, T=0.1918, yield_=0.0125)
        self.assertGreater(f, 6120)
        self.assertAlmostEqual(f, 6150.36, delta=0.01)

    def test_yield_above_rate_inverts_it(self):
        self.assertLess(p.forward_price(100, r=0.02, T=1.0, yield_=0.05), 100)

    def test_zero_time_is_spot(self):
        self.assertAlmostEqual(p.forward_price(4321, r=0.05, T=0.0), 4321, delta=1e-9)

    def test_storage_costs_push_the_forward_up(self):
        self.assertGreater(p.forward_price(80, r=0.04, T=0.5, storage=0.03),
                           p.forward_price(80, r=0.04, T=0.5))

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            p.forward_price(0, r=0.04, T=1.0)
        with self.assertRaises(ValueError):
            p.forward_price(100, r=0.04, T=-1.0)


class TestCarryInversion(unittest.TestCase):
    def test_implied_carry_round_trips(self):
        spot, r, T = 6120.0, 0.0383, 0.25
        f = p.forward_price(spot, r=r, T=T)
        self.assertAlmostEqual(p.implied_carry(spot, f, T), r, delta=1e-12)

    def test_basis_sign(self):
        self.assertLess(p.basis(6142, 6150.36), 0)
        self.assertGreater(p.basis(6160, 6150.36), 0)

    def test_curve_shape(self):
        self.assertEqual(p.curve_shape(70.0, 72.0), "contango")
        self.assertEqual(p.curve_shape(72.0, 70.0), "backwardation")
        self.assertEqual(p.curve_shape(70.0, 70.0), "flat")


class TestBlack76(unittest.TestCase):
    F, K, SIG, R, T = 6142.0, 6200.0, 0.17, 0.0383, 0.0822

    def test_put_call_parity_holds(self):
        c = p.black76(self.F, self.K, self.SIG, self.R, self.T, "call")
        put = p.black76(self.F, self.K, self.SIG, self.R, self.T, "put")
        gap = p.put_call_parity_gap(c, put, self.F, self.K, self.R, self.T)
        self.assertAlmostEqual(gap, 0.0, delta=1e-10)

    def test_atm_call_and_put_are_equal(self):
        c = p.black76(100, 100, 0.2, 0.03, 0.5, "call")
        put = p.black76(100, 100, 0.2, 0.03, 0.5, "put")
        self.assertAlmostEqual(c, put, delta=1e-10)

    def test_price_never_below_intrinsic(self):
        df = math.exp(-self.R * self.T)
        c = p.black76(6300, 6200, self.SIG, self.R, self.T, "call")
        self.assertGreaterEqual(c, df * 100 - 1e-9)

    def test_monotonic_in_volatility(self):
        prices = [p.black76(self.F, self.K, s, self.R, self.T, "call")
                  for s in (0.10, 0.15, 0.20, 0.30)]
        self.assertEqual(prices, sorted(prices))

    def test_monotonic_in_time(self):
        prices = [p.black76(self.F, self.K, self.SIG, self.R, t, "call")
                  for t in (0.05, 0.10, 0.25, 0.50)]
        self.assertEqual(prices, sorted(prices))

    def test_deep_otm_call_is_worthless(self):
        self.assertLess(p.black76(100, 400, 0.15, 0.03, 0.02, "call"), 1e-6)

    def test_rejects_bad_input(self):
        for bad in ({"F": 0}, {"K": 0}, {"sigma": 0}, {"T": 0}):
            kwargs = {"F": 100, "K": 100, "sigma": 0.2, "r": 0.03, "T": 0.5}
            kwargs.update(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.black76(**kwargs)
        with self.assertRaises(ValueError):
            p.black76(100, 100, 0.2, 0.03, 0.5, kind="straddle")


class TestGreeks(unittest.TestCase):
    ARGS = (6142, 6200, 0.17, 0.0383, 0.0822)

    def test_call_delta_bounds(self):
        d = p.greeks(*self.ARGS, "call")["delta"]
        self.assertTrue(0.0 < d < 1.0)

    def test_put_delta_is_negative(self):
        d = p.greeks(*self.ARGS, "put")["delta"]
        self.assertTrue(-1.0 < d < 0.0)

    def test_deltas_differ_by_the_discount_factor(self):
        c = p.greeks(*self.ARGS, "call")["delta"]
        put = p.greeks(*self.ARGS, "put")["delta"]
        self.assertAlmostEqual(c - put, math.exp(-0.0383 * 0.0822), delta=1e-12)

    def test_gamma_and_vega_are_positive(self):
        g = p.greeks(*self.ARGS, "call")
        self.assertGreater(g["gamma"], 0)
        self.assertGreater(g["vega"], 0)

    def test_theta_decays_a_long_option(self):
        self.assertLess(p.greeks(*self.ARGS, "call")["theta"], 0)

    def test_theta_difference_matches_parity(self):
        gc, gp = p.greeks(*self.ARGS, "call"), p.greeks(*self.ARGS, "put")
        expected = 0.0383 * (gc["price"] - gp["price"])
        self.assertAlmostEqual(gc["theta"] - gp["theta"], expected, delta=1e-10)

    def test_delta_approximates_finite_difference(self):
        F, K, s, r, T = self.ARGS
        h = 0.01
        fd = (p.black76(F + h, K, s, r, T, "call")
              - p.black76(F - h, K, s, r, T, "call")) / (2 * h)
        self.assertAlmostEqual(fd, p.greeks(*self.ARGS, "call")["delta"], delta=1e-6)

    def test_vega_approximates_finite_difference(self):
        F, K, s, r, T = self.ARGS
        h = 1e-5
        fd = (p.black76(F, K, s + h, r, T, "call")
              - p.black76(F, K, s - h, r, T, "call")) / (2 * h)
        vega = p.greeks(*self.ARGS, "call")["vega"]
        self.assertAlmostEqual(fd, vega, delta=abs(vega) * 1e-5)

    def test_gamma_approximates_finite_difference(self):
        F, K, s, r, T = self.ARGS
        h = 1.0
        fd = (p.black76(F + h, K, s, r, T, "call")
              - 2 * p.black76(F, K, s, r, T, "call")
              + p.black76(F - h, K, s, r, T, "call")) / (h * h)
        gamma = p.greeks(*self.ARGS, "call")["gamma"]
        self.assertAlmostEqual(fd, gamma, delta=abs(gamma) * 1e-3)


class TestImpliedVol(unittest.TestCase):
    def test_round_trip(self):
        F, r, T = 6142.0, 0.0383, 0.25
        for sigma in (0.08, 0.17, 0.35, 0.80):
            for K in (5800, 6142, 6500):
                for kind in ("call", "put"):
                    with self.subTest(sigma=sigma, K=K, kind=kind):
                        price = p.black76(F, K, sigma, r, T, kind)
                        got = p.implied_vol(price, F, K, r, T, kind)
                        self.assertAlmostEqual(got, sigma, delta=1e-5)

    def test_rejects_price_below_intrinsic(self):
        with self.assertRaises(ValueError):
            p.implied_vol(1.0, 6300, 6000, 0.0383, 0.25, "call")

    def test_rejects_nonpositive_price(self):
        with self.assertRaises(ValueError):
            p.implied_vol(0.0, 6142, 6200, 0.0383, 0.25, "call")


class TestMoneyness(unittest.TestCase):
    def test_sign(self):
        self.assertGreater(p.moneyness(6300, 6200), 0)
        self.assertLess(p.moneyness(6100, 6200), 0)
        self.assertAlmostEqual(p.moneyness(6200, 6200), 0.0, delta=1e-12)


if __name__ == "__main__":
    unittest.main()
