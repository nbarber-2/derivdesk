# derivdesk — project memory

Context for any session working in this repo. Read this first.

## What this is

Nick Barber's FINA 30233 Financial Derivatives semester project (TCU, fall 2026,
instructor McFarland). Due 29 Nov 2026: a written essay plus a five-minute
presentation on 11/30, 12/2 or 12/4.

The assignment is a controlled experiment with three books:

| Book | Who runs it | Where |
|---|---|---|
| AI derivatives account | Claude, autonomously | CME Institute Simulator, `Invest2_Fall26_1` |
| Non-AI account | **Nick alone, unaided** | CME Institute, `Invest2_Fall26_2` |
| Stock portfolio | Claude, autonomously | TCU Agentic Advisor (different class) |

**The non-AI account is off limits.** Never develop strategy, signals or entries
for it, and never read its positions. It is the human baseline the whole
comparison rests on, and contaminating it invalidates 25% of the grade
(strategy discussion + conclusions) as well as the paper's central claim.
Checking Nick's arithmetic on its valuations is fine; deciding its trades is not.

## Trading window

Practice mode from now; the graded challenge runs 12 Oct 5:00 PM CT to
12 Nov 5:00 PM CT. $100,000 account, max 10 contracts per product.

Graded requirements, per book: at least one futures trade, at least one options
trade, at least one futures contract marked to market from one session to the
next, and fair valuations of one futures and one options position.

## How the desk runs

Three scheduled tasks, weekdays Central: 8:45 AM (research, falsification
check, size, execute), 2:30 PM (mark to market, fair value, overnight
decision), 5:45 PM (Agentic Advisor portfolio).

State lives in an Artifact database, not in this repo:
`https://claude.ai/code/artifact/52f165fa-4736-4528-8032-8d6399dcb813`

- `config/deskrules` — hard rules, risk limits, log schema. Authoritative.
- `config/simulator` — platform mechanics, contract-roll hazard
- `log/<date>-<window>` — every decision with its reasoning
- `positions/<id>`, `account/state`, `context/market-read`, `portfolio/<date>`

## The two design decisions worth preserving

**Falsification first.** Before researching any view, the desk writes down what
would prove it wrong and looks for *that* before anything supportive. Default
sizing is normal; leverage must be earned by surviving a hostile check. If the
log shows the view confirmed most days, the check has stopped working and that
is itself a finding worth reporting.

**`viewSource` on every entry** — `nick` when he supplied the morning view,
`desk` when the model formed its own. This splits the record into two
sub-experiments for free: how his calls did versus how the model's did.

## Risk limits

$5,000 max risked at the stop per trade, $40,000 max margin, $10,000 daily loss
halts new positions, a stop on every position. `sizing.size_position` returns
`contracts == 0` when nothing clears the limits — that is an answer, not an
error.

## Conventions

Standard library only, Python 3.9+. The scheduled sessions run in ephemeral
containers where PyPI is sometimes unreachable, so a dependency is a failure
waiting for a bad morning. Tests are `unittest`, run with
`python -m unittest discover -s tests -t .` — keep them dependency-free too.

Contract specs and margins live in `contracts.SPECS`. Margins are indicative
and move with volatility; prefer whatever the simulator reports.

## Known hazards

**Contract rolls fire on volume, not on a date**, and an open position does not
roll with the market: P&L keeps pricing the held contract while the quote board
shows the new front month. Check every window. An unnoticed roll silently
corrupts the graded mark-to-market trail. `mtm.rolled` exists for this.

**Scheduled tasks bound to Nick's Mac disable themselves** with
`device_absent` when it is asleep at fire time. This already cost three days in
September. Execution needs the laptop open; research does not.

## What still needs doing

- Push this repo (it was built in a cloud session with no credentials)
- Confirm whether the four CME eligibility courses gate participation
- November: run `analysis/metrics.py` over the exported log and write the paper
