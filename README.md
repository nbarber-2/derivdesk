# derivdesk

Pricing, position sizing and mark-to-market for a futures and options trading
desk. Written for the FINA 30233 Financial Derivatives semester project at TCU
(fall 2026), where an AI-run account trades a CME Institute simulator against a
separately developed human baseline.

**No dependencies.** Standard library only, Python 3.9+. That is deliberate:
the scheduled trading sessions that call this run in ephemeral containers, and
anything requiring a package install is a failure mode waiting for a bad
morning.

## Why this exists

The trading windows used to compute Black-76 and position sizes inline, in
prose. That works until it quietly doesn't — a transposed sign in a theta, a
stop distance measured from the wrong price, a margin check done from memory.
Arithmetic that decides what gets traded belongs in tested code.

## Install

```bash
git clone https://github.com/<user>/derivdesk.git
cd derivdesk
python -m unittest discover -s tests -t .
```

## Command line

Every command prints JSON, so output drops straight into the desk's database.

```bash
# How many contracts do the risk limits actually permit?
python -m derivdesk.cli size --equity 100000 --entry 6142 --stop 6082 --symbol ES

# Cost-of-carry fair value, and how far the market is from it
python -m derivdesk.cli fwd --spot 6120 --rate 0.0383 --years 0.1918 \
                            --div 0.0125 --market 6142

# Black-76 price and greeks, both sides, with a parity check
python -m derivdesk.cli black76 --futures 6142 --strike 6200 --vol 0.17 \
                                --rate 0.0383 --years 0.0822

# What volatility is the market actually pricing?
python -m derivdesk.cli iv --price 92.91 --futures 6142 --strike 6200 \
                           --rate 0.0383 --years 0.0822

# One session's mark, against the prior session's settlement
python -m derivdesk.cli mtm --symbol ES --side long --qty 2 \
                            --entry 6100 --mark 6120 --prior 6110 --stop 6082

python -m derivdesk.cli specs
```

## Library

```python
from derivdesk import forward_price, black76, greeks, size_position, mark_to_market

forward_price(6120, r=0.0383, T=0.1918, yield_=0.0125)   # 6150.36
black76(6142, 6200, sigma=0.17, r=0.0383, T=0.0822)      # 92.91

s = size_position(equity=100_000, entry=6142, stop=6082, symbol="ES")
s.contracts            # 1
s.binding_constraint   # 'per-trade risk'

m = mark_to_market("ES", "long", 2, entry=6100, mark=6120, prior_mark=6110)
m.daily_pnl            # 1000.0
```

## What's in it

| Module | Contents |
|---|---|
| `contracts` | CME specs — multiplier, tick, tick value, indicative margin, asset class |
| `pricing` | Cost-of-carry forwards, basis, implied carry, curve shape; Black-76 price, greeks, implied vol, put-call parity |
| `sizing` | Position sizing under per-trade risk, margin and platform-cap limits, with micro-contract fallback |
| `mtm` | Daily marks against the prior session, stop breaches, contract-roll detection |

## Risk limits

Defaults assume a $100,000 account:

| Limit | Default | On $100k |
|---|---|---|
| Risk at the stop, per trade | 5% of equity | $5,000 |
| Margin posted | 40% of equity | $40,000 |
| Daily loss that halts new positions | 10% of equity | $10,000 |
| Contracts per product | 10 | platform cap |

`size_position` returns `contracts == 0` when nothing clears the limits. That
is an answer, not an error: the trade cannot be expressed within the risk
budget and should be skipped or replanned with a tighter stop.

## Notes on the model

Forward pricing is continuous-compounding cost of carry,
`F = S·e^((r+u−y)T)`. Options are Black-76 on the futures price rather than
Black-Scholes on spot, which is the right model for options on futures and
avoids double-counting carry.

Implied volatility uses bisection rather than Newton-Raphson. Slower, but it
cannot diverge on the wings where vega collapses — which is exactly where a
trading model tends to ask.

Margin figures in `contracts.SPECS` are indicative and move with volatility.
Prefer the margin the simulator reports over the default.

Contract rolls on the CME Institute simulator are triggered by volume, not by
date, and an open position does not roll with the market: P&L keeps pricing
the contract held while the quote board shows the new front month. `mtm.rolled`
exists to catch that, and it gets checked every window rather than on a
calendar.

## Tests

67 tests, no dependencies:

```bash
python -m unittest discover -s tests -t . -v
```

Coverage includes put-call parity, greeks verified against finite differences,
implied-vol round trips across strikes and volatilities, every binding
constraint in the sizing logic, and daily marks reconciling to open P&L on both
sides of the market.
