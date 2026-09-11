"""Position sizing under hard risk limits.

The limits exist because the desk trades unattended. A correct view sized too
big is still a blown account, and a blown account in week one leaves nothing
to write about in week five.
"""

from dataclasses import dataclass, asdict
from .contracts import Contract, get


@dataclass
class RiskLimits:
    risk_frac: float = 0.05      # max fraction of equity lost at the stop, per trade
    margin_frac: float = 0.40    # max fraction of equity posted as margin
    daily_halt_frac: float = 0.10  # daily loss that stops new positions
    max_per_product: int = 10    # platform cap

    def risk_budget(self, equity: float) -> float:
        return equity * self.risk_frac

    def margin_budget(self, equity: float) -> float:
        return equity * self.margin_frac

    def halt_level(self, equity: float) -> float:
        return equity * self.daily_halt_frac


@dataclass
class Sizing:
    symbol: str
    contracts: int
    entry: float
    stop: float
    points_at_risk: float
    risk_per_contract: float
    total_risk: float
    margin_required: float
    notional: float
    notional_pct_equity: float
    binding_constraint: str
    rejected_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.contracts > 0

    def as_dict(self) -> dict:
        return asdict(self)


def size_position(equity: float, entry: float, stop: float, symbol: str,
                  limits: RiskLimits = None, margin_per_contract: float = None
                  ) -> Sizing:
    """How many contracts the limits actually permit.

    Sizes off the distance to the stop, not off conviction. Returns a Sizing
    with contracts == 0 when no size clears the limits -- that is a valid
    answer, not an error: it means this trade cannot be expressed within the
    risk budget and should be skipped or re-planned with a tighter stop.
    """
    limits = limits or RiskLimits()
    spec: Contract = get(symbol)
    margin = margin_per_contract if margin_per_contract is not None else spec.approx_margin

    if equity <= 0:
        raise ValueError("equity must be positive")
    if entry <= 0:
        raise ValueError("entry must be positive")

    points = abs(entry - stop)
    if points == 0:
        return Sizing(spec.symbol, 0, entry, stop, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                      "none", "stop equals entry: no defined risk")

    risk_per = points * spec.multiplier
    by_risk = int(limits.risk_budget(equity) // risk_per)
    by_margin = int(limits.margin_budget(equity) // margin) if margin > 0 else limits.max_per_product
    cap = limits.max_per_product

    n = min(by_risk, by_margin, cap)
    binding = min(
        (by_risk, "per-trade risk"),
        (by_margin, "margin budget"),
        (cap, "platform contract cap"),
        key=lambda pair: pair[0],
    )[1]

    reason = ""
    if n <= 0:
        n = 0
        if by_risk <= 0:
            reason = (f"one contract risks ${risk_per:,.0f} at a {points:g}-point stop, "
                      f"over the ${limits.risk_budget(equity):,.0f} budget. "
                      f"Tighten the stop or use a smaller contract.")
        else:
            reason = (f"margin of ${margin:,.0f} per contract exceeds the "
                      f"${limits.margin_budget(equity):,.0f} budget.")

    notional = entry * spec.multiplier * n
    return Sizing(
        symbol=spec.symbol,
        contracts=n,
        entry=entry,
        stop=stop,
        points_at_risk=points,
        risk_per_contract=risk_per,
        total_risk=risk_per * n,
        margin_required=margin * n,
        notional=notional,
        notional_pct_equity=(notional / equity * 100.0) if equity else 0.0,
        binding_constraint=binding,
        rejected_reason=reason,
    )


def downsize_to_micro(equity: float, entry: float, stop: float, symbol: str,
                      limits: RiskLimits = None) -> Sizing:
    """Retry a rejected full-size trade in its micro equivalent.

    Returns the micro sizing when the full-size contract cannot clear the
    risk budget, otherwise the original.
    """
    micro = {"ES": "MES", "NQ": "MNQ"}
    full = size_position(equity, entry, stop, symbol, limits)
    if full.ok or symbol.upper() not in micro:
        return full
    return size_position(equity, entry, stop, micro[symbol.upper()], limits)
