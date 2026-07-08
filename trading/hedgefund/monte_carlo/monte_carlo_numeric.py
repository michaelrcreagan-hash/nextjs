"""
Monte Carlo Stress Test — 4-sleeve portfolio
Saves JSON summary and chart-ready percentile data.
"""
import json
import numpy as np

np.random.seed(42)
N_PATHS = 10000
YEARS = 10
months = YEARS * 12
monthly_contrib = 3000
base_capital = 70000

sleeves = {
    "Macro":      {"mean": 0.35, "vol": 0.18},
    "Income":     {"mean": 0.07, "vol": 0.08},
    "Innovation": {"mean": 0.60, "vol": 0.36},
    "Options":    {"mean": 0.18, "vol": 0.28},
}
names = list(sleeves.keys())
means = np.array([sleeves[n]["mean"] for n in names])
vols  = np.array([sleeves[n]["vol"]  for n in names])

corr = np.array([
    [1.00, 0.20, 0.55, 0.60],
    [0.20, 1.00, 0.15, 0.10],
    [0.55, 0.15, 1.00, 0.70],
    [0.60, 0.10, 0.70, 1.00],
])
cov = np.outer(vols, vols) * corr
chol = np.linalg.cholesky(cov)

regime_weights = {
    "RISK-ON":  np.array([0.40, 0.15, 0.35, 0.10]),
    "MIXED":    np.array([0.30, 0.25, 0.20, 0.10]),
    "CAUTION":  np.array([0.15, 0.40, 0.05, 0.05]),
    "RISK-OFF": np.array([0.05, 0.50, 0.00, 0.00]),
}
current_regime = "MIXED"
weights = regime_weights[current_regime]
cash_w = 1.0 - float(weights.sum())
assert cash_w >= 0

# Simulate monthly log-returns for each sleeve
Z = np.random.randn(months, 4, N_PATHS)
for t in range(months):
    Z[t] = chol @ Z[t]

mu_month = (means / 12)[None, :, None]
sigma_month = (vols / np.sqrt(12))[None, :, None]
monthly_log_ret = mu_month + sigma_month * Z
monthly_ret = np.exp(monthly_log_ret) - 1  # [months, 4, N_PATHS]

# Weighted portfolio return each month
weights_t = weights[None, :, None]
portfolio_ret = (monthly_ret * weights_t).sum(axis=1)  # [months, N_PATHS]

# Add cash/bond carry: 3.5% monthly equivalent to cash portion
portfolio_ret += cash_w * (0.035 / 12)

# Compound with monthly contributions
portfolio_value = np.zeros((months + 1, N_PATHS), dtype=np.float64)
portfolio_value[0, :] = base_capital
for t in range(months):
    portfolio_value[t + 1, :] = portfolio_value[t, :] * (1 + portfolio_ret[t, :]) + monthly_contrib

# Stress tests: shock only equity sleeves, not cash/bond carry
def apply_crisis(paths, crisis_months, equity_shocks):
    out = paths.copy()
    start = months - crisis_months
    # Apply only to equity portion; cash/bond grows through
    for i, name in enumerate(names):
        if i >= len(equity_shocks) or equity_shocks[i] == 0:
            continue
        w_i = float(weights[i])
        # Simple multiplicative shock to total NAV
        out[start + 1:, :] *= (1 + float(equity_shocks[i]) * w_i)
    return out

# 2008 style: equity drawdowns over 6 months (through Oct 2028 analog)
paths_2008 = apply_crisis(portfolio_value.copy(), 6, [-0.25, 0.02, -0.42, -0.35])
# 2022 style
paths_2022 = apply_crisis(portfolio_value.copy(), 6, [-0.20, -0.06, -0.32, -0.28])
# Dual: back-to-back
paths_2crisis = apply_crisis(portfolio_value.copy(), 12, [-0.25, 0.02, -0.42, -0.35, -0.20, -0.06, -0.32, -0.28])

all_results = {}

def calc_pct(x, p):
    return round(float(np.percentile(x, p)), 0)

def calc_stats(paths, label):
    final = paths[-1, :]
    running_max = np.maximum.accumulate(paths, axis=0)
    drawdowns = (paths - running_max) / running_max
    max_dd = drawdowns.min(axis=0)
    final_cagr = np.power(final / base_capital, 1 / YEARS) - 1
    p1m = 1_000_000
    p10m = 10_000_000
    return {
        "label": label,
        "median_final_k": calc_pct(final, 50) / 1000,
        "mean_final_k": round(float(np.mean(final)) / 1000, 0),
        "worst5_final_k": calc_pct(final, 5) / 1000,
        "best5_final_k": calc_pct(final, 95) / 1000,
        "median_cagr": round(float(np.median(final_cagr)) * 100, 1),
        "mean_cagr": round(float(np.mean(final_cagr)) * 100, 1),
        "max_dd_median": round(float(np.median(max_dd)) * 100, 1),
        "max_dd_worst5": round(float(np.percentile(max_dd, 5)) * 100, 1),
        "prob_loss_pct": round(float((final < base_capital).mean()) * 100, 1),
        "prob_over_1m_pct": round(float((final > p1m).mean()) * 100, 1),
        "prob_over_10m_pct": round(float((final > p10m).mean()) * 100, 1),
    }

for paths, label in [
    (portfolio_value, "Baseline (no crisis)"),
    (paths_2008, "2008-style crisis (years 9-10)"),
    (paths_2022, "2022-style drawdown (years 9-10)"),
    (paths_2crisis, "Dual crisis (2008 + 2022, years 8-10)"),
]:
    all_results[label] = calc_stats(paths, label)

with open("monte_carlo_summary.json", "w") as f:
    json.dump(all_results, f, indent=2)

# Save simplified percentiles for charts
percentiles = {"months": list(range(months + 1)), "dollar_percentiles": {}}
for label, paths, color in [
    ("baseline", portfolio_value, "#4488ff"),
    ("crisis_2008", paths_2008, "#ff6644"),
    ("crisis_2022", paths_2022, "#ff4444"),
    ("dual_crisis", paths_2crisis, "#cc0000"),
]:
    pcts = {
        "p5": [float(x) for x in np.percentile(paths, 5, axis=1)],
        "p50": [float(x) for x in np.percentile(paths, 50, axis=1)],
        "p95": [float(x) for x in np.percentile(paths, 95, axis=1)],
    }
    percentiles["dollar_percentiles"][label] = pcts

with open("monte_carlo_percentiles.json", "w") as f:
    json.dump(percentiles, f)

print("=" * 90)
print("MONTE CARLO STRESS TEST RESULTS (10,000 paths × 10 years)")
print("Base: $70K + $3K/mo | Regime: MIXED/CAUTION")
print("=" * 90)
for label, s in all_results.items():
    print(f"\n{label}")
    for k, v in s.items():
        if k != "label":
            print(f"  {k:30s}: {str(v):>15}")

print("\nFILES: monte_carlo_summary.json, monte_carlo_percentiles.json")
