"""Mark to market.

The rubric grades a dated trail of daily marks on at least one futures
contract, so this records each session's mark against the prior session's --
never a running total, which loses the day-by-day evidence.
"""

from dataclasses import dataclass, asdict
from .contracts import get


def direction(side: str) -> int:
    s = side.strip().lower()
    if s in ("long", "buy", "b", "l"):
        return 1
    if s in ("short", "sell", "s"):
        return -1
    raise ValueError(f"unrecognised side {side!r}")


@dataclass
class Mark:
    symbol: str
    side: str
    qty: int
    entry: float
    prior_mark: float
    mark: float
    multiplier: float
    daily_pnl: float
    open_pnl: float
    contract_month: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def mark_to_market(symbol: str, side: str, qty: int, entry: float,
                   mark: float, prior_mark: float = None,
                   contract_month: str = "") -> Mark:
    """One session's mark.

    prior_mark defaults to entry, which is correct on the position's first day
    and wrong on every day after -- pass the previous session's settlement.
    """
    spec = get(symbol)
    d = direction(side)
    prior = entry if prior_mark is None else prior_mark
    return Mark(
        symbol=spec.symbol,
        side=side.lower(),
        qty=qty,
        entry=entry,
        prior_mark=prior,
        mark=mark,
        multiplier=spec.multiplier,
        daily_pnl=(mark - prior) * d * qty * spec.multiplier,
        open_pnl=(mark - entry) * d * qty * spec.multiplier,
        contract_month=contract_month,
    )


def stop_breached(side: str, mark: float, stop: float) -> bool:
    """True when price has traded through the stop."""
    return mark <= stop if direction(side) == 1 else mark >= stop


def rolled(position_month: str, front_month: str) -> bool:
    """True when the held contract is no longer the front month.

    Rolls on the CME Institute simulator fire on volume, not on a date, so
    this gets checked every window rather than on a calendar.
    """
    if not position_month or not front_month:
        return False
    return position_month.strip().upper() != front_month.strip().upper()
