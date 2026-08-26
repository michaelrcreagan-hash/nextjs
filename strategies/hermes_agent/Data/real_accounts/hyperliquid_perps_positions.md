# Hyperliquid perps / crypto-margin positions

> Raw, as dictated by the user 2026-08-26. Not yet normalized — several
> fields are ambiguous (see notes). Do not treat as clean structured data
> until clarified; see DISCOVERY.md open question #5.

## Perps

| Symbol (as given) | Direction | Size | Unrealized P&L | Notes |
|---|---|---|---|---|
| "Spcx" | SHORT | 1.5 | $19 | Ticker unclear — possibly a transcription error. Not a standard equity/crypto symbol found elsewhere in this repo's universes. |
| "Mu" | LONG | 1 (entry ref "17"?) | $254 | Likely MU (Micron) — but MU doesn't trade as a Hyperliquid perp under normal circumstances; could also be a different asset. Needs clarification. |
| ETH | LONG | 0.2 | $111 | |

## Coin-margined shorts (BTC/ETH, margin account)

| Asset | Direction | Notional | Entry | Unrealized P&L (in coin terms) |
|---|---|---|---|---|
| ETH | LONG | 0.2 | — | 115 (units unclear — likely USD, inconsistent with "in coin terms" elsewhere) |
| BTC | SHORT (coin-margin) | 9,000 | 101,000 | 0.027 BTC |
| ETH | SHORT (coin-margin) | 6,000 | 3,543 | 0.75 ETH |
| BTC | SHORT (coin-margin) | 20,200 | 121,000 | 0.094 BTC |
| BTC | SHORT (coin-margin) | 10,500 | 110,000 | 0.04 BTC |
| BTC | SHORT (coin-margin) | 7,750 | 96,000 | 0.019 BTC |
| BTC | SHORT (coin-margin) | 16,900 | 87,700 | 0.025 BTC |

**Six separate BTC/ETH coin-margined short entries at six different BTC
price levels (87.7k, 96k, 101k(ETH long, not short), 110k, 121k)** — reads
as a scaled/laddered short book built up over time as BTC ran from ~88k to
~121k+, rather than one position. No account-level margin/equity total was
provided — only per-lot unrealized P&L in coin terms. **This needs an
account-level balance pull (Hyperliquid API/MCP) before it can be sized
correctly relative to the rest of the portfolio.**

## Open questions (tracked in DISCOVERY.md)
- What are "Spcx" and "Mu" actually — real Hyperliquid perp tickers, or
  transcription artifacts?
- What is total Hyperliquid account equity (margin balance), not just
  per-position P&L?
- Is the "coin margin short" book still open as of 2026-08-26, and is it
  intended as a directional bet, a hedge against the Coinbase spot BTC/ETH
  holdings, or a funding-rate carry trade?
