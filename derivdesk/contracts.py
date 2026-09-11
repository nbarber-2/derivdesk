"""CME contract specifications.

Multipliers and tick values are the exchange's published specs. Margin figures
are approximate and move with volatility -- always prefer the margin the
simulator reports over the default here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    symbol: str
    name: str
    multiplier: float      # dollars of P&L per 1.00 move in the quoted price
    tick: float            # minimum price increment
    approx_margin: float   # indicative initial margin per contract, USD
    asset_class: str

    @property
    def tick_value(self) -> float:
        """Dollars gained or lost per one-tick move, per contract."""
        return self.tick * self.multiplier

    def pnl(self, price_move: float, qty: float = 1.0) -> float:
        """Dollar P&L for a given price move, ignoring direction."""
        return price_move * self.multiplier * qty


SPECS = {
    "ES":  Contract("ES",  "E-mini S&P 500",     50.0,  0.25,   17600.0, "equity"),
    "MES": Contract("MES", "Micro E-mini S&P",    5.0,  0.25,    1760.0, "equity"),
    "NQ":  Contract("NQ",  "E-mini Nasdaq-100",  20.0,  0.25,   28000.0, "equity"),
    "MNQ": Contract("MNQ", "Micro E-mini Nasdaq", 2.0,  0.25,    2800.0, "equity"),
    "YM":  Contract("YM",  "E-mini Dow",          5.0,  1.00,   10500.0, "equity"),
    "RTY": Contract("RTY", "E-mini Russell 2000", 50.0, 0.10,    9500.0, "equity"),
    "CL":  Contract("CL",  "WTI Crude Oil",     1000.0, 0.01,    6800.0, "energy"),
    "NG":  Contract("NG",  "Natural Gas",      10000.0, 0.001,   4200.0, "energy"),
    "GC":  Contract("GC",  "Gold",               100.0, 0.10,   12000.0, "metals"),
    "SI":  Contract("SI",  "Silver",            5000.0, 0.005,  16000.0, "metals"),
    "ZN":  Contract("ZN",  "10-Year T-Note",    1000.0, 0.015625, 2200.0, "rates"),
    "ZB":  Contract("ZB",  "30-Year T-Bond",    1000.0, 0.03125,  4600.0, "rates"),
    "ZC":  Contract("ZC",  "Corn",                50.0, 0.25,    1900.0, "ags"),
    "ZS":  Contract("ZS",  "Soybeans",            50.0, 0.25,    3400.0, "ags"),
    "6E":  Contract("6E",  "Euro FX",         125000.0, 0.00005, 3100.0, "fx"),
    "6J":  Contract("6J",  "Japanese Yen",  12500000.0, 0.0000005, 3300.0, "fx"),
}


def get(symbol: str) -> Contract:
    """Look up a contract spec. Raises KeyError with the valid list on a miss."""
    key = symbol.upper()
    if key not in SPECS:
        raise KeyError(f"unknown contract {symbol!r}; known: {sorted(SPECS)}")
    return SPECS[key]
