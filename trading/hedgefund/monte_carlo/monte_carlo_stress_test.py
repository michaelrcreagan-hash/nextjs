"""
Monte Carlo Stress Test — 4-Sleeve Portfolio
Simulates 10,000 paths and stress-tests against 2008/2022 drawdown scenarios.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import os, json

np.random.seed(42)
N_PATHS = 10000
YEARS = 10

# ── 1. SLEEVE PARAMETERS ──────────────────────────────────────────────
# Means = annualised returns, vols = annualised volatility
# Correlated via Cholesky
sleeves = {
    "Macro":      {"mean": 0.35, "vol": 0.18, "base_w": 0.30},
    "Income":     {"mean": 0.07, "vol": 0.08, "base_w": 0.25},
    "Innovation": {"mean": 0.65, "vol": 0.38, "base_w": 0.20},
    "Options":    {"mean": 0.20, "vol": 0.30, "base_w": 0.05},
}

names = list(sleeves.keys())
means = np.array([sleeves[n]["mean"] for n in names])
vols  = np.array([sleeves[n]["vol"]  for n in names])

# Correlation matrix: Macro/Income low corr, Innovation higher, Options highest
corr = np.array([
    [1.00, 0.20, 0.55, 0.60],   # Macro
    [0.20, 1.00, 0.15, 0.10],   # Income
    [0.55, 0.15, 1.00, 0.70],   # Innovation
    [0.60, 0.10, 0.70, 1.00],   # Options
])
cov = np.outer(vols, vols) * corr
chol = np.linalg.cholesky(cov)

# ── 2. REGIME OVERLAY ─────────────────────────────────────────────────
# Current MIXED/CAUTION regime reduces Innovation & Options weights
regime_weights = {
    "RISK-ON":  np.array([0.40, 0.15, 0.35, 0.10]),
    "MIXED":    np.array([0.30, 0.25, 0.20, 0.10]),
    "CAUTION":  np.array([0.15, 0.40, 0.05, 0.05]),
    "RISK-OFF": np.array([0.05, 0.50, 0.00, 0.00]),
}
current_regime = "MIXED"          # Jul 7 2026
weights = regime_weights[current_regime]

# Cash from residual
cash_w = 1.0 - weights.sum()     # ~0.05

# ── 3. MONTE CARLO ────────────────────────────────────────────────────
# Monthly steps for 10 years
months = YEARS * 12
dt = 1/12

# Paths array: [month, sleeve, path]
mu_month  = means * dt
sigma_month = vols * np.sqrt(dt)

# Pre-generate normals: shape [months, 4, N_PATHS]
Z = np.random.randn(months, 4, N_PATHS)
# Correlate
for t in range(months):
    Z[t] = chol @ Z[t]

# Cumulative returns per sleeve per path
cum = np.cumsum(mu_month[None, :, None] + sigma_month[None, :, None] * Z, axis=0)
# Shape: [months, 4, N_PATHS] → convert to growth factors
growth = np.exp(cum)   # [months, 4, N_PATHS]

# Apply regime weights (constant for now)
w = weights[:, None, None]   # [4, 1, 1]
portfolio_growth = (growth * w.reshape(1, -1, 1)).sum(axis=1)   # [months, N_PATHS]
# Add cash (no growth)
cash_growth = np.ones((months, N_PATHS)) * (1 + 0.05 * dt) ** np.arange(months)[:, None]
portfolio_growth += cash_w * (cash_growth - 1)

# Cumulative portfolio value
portfolio_value = np.cumprod(1 + portfolio_growth, axis=0)

# ── 4. STRESS PERIODS ────────────────────────────────────────────────
# 2008 Crisis simulation: 6-month equity drawdown
# 2022 drawdown simulation

def apply_crisis(paths, crisis_months, sleeve_shocks):
    """sleeve_shocks: 6-element array of cumulative returns during crisis"""
    shocked = paths.copy()
    start = months - crisis_months
    for i, name in enumerate(names[:len(sleeve_shocks)]):
        # Replace tail with shock
        idx = list(sleeves.keys()).index(name)
        shocked[start:, :] *= (1 + sleeve_shocks[idx])
    return shocked

# 2008-style: Macro -22%, Income +4%, Innovation -45%, Options -50%
crisis_2008_shocks = np.array([-0.22, 0.04, -0.45, -0.50])
paths_2008 = apply_crisis(portfolio_value.copy(), 6, crisis_2008_shocks)

# 2022-style: Macro -18%, Income -8%, Innovation -35%, Options -30%
crisis_2022_shocks = np.array([-0.18, -0.08, -0.35, -0.30])
paths_2022 = apply_crisis(portfolio_value.copy(), 6, crisis_2022_shocks)

# Combined: 2008 + 2022 back-to-back
paths_2crisis = apply_crisis(portfolio_value.copy(), 12, np.concatenate([crisis_2008_shocks, crisis_2022_shocks]))

# ── 5. STATISTICS ─────────────────────────────────────────────────────
def calc_stats(paths, label):
    final = paths[-1, :]
    cagr = np.power(final, 1/YEARS) - 1
    # Max drawdown
    running_max = np.maximum.accumulate(paths, axis=0)
    drawdowns = (paths - running_max) / running_max
    max_dd = drawdowns.min(axis=0)
    # Prob of loss
    prob_loss = (final < 1.0).mean()
    # Prob of >$1M from $70K starting capital
    prob_1m = (final > 1_000_000/70_000).mean()
    # Prob of >$10M
    prob_10m = (final > 10_000_000/70_000).mean()
    return {
        "Scenario": label,
        "Median Final ($K)": round(float(np.median(final))*70, 0),
        "Mean Final ($K)": round(float(np.mean(final))*70, 0),
        "Median CAGR": round(float(np.median(cagr))*100, 1),
        "Mean CAGR": round(float(np.mean(cagr))*100, 1),
        "Worst 5% Final ($K)": round(float(np.percentile(final, 5))*70, 0),
        "Best 5% Final ($K)": round(float(np.percentile(final, 95))*70, 0),
        "Max DD (median)": f"{float(np.median(max_dd))*100:.1f}%",
        "Max DD (worst 5%)": f"{float(np.percentile(max_dd, 5))*100:.1f}%",
        "Prob Loss": f"{float(prob_loss)*100:.1f}%",
        "Prob >$1M":  f"{float(prob_1m)*100:.1f}%",
        "Prob >$10M": f"{float(prob_10m)*100:.1f}%",
    }

results = []
for paths, label in [
    (portfolio_value, "Baseline (no crisis)"),
    (paths_2008, "2008 Crisis Stress (yr 9-10)"),
    (paths_2022, "2022 Drawdown Stress (yr 9-10)"),
    (paths_2crisis, "Dual Crisis (2008 + 2022, yr 8-10)"),
]:
    results.append(calc_stats(paths, label))

df = pd.DataFrame(results)

# ── 6. PLOT ────────────────────────────────────────────────────────────
out_dir = os.path.dirname(os.path.abspath(__file__))
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle("Monte Carlo Stress Test: 4-Sleeve Portfolio\n10,000 paths × 10 years | $70K base + $3K/mo", fontsize=15, fontweight='bold')

def plot_paths(ax, paths, label, color, alpha=0.08):
    month_grid = np.arange(months)
    # Plot 200 representative paths + median + 5/95 percentiles
    n_plot = min(200, N_PATHS)
    idx = np.random.choice(N_PATHS, n_plot, replace=False)
    for i in idx:
        ax.plot(month_grid, paths[:, i]*70_000, color=color, alpha=alpha, linewidth=0.5)
    p05 = np.percentile(paths, 5, axis=1) * 70_000
    p50 = np.percentile(paths, 50, axis=1) * 70_000
    p95 = np.percentile(paths, 95, axis=1) * 70_000
    ax.plot(month_grid, p50, color='white', lw=2.5, label='Median')
    ax.plot(month_grid, p05, color='#ff4444', lw=1.5, ls='--', label='5th %ile')
    ax.plot(month_grid, p95, color='#44ff44', lw=1.5, ls='--', label='95th %ile')
    ax.axhline(1_000_000, color='gold', lw=1.5, ls=':', label='$1M target')
    ax.axhline(100_000, color='cyan', lw=1, ls=':', label='$100K')
    ax.set_title(label, fontsize=11, fontweight='bold')
    ax.set_xlabel("Months")
    ax.set_ylabel("Portfolio Value ($)")
    ax.set_yscale('log')
    ax.legend(fontsize=7, loc='upper left')
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, months)

plot_paths(axes[0,0], portfolio_value, "Baseline — No Crisis", '#4488ff')
plot_paths(axes[0,1], paths_2008, "2008 Crisis (yr 9-10)", '#ff6644')
plot_paths(axes[1,0], paths_2022, "2022 Drawdown (yr 9-10)", '#ff4444')
plot_paths(axes[1,1], paths_2crisis, "Dual Crisis (2008+2022)", '#cc0000')

plt.tight_layout(rect=[0, 0, 1, 0.96])

# ── 7. DRAWDOWN COMPARISON CHART ──────────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(12, 6))
for paths, label, color in [
    (portfolio_value, "Baseline", '#4488ff'),
    (paths_2008, "+2008 Crisis", '#ff6644'),
    (paths_2022, "+2022 Drawdown", '#ff4444'),
    (paths_2crisis, "+Dual Crisis", '#cc0000'),
]:
    running_max = np.maximum.accumulate(paths, axis=0)
    dd = ((paths - running_max) / running_max).min(axis=0)
    dd_p05 = np.percentile(dd, 5) * 100
    dd_p50 = np.percentile(dd, 50) * 100
    dd_p95 = np.percentile(dd, 95) * 100
    ax2.barh(label, dd_p50, color=color, alpha=0.8, height=0.5)
    ax2.errorbar(dd_p50, label, xerr=[[abs(dd_p05-dd_p50)], [abs(dd_p95-dd_p50)]],
                 color='black', capsize=5, elinewidth=1)

ax2.axvline(-15, color='orange', lw=1.5, ls='--', label='-15% threshold')
ax2.axvline(-25, color='red', lw=1.5, ls='--', label='-25% threshold')
ax2.set_xlabel("Max Drawdown % (median ± 90% CI)")
ax2.set_title("Max Drawdown Distribution by Scenario", fontsize=13, fontweight='bold')
ax2.legend(loc='lower left')
ax2.grid(True, alpha=0.3, axis='x')

plt.tight_layout()

# ── 8. ALLOCATION PIE + REGIME MATRIX ────────────────────────────────
fig3, axes3 = plt.subplots(1, 2, figsize=(14, 6))

# Pie chart — current allocation
ax_pie = axes3[0]
labels_pie = list(weights) + [cash_w]
labels_text = [f"{n}\n{w*100:.0f}%" for n, w in zip(names + ["Cash"], labels_pie)]
colors_pie = ['#4477ff', '#ff8844', '#44cc44', '#ff44ff', '#aaaaaa']
ax_pie.pie(labels_pie, labels=labels_text, colors=colors_pie, startangle=90,
           textprops={'fontsize': 9})
ax_pie.set_title("Current Allocation\nMIXED/CAUTION Regime", fontsize=11, fontweight='bold')

# Regime matrix heatmap
ax_heat = axes3[1]
regime_names = list(regime_weights.keys())
regime_matrix = np.array([list(regime_weights[r]) + [1-regime_weights[r].sum()] for r in regime_names])
im = ax_heat.imshow(regime_matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=0.5)
ax_heat.set_xticks(np.arange(len(names)+1))
ax_heat.set_xticklabels(names + ["Cash"], rotation=15, ha='right')
ax_heat.set_yticks(np.arange(len(regime_names)))
ax_heat.set_yticklabels(regime_names)
for i in range(len(regime_names)):
    for j in range(len(names)+1):
        ax_heat.text(j, i, f"{regime_matrix[i,j]*100:.0f}%", ha='center', va='center',
                    color='white' if regime_matrix[i,j] > 0.25 else 'black', fontsize=10)
ax_heat.set_title("Regime-Adjusted Allocation", fontsize=11, fontweight='bold')
plt.colorbar(im, ax=ax_heat, label='Weight')

plt.tight_layout()

# ── 9. SAVE ────────────────────────────────────────────────────────────
chart_path = os.path.join(out_dir, "monte_carlo_stress_test.png")
chart_dd  = os.path.join(out_dir, "drawdown_comparison.png")
chart_pie = os.path.join(out_dir, "allocation_by_regime.png")
fig.savefig(chart_path, dpi=150, bbox_inches='tight')
fig2.savefig(chart_dd, dpi=150, bbox_inches='tight')
fig3.savefig(chart_pie, dpi=150, bbox_inches='tight')

# Save stats JSON
stats_path = os.path.join(out_dir, "monte_carlo_stats.json")
with open(stats_path, 'w') as f:
    json.dump(results, f, indent=2)

# Print table
print("\n" + "="*90)
print("MONTE CARLO STRESS TEST RESULTS (10,000 paths × 10 years)")
print("="*90)
for r in results:
    print(f"\n{r['Scenario']}")
    for k, v in r.items():
        if k != "Scenario":
            print(f"  {k:30s}: {v:>12}")

print("\n" + "="*90)
print("FILES SAVED:")
print(f"  {chart_path}")
print(f"  {chart_dd}")
print(f"  {chart_pie}")
print(f"  {stats_path}")
print("="*90)

# Key takeaway
print("\n🎯 KEY TAKEAWAY:")
baseline = results[0]
crisis_08 = results[1]
crisis_22 = results[2]
dual = results[3]
print(f"   Baseline: {baseline['Median Final ($K)']} median → {baseline['Median CAGR']} median CAGR")
print(f"   +2008:    {crisis_08['Median Final ($K)']} median → {crisis_08['Median CAGR']} median CAGR")
print(f"   +2022:    {crisis_22['Median Final ($K)']} median → {crisis_22['Median CAGR']} median CAGR")
print(f"   +Dual:    {dual['Median Final ($K)']} median → {dual['Median CAGR']} median CAGR")
dual_median = float(dual['Median Final ($K)'])
dual_worst = float(dual['Worst 5% Final ($K)'])
print(f"\n   Even through dual crisis, median path reaches ~${dual_median:,.0f}")
print(f"   5th percentile through dual crisis: ${dual_worst:,.0f}")
