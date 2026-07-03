import urllib.request, json, datetime, os, time

SYMBOLS = {
    "VST": 2019, "CEG": 2022, "TLN": 2023, "OKLO": 2024, "SMR": 2022,
    "CCJ": 2019, "SMCI": 2019, "DELL": 2019, "CLS": 2019,
}
TODAY = datetime.date.today()
START = datetime.date(2019, 1, 1)
OUT = "trading/hedgefund/data"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()

def from_stooq(sym):
    url = f"https://stooq.com/q/d/l/?s={sym.lower()}.us&d1={START:%Y%m%d}&d2={TODAY:%Y%m%d}&i=d"
    text = get(url)
    lines = text.strip().splitlines()
    if not lines or not lines[0].lower().startswith("date"):
        raise ValueError(f"stooq bad response: {lines[:1]}")
    rows = []
    for ln in lines[1:]:
        p = ln.split(",")
        if len(p) < 6 or not p[4]:
            continue
        try:
            vol = float(p[5])
        except ValueError:
            vol = 0.0
        rows.append((p[0], float(p[4]), vol))
    return rows

def from_yahoo(sym):
    p1 = int(time.mktime(datetime.datetime(2019, 1, 1).timetuple()))
    p2 = int(time.time())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"
    data = json.loads(get(url))
    res = data["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    rows = []
    for t, c, v in zip(ts, q["close"], q["volume"]):
        if c is None:
            continue
        d = datetime.datetime.utcfromtimestamp(t).date()
        rows.append((d.isoformat(), float(c), float(v or 0)))
    return rows

report = []
failures = []
for sym, y0 in SYMBOLS.items():
    rows, src = None, None
    for name, fn in (("stooq", from_stooq), ("yahoo", from_yahoo)):
        try:
            rows = fn(sym)
            src = name
            if rows:
                break
        except Exception as e:
            print(f"{sym}: {name} failed: {e}")
    if not rows:
        failures.append(sym)
        continue
    rows = [r for r in rows if r[0] >= f"{y0}-01-01"]
    rows.sort(key=lambda r: r[0])
    with open(f"{OUT}/{sym}.csv", "w") as f:
        f.write("date,close,volume\n")
        for d, c, v in rows:
            f.write(f"{d},{c:.2f},{int(v / 1000 + 0.5)}\n")
    report.append(f"{sym},{src},{len(rows)},{rows[0][0]},{rows[-1][0]}")
    time.sleep(1)

with open(f"{OUT}/_fetch_report.txt", "w") as f:
    f.write("\n".join(report) + ("\nFAILED: " + ",".join(failures) if failures else "") + "\n")
print("\n".join(report))
if failures:
    print("FAILED:", ",".join(failures))
    raise SystemExit(0)
