"""No-arbitrage futures pricing and Black-76 options on futures.

Standard library only. Every function takes rates and volatilities as decimals
(0.0383 for 3.83%) and times in years.
"""

import math

SQRT_2PI = math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    """Standard normal CDF, via the exact error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / SQRT_2PI


# --------------------------------------------------------------------------
# Futures: cost of carry
# --------------------------------------------------------------------------

def forward_price(spot: float, r: float, T: float, storage: float = 0.0,
                  yield_: float = 0.0) -> float:
    """No-arbitrage forward price under continuous compounding.

        F = S * exp((r + u - y) * T)

    r       risk-free rate
    storage u, carrying cost as a rate (commodities)
    yield_  y, dividend yield or convenience yield
    """
    if spot <= 0:
        raise ValueError("spot must be positive")
    if T < 0:
        raise ValueError("T must be non-negative")
    return spot * math.exp((r + storage - yield_) * T)


def net_carry(r: float, storage: float = 0.0, yield_: float = 0.0) -> float:
    """The annualised net cost of carry, r + u - y."""
    return r + storage - yield_


def basis(market: float, theoretical: float) -> float:
    """Market price minus theoretical. Positive means the future is rich."""
    return market - theoretical


def implied_carry(spot: float, futures: float, T: float) -> float:
    """The net carry rate the market is actually pricing.

    Inverts the cost-of-carry relation: c = ln(F/S) / T. Compare against your
    own r + u - y to see what the market disagrees with you about.
    """
    if spot <= 0 or futures <= 0:
        raise ValueError("prices must be positive")
    if T <= 0:
        raise ValueError("T must be positive")
    return math.log(futures / spot) / T


def curve_shape(near: float, far: float) -> str:
    """'contango' when the deferred contract trades above the near one."""
    if math.isclose(near, far):
        return "flat"
    return "contango" if far > near else "backwardation"


# --------------------------------------------------------------------------
# Options on futures: Black-76
# --------------------------------------------------------------------------

def _d1_d2(F: float, K: float, sigma: float, T: float):
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / v
    return d1, d1 - v


def _validate(F, K, sigma, T):
    if F <= 0 or K <= 0:
        raise ValueError("F and K must be positive")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if T <= 0:
        raise ValueError("T must be positive")


def black76(F: float, K: float, sigma: float, r: float, T: float,
            kind: str = "call") -> float:
    """Black-76 price of a European option on a futures contract.

        c = exp(-rT) * [F*N(d1) - K*N(d2)]
        p = exp(-rT) * [K*N(-d2) - F*N(-d1)]

    Returns the price in the futures' quoted units. Multiply by the contract
    multiplier for dollars.
    """
    _validate(F, K, sigma, T)
    d1, d2 = _d1_d2(F, K, sigma, T)
    df = math.exp(-r * T)
    if kind == "call":
        return df * (F * norm_cdf(d1) - K * norm_cdf(d2))
    if kind == "put":
        return df * (K * norm_cdf(-d2) - F * norm_cdf(-d1))
    raise ValueError("kind must be 'call' or 'put'")


def greeks(F: float, K: float, sigma: float, r: float, T: float,
           kind: str = "call") -> dict:
    """Delta, gamma, vega and theta under Black-76.

    vega is per 1.00 of volatility (divide by 100 for one vol point).
    theta is per year (divide by 365 for one calendar day).
    """
    _validate(F, K, sigma, T)
    d1, d2 = _d1_d2(F, K, sigma, T)
    df = math.exp(-r * T)
    rt = math.sqrt(T)
    price = black76(F, K, sigma, r, T, kind)

    if kind == "call":
        delta = df * norm_cdf(d1)
    else:
        delta = -df * norm_cdf(-d1)

    gamma = df * norm_pdf(d1) / (F * sigma * rt)
    vega = F * df * norm_pdf(d1) * rt
    theta = -F * df * norm_pdf(d1) * sigma / (2.0 * rt) + r * price

    return {"price": price, "delta": delta, "gamma": gamma,
            "vega": vega, "theta": theta, "d1": d1, "d2": d2}


def put_call_parity_gap(call: float, put: float, F: float, K: float,
                        r: float, T: float) -> float:
    """(c - p) - exp(-rT)*(F - K). Zero when parity holds.

    A non-zero gap on real market prices is either an arbitrage or, far more
    often, stale quotes on one leg. Check the quotes before believing it.
    """
    return (call - put) - math.exp(-r * T) * (F - K)


def implied_vol(price: float, F: float, K: float, r: float, T: float,
                kind: str = "call", tol: float = 1e-8,
                max_iter: int = 200) -> float:
    """Volatility that reproduces `price` under Black-76, by bisection.

    Bisection rather than Newton: slower, but it cannot diverge on the wings
    where vega collapses, which is exactly where a trading model asks.
    """
    if price <= 0:
        raise ValueError("price must be positive")
    df = math.exp(-r * T)
    intrinsic = df * (max(F - K, 0.0) if kind == "call" else max(K - F, 0.0))
    if price < intrinsic - tol:
        raise ValueError(f"price {price} is below intrinsic {intrinsic}")

    lo, hi = 1e-9, 5.0
    if black76(F, K, hi, r, T, kind) < price:
        raise ValueError("price exceeds the model's range at 500% vol")

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if black76(F, K, mid, r, T, kind) < price:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def moneyness(F: float, K: float) -> float:
    """F/K - 1. Positive means a call is in the money."""
    return F / K - 1.0
