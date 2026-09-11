"""Command line interface.

The scheduled trading windows call these instead of doing arithmetic in their
heads. Every command prints JSON so the output can go straight into the
dashboard database.

    python -m derivdesk.cli size   --equity 100000 --entry 6142 --stop 6082 --symbol ES
    python -m derivdesk.cli fwd    --spot 6120 --rate 0.0383 --years 0.1918 --div 0.0125 --market 6142
    python -m derivdesk.cli black76 --futures 6142 --strike 6200 --vol 0.17 --rate 0.0383 --years 0.0822
    python -m derivdesk.cli iv     --price 92.91 --futures 6142 --strike 6200 --rate 0.0383 --years 0.0822
    python -m derivdesk.cli mtm    --symbol ES --side long --qty 2 --entry 6100 --mark 6120 --prior 6110
    python -m derivdesk.cli specs
"""

import argparse
import json
import sys

from . import contracts, pricing
from .sizing import RiskLimits, size_position, downsize_to_micro
from .mtm import mark_to_market, stop_breached


def _out(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_size(a):
    limits = RiskLimits(risk_frac=a.risk_frac, margin_frac=a.margin_frac,
                        max_per_product=a.max_contracts)
    fn = downsize_to_micro if a.allow_micro else size_position
    s = fn(a.equity, a.entry, a.stop, a.symbol, limits) if a.allow_micro else \
        size_position(a.equity, a.entry, a.stop, a.symbol, limits, a.margin)
    _out(s.as_dict())


def cmd_fwd(a):
    f = pricing.forward_price(a.spot, a.rate, a.years, a.storage, a.div)
    result = {
        "theoretical_forward": round(f, 4),
        "net_carry": round(pricing.net_carry(a.rate, a.storage, a.div), 6),
        "years": a.years,
    }
    if a.market is not None:
        b = pricing.basis(a.market, f)
        result.update({
            "market": a.market,
            "basis": round(b, 4),
            "basis_pct": round(b / f * 100, 4),
            "market_is": "rich to carry" if b > 0 else "cheap to carry",
            "implied_carry": round(pricing.implied_carry(a.spot, a.market, a.years), 6),
        })
    _out(result)


def cmd_black76(a):
    call = pricing.greeks(a.futures, a.strike, a.vol, a.rate, a.years, "call")
    put = pricing.greeks(a.futures, a.strike, a.vol, a.rate, a.years, "put")
    mult = a.multiplier
    _out({
        "call": {k: round(v, 6) for k, v in call.items()},
        "put": {k: round(v, 6) for k, v in put.items()},
        "call_dollars": round(call["price"] * mult, 2),
        "put_dollars": round(put["price"] * mult, 2),
        "moneyness": round(pricing.moneyness(a.futures, a.strike), 6),
        "parity_gap": round(pricing.put_call_parity_gap(
            call["price"], put["price"], a.futures, a.strike, a.rate, a.years), 10),
    })


def cmd_iv(a):
    vol = pricing.implied_vol(a.price, a.futures, a.strike, a.rate, a.years, a.kind)
    _out({"implied_vol": round(vol, 6), "implied_vol_pct": round(vol * 100, 3),
          "kind": a.kind})


def cmd_mtm(a):
    m = mark_to_market(a.symbol, a.side, a.qty, a.entry, a.mark, a.prior,
                       a.contract_month or "")
    d = m.as_dict()
    if a.stop is not None:
        d["stop"] = a.stop
        d["stop_breached"] = stop_breached(a.side, a.mark, a.stop)
    _out(d)


def cmd_specs(a):
    _out({s: {"name": c.name, "multiplier": c.multiplier, "tick": c.tick,
              "tick_value": c.tick_value, "approx_margin": c.approx_margin,
              "asset_class": c.asset_class}
          for s, c in sorted(contracts.SPECS.items())})


def build_parser():
    p = argparse.ArgumentParser(prog="derivdesk", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("size", help="contracts permitted by the risk limits")
    s.add_argument("--equity", type=float, required=True)
    s.add_argument("--entry", type=float, required=True)
    s.add_argument("--stop", type=float, required=True)
    s.add_argument("--symbol", required=True)
    s.add_argument("--margin", type=float, default=None,
                   help="margin per contract; defaults to the spec estimate")
    s.add_argument("--risk-frac", type=float, default=0.05)
    s.add_argument("--margin-frac", type=float, default=0.40)
    s.add_argument("--max-contracts", type=int, default=10)
    s.add_argument("--allow-micro", action="store_true",
                   help="fall back to the micro contract if full size is rejected")
    s.set_defaults(func=cmd_size)

    f = sub.add_parser("fwd", help="cost-of-carry forward price and basis")
    f.add_argument("--spot", type=float, required=True)
    f.add_argument("--rate", type=float, required=True)
    f.add_argument("--years", type=float, required=True)
    f.add_argument("--div", type=float, default=0.0, help="dividend/convenience yield")
    f.add_argument("--storage", type=float, default=0.0)
    f.add_argument("--market", type=float, default=None)
    f.set_defaults(func=cmd_fwd)

    b = sub.add_parser("black76", help="option price and greeks")
    b.add_argument("--futures", type=float, required=True)
    b.add_argument("--strike", type=float, required=True)
    b.add_argument("--vol", type=float, required=True)
    b.add_argument("--rate", type=float, required=True)
    b.add_argument("--years", type=float, required=True)
    b.add_argument("--multiplier", type=float, default=50.0)
    b.set_defaults(func=cmd_black76)

    i = sub.add_parser("iv", help="implied volatility from a market price")
    i.add_argument("--price", type=float, required=True)
    i.add_argument("--futures", type=float, required=True)
    i.add_argument("--strike", type=float, required=True)
    i.add_argument("--rate", type=float, required=True)
    i.add_argument("--years", type=float, required=True)
    i.add_argument("--kind", choices=["call", "put"], default="call")
    i.set_defaults(func=cmd_iv)

    m = sub.add_parser("mtm", help="one session's mark to market")
    m.add_argument("--symbol", required=True)
    m.add_argument("--side", required=True)
    m.add_argument("--qty", type=int, required=True)
    m.add_argument("--entry", type=float, required=True)
    m.add_argument("--mark", type=float, required=True)
    m.add_argument("--prior", type=float, default=None,
                   help="prior session's settlement; defaults to entry")
    m.add_argument("--stop", type=float, default=None)
    m.add_argument("--contract-month", default="")
    m.set_defaults(func=cmd_mtm)

    sp = sub.add_parser("specs", help="dump the contract specifications")
    sp.set_defaults(func=cmd_specs)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (ValueError, KeyError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
