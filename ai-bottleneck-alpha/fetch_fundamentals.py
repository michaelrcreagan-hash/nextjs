"""
Point-in-time fundamentals from SEC EDGAR's XBRL API.

WHY EDGAR AND NOT A VENDOR
--------------------------
Every fundamental backtest lives or dies on one question: on the day you would
have traded, what did you actually know? Vendor fundamentals are usually keyed
to the FISCAL PERIOD END, and using that date grants 30-90 days of lookahead --
NVDA's July-2026 quarter did not become public until 2026-08-26, so a model
that "knew" it on July 26 is trading on information that did not exist.

EDGAR carries a `filed` date on every individual fact. That removes the need to
assume a reporting lag: the data is point-in-time by construction. It is also
keyless and scriptable, so none of it costs context.

(Other sources were tried first. FMP has filing dates but its price endpoints
are plan-gated and its statements would cost a tool call per ticker. Yahoo's
fundamentals-timeseries is keyless but caps quarterly history at five periods.)

TWO EDGAR GOTCHAS, BOTH FOUND BY RUNNING INTO THEM
--------------------------------------------------
1. HEADERS. SEC rejects a bare non-browser user agent, and separately rejects
   any request carrying no `Accept` header at all -- which urllib omits by
   default. The identical request that succeeds under curl returns 403 from
   Python. Both headers are required; neither alone suffices.

2. companyconcept LIES BY OMISSION. The per-tag endpoint returns a well-formed
   `{"units": {"USD": []}}` -- empty, not 404 -- for tag/company pairs that
   companyfacts holds data for. AMKR, HUBB and CDNS all came back "sparse" that
   way on the first run, and would have been quietly dropped from the study as
   though they were IFRS filers. This module therefore pulls companyfacts once
   per company and reads every tag out of the single authoritative document.
   That is also fewer requests: one per ticker instead of nine to twenty.

WHAT IS COLLECTED
-----------------
Beyond the income-statement lines, one tag matters specifically for this task:

  RevenueRemainingPerformanceObligation -- this is BACKLOG as disclosed under
  ASC 606. The task asked for a backlog filter and, for the firms that report
  it, this is the real number rather than a proxy. ContractWithCustomerLiability
  (deferred revenue) is kept as the weaker fallback.

Foreign filers (ASML, TSM, UMC, CCJ, GFS) file 20-F/40-F and tag under
`ifrs-full` rather than `us-gaap`, so both namespaces are searched and the one
actually used is recorded per concept. Coverage is reported per ticker so gaps
stay visible instead of silently becoming NaN.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.universe import TICKERS

OUT = Path(__file__).resolve().parent / "data" / "fundamentals"
RAW = OUT / "raw"

UA = {"User-Agent": "Mozilla/5.0 (compatible; equity-research/1.0)",
      "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}

# Ordered candidates per concept. Order matters: the first tag with usable
# facts wins, so the most specific/modern tag is listed first.
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet",
                "RevenueFromSaleOfGoods", "Revenue"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "net_income": ["NetIncomeLoss", "ProfitLoss",
                   "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "eps_diluted": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare",
                    "IncomeLossFromContinuingOperationsPerDilutedShare"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "inventory": ["InventoryNet", "Inventories"],
    "backlog_rpo": ["RevenueRemainingPerformanceObligation"],
    "deferred_rev": ["ContractWithCustomerLiabilityCurrent",
                     "ContractWithCustomerLiability", "DeferredRevenueCurrent"],
}
NAMESPACES = ("us-gaap", "ifrs-full")
KEEP_UNITS = ("USD", "USD/shares")


def get(url, retries=4):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            d = urllib.request.urlopen(req, timeout=90).read()
            if d[:2] == b"\x1f\x8b":
                d = gzip.decompress(d)
            return json.loads(d)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if a == retries - 1:
                raise
            time.sleep(2.0 * (a + 1))
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2.0 * (a + 1))
    return None


def cik_map():
    f = RAW / "_cik.json"
    if f.exists():
        return json.loads(f.read_text())
    j = get("https://www.sec.gov/files/company_tickers.json")
    m = {v["ticker"].upper(): f"CIK{int(v['cik_str']):010d}" for v in j.values()}
    RAW.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(m))
    return m


def extract(cf):
    """Pull the wanted concepts out of one companyfacts document."""
    ns_all = cf.get("facts", {})
    data, cov = {}, {}
    for concept, tags in CONCEPTS.items():
        picked, used = [], None
        for tag in tags:
            for ns in NAMESPACES:
                node = ns_all.get(ns, {}).get(tag)
                if not node:
                    continue
                rows = []
                for unit, arr in node.get("units", {}).items():
                    if unit not in KEEP_UNITS:
                        continue
                    for r in arr:
                        if not r.get("filed") or r.get("val") is None:
                            continue
                        rows.append({"start": r.get("start"), "end": r["end"],
                                     "filed": r["filed"], "form": r.get("form"),
                                     "fy": r.get("fy"), "fp": r.get("fp"),
                                     "val": r["val"]})
                if rows:
                    picked, used = rows, f"{ns}:{tag}"
                    break
            if picked:
                break
        data[concept] = picked
        cov[concept] = used
    return data, cov


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    cm = cik_map()
    syms = [t for t in TICKERS if t != "PSTG"]

    print("=" * 100)
    print(f"SEC EDGAR companyfacts -- {len(syms)} tickers, {len(CONCEPTS)} concepts")
    print("  one request per company; every fact carries its own `filed` date")
    print("=" * 100)

    summary = {}
    for i, t in enumerate(syms, 1):
        f = RAW / f"{t}.json"
        if f.exists() and json.loads(f.read_text()).get("src") == "companyfacts":
            d = json.loads(f.read_text())
            summary[t] = d["coverage"]
            n = sum(1 for v in d["coverage"].values() if v)
            print(f"  [{i:>2d}/{len(syms)}] {t:<6s} cached  {n}/{len(CONCEPTS)}")
            continue
        cik = cm.get(t)
        if not cik:
            print(f"  [{i:>2d}/{len(syms)}] {t:<6s} NO CIK")
            summary[t] = {}
            continue
        try:
            cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/{cik}.json")
        except Exception as e:
            print(f"  [{i:>2d}/{len(syms)}] {t:<6s} FAIL {type(e).__name__}")
            summary[t] = {}
            continue
        time.sleep(0.15)
        if not cf:
            print(f"  [{i:>2d}/{len(syms)}] {t:<6s} no companyfacts document")
            summary[t] = {}
            continue
        data, cov = extract(cf)
        f.write_text(json.dumps({"ticker": t, "cik": cik, "src": "companyfacts",
                                 "coverage": cov, "facts": data}))
        summary[t] = cov
        n = sum(1 for v in cov.values() if v)
        ns = {v.split(":")[0] for v in cov.values() if v}
        print(f"  [{i:>2d}/{len(syms)}] {t:<6s} {n}/{len(CONCEPTS)} concepts, "
              f"{len(data['revenue']):>4d} rev facts, "
              f"{len(data['backlog_rpo']):>3d} RPO  [{','.join(sorted(ns)) or '-'}]"
              + ("" if n >= 5 else "   <- SPARSE"))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_coverage.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "-" * 100)
    rev = [t for t, c in summary.items() if c.get("revenue")]
    bl = [t for t, c in summary.items() if c.get("backlog_rpo")]
    gp = [t for t, c in summary.items() if c.get("gross_profit")]
    sparse = [t for t, c in summary.items() if sum(1 for v in c.values() if v) < 5]
    print(f"  revenue      : {len(rev)}/{len(syms)}")
    print(f"  gross profit : {len(gp)}/{len(syms)}")
    print(f"  RPO backlog  : {len(bl)}/{len(syms)}")
    print(f"  sparse       : {len(sparse)}  {sparse}")


if __name__ == "__main__":
    main()
