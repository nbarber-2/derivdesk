"""Performance and process metrics over the desk's decision log.

This is the engine for the November writeup. It answers the questions the
rubric actually grades — how the AI strategy performed, how the personal one
performed, and what the comparison shows — plus one the rubric does not ask
but the paper is stronger for: whether the falsification check was doing any
work, or quietly rubber-stamping every view.

Standard library only, like the rest of the package.
"""

import json
import math
from collections import Counter
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_log(path):
    """Load log entries from a JSON file (a list, or {id: {...}} export)."""
    with open(path) as fh:
        raw = json.load(fh)
    entries = list(raw.values()) if isinstance(raw, dict) else list(raw)
    return sorted(entries, key=lambda e: e.get("seq", 0))


def decisions(entries):
    """Entries that actually reached a verdict — the decision points."""
    return [e for e in entries if e.get("verdict")]


# ---------------------------------------------------------------------------
# process metrics — was the method sound?
# ---------------------------------------------------------------------------

def verdict_mix(entries):
    """How often each verdict was reached, as fractions."""
    d = decisions(entries)
    if not d:
        return {}
    counts = Counter(e["verdict"] for e in d)
    return {k: v / len(d) for k, v in sorted(counts.items())}


def sizing_mix(entries):
    d = [e for e in entries if e.get("sizing")]
    if not d:
        return {}
    counts = Counter(e["sizing"] for e in d)
    return {k: v / len(d) for k, v in sorted(counts.items())}


def confirmation_rate(entries):
    """Fraction of decisions that came back 'Confirmed'.

    The falsification check exists to make confirmation costly. If nearly
    every view is confirmed, the check is not binding and the model is
    agreeing with whoever spoke last. Report this honestly in the paper;
    a high number is a finding, not something to hide.
    """
    d = decisions(entries)
    if not d:
        return None
    return sum(1 for e in d if e["verdict"] == "Confirmed") / len(d)


def stand_down_rate(entries):
    """Fraction of decisions that resulted in no trade.

    A desk that never stands down is not exercising judgement.
    """
    d = [e for e in entries if e.get("sizing")]
    if not d:
        return None
    return sum(1 for e in d if e["sizing"] == "Stand down") / len(d)


def split_by_view_source(entries):
    """Separate the days Nick supplied the view from the days the desk did."""
    nick = [e for e in entries if e.get("viewSource") == "nick"]
    desk = [e for e in entries if e.get("viewSource") == "desk"]
    return {"nick": nick, "desk": desk}


def math_source_mix(entries):
    """How often the tested package produced the numbers vs. manual work."""
    d = [e for e in entries if e.get("mathSource")]
    if not d:
        return {}
    counts = Counter(e["mathSource"] for e in d)
    return {k: v / len(d) for k, v in sorted(counts.items())}


# ---------------------------------------------------------------------------
# performance metrics — how did the book do?
# ---------------------------------------------------------------------------

def equity_curve(snapshots):
    """[(date, equity)] sorted by date, from account snapshots."""
    pts = [(s["date"], float(s["equity"])) for s in snapshots if "equity" in s]
    return sorted(pts, key=lambda p: p[0])


def daily_returns(curve):
    """Simple period-over-period returns from an equity curve."""
    out = []
    for (_, prev), (_, cur) in zip(curve, curve[1:]):
        if prev:
            out.append(cur / prev - 1.0)
    return out


def total_return(curve):
    if len(curve) < 2 or not curve[0][1]:
        return None
    return curve[-1][1] / curve[0][1] - 1.0


def max_drawdown(curve):
    """Largest peak-to-trough decline, as a positive fraction."""
    if not curve:
        return None
    peak, worst = curve[0][1], 0.0
    for _, v in curve:
        peak = max(peak, v)
        if peak:
            worst = max(worst, (peak - v) / peak)
    return worst


def sharpe(returns, periods_per_year=252, rf_annual=0.0):
    """Annualised Sharpe ratio. None when there is no dispersion to divide by."""
    n = len(returns)
    if n < 2:
        return None
    rf = rf_annual / periods_per_year
    excess = [r - rf for r in returns]
    mean = sum(excess) / n
    var = sum((r - mean) ** 2 for r in excess) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return (mean / sd) * math.sqrt(periods_per_year)


def return_over_drawdown(curve):
    """Total return divided by max drawdown — return per unit of pain.

    The honest headline for comparing an aggressive book against a
    conservative one. Raw return alone flatters whichever took more risk.
    """
    tr, dd = total_return(curve), max_drawdown(curve)
    if tr is None or not dd:
        return None
    return tr / dd


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@dataclass
class Report:
    label: str
    decisions: int
    total_return: float = None
    max_drawdown: float = None
    sharpe: float = None
    return_over_drawdown: float = None
    confirmation_rate: float = None
    stand_down_rate: float = None
    verdict_mix: dict = None
    sizing_mix: dict = None
    math_source_mix: dict = None

    def as_dict(self):
        return asdict(self)


def build_report(entries, snapshots=None, label="AI account"):
    curve = equity_curve(snapshots or [])
    return Report(
        label=label,
        decisions=len(decisions(entries)),
        total_return=total_return(curve),
        max_drawdown=max_drawdown(curve),
        sharpe=sharpe(daily_returns(curve)),
        return_over_drawdown=return_over_drawdown(curve),
        confirmation_rate=confirmation_rate(entries),
        stand_down_rate=stand_down_rate(entries),
        verdict_mix=verdict_mix(entries),
        sizing_mix=sizing_mix(entries),
        math_source_mix=math_source_mix(entries),
    )


def compare_view_sources(entries, snapshots=None):
    """Two reports: days Nick drove the view, days the desk did."""
    split = split_by_view_source(entries)
    return {k: build_report(v, snapshots, label=f"view by {k}").as_dict()
            for k, v in split.items()}
