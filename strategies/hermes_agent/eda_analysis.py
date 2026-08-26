"""
CBT Framework /cbt:eda -- hermes_agent

Self-contained EDA script. Loads the two time-series datasets staged in
Data/ (btc_historical_data.csv, btc_ml_features.csv) and produces the
core + ML-specific analyses described in DISCOVERY.md, saving plots to
plots/eda/ and printing summary stats to stdout for EDA.md to cite.

Note on scope: the real-account holdings CSVs in Data/real_accounts/ are
point-in-time snapshots, not time series -- they are NOT included here.
There is nothing to run returns/volatility/seasonality analysis on until
historical price data is fetched for those tickers (see DISCOVERY.md's
data-gap section). This script covers what's actually replayable today:
the BTC/ETH/SOL/spot-ETF/SPY/TLT daily panel and the BTC ML feature set.
"""
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from statsmodels.tsa.stattools import adfuller, kpss

warnings.filterwarnings("ignore")

sns.set_theme(style="darkgrid", palette="deep")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["figure.dpi"] = 150

HERE = Path(__file__).parent
DATA = HERE / "Data"
PLOTS = HERE / "plots" / "eda"
PLOTS.mkdir(parents=True, exist_ok=True)

summary = {}

# ---------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------
px = pd.read_csv(DATA / "btc_historical_data.csv", parse_dates=["Date"]).set_index("Date").sort_index()
feat = pd.read_csv(DATA / "btc_ml_features.csv", parse_dates=["Date"]).set_index("Date").sort_index()

print("=== Data Overview ===")
print("btc_historical_data.csv:", px.shape, px.index.min().date(), "->", px.index.max().date())
print("btc_ml_features.csv:", feat.shape, feat.index.min().date(), "->", feat.index.max().date())

summary["price_shape"] = list(px.shape)
summary["price_range"] = [str(px.index.min().date()), str(px.index.max().date())]
summary["feat_shape"] = list(feat.shape)
summary["feat_range"] = [str(feat.index.min().date()), str(feat.index.max().date())]

# gap check (trading-day cadence is irregular across crypto 7d/wk vs equity 5d/wk
# sources merged into one panel, so just report calendar-day gaps > 3 days)
gaps = px.index.to_series().diff().dt.days
big_gaps = gaps[gaps > 3]
print(f"\nCalendar gaps >3 days in price panel: {len(big_gaps)}")
summary["price_gaps_gt_3d"] = int(len(big_gaps))
if len(big_gaps):
    print(big_gaps.tail(10))

dup_dates = px.index.duplicated().sum()
print("Duplicate dates (price panel):", dup_dates)
summary["price_dup_dates"] = int(dup_dates)

missing_pct = px.isnull().mean().mean() * 100
print(f"Missing values (price panel): {missing_pct:.3f}%")
summary["price_missing_pct"] = float(missing_pct)

# ---------------------------------------------------------------------
# 2. Returns distribution (BTC-USD as primary asset)
# ---------------------------------------------------------------------
rets = px.pct_change().dropna()
btc_ret = rets["BTC-USD"]
log_ret = np.log(px["BTC-USD"]).diff().dropna()

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
sns.histplot(btc_ret, kde=True, ax=axes[0], color="#4C72B0")
axes[0].set_title("BTC-USD daily returns")
sns.histplot(log_ret, kde=True, ax=axes[1], color="#DD8452")
axes[1].set_title("BTC-USD daily log returns")
stats.probplot(btc_ret, dist="norm", plot=axes[2])
axes[2].set_title("QQ plot vs Normal")
plt.tight_layout()
plt.savefig(PLOTS / "returns_distribution.png")
plt.close()

skew, kurt = stats.skew(btc_ret), stats.kurtosis(btc_ret)
print(f"\nBTC daily return: mean={btc_ret.mean():.5f} std={btc_ret.std():.5f} skew={skew:.3f} kurtosis={kurt:.3f}")
summary["btc_ret_mean"] = float(btc_ret.mean())
summary["btc_ret_std"] = float(btc_ret.std())
summary["btc_ret_skew"] = float(skew)
summary["btc_ret_kurtosis"] = float(kurt)

# ---------------------------------------------------------------------
# 3. Correlation matrix (all assets, close-to-close returns)
# ---------------------------------------------------------------------
corr = rets.corr()
plt.figure(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, vmin=-1, vmax=1)
plt.title("Daily return correlation -- price panel")
plt.tight_layout()
plt.savefig(PLOTS / "correlation_matrix.png")
plt.close()

btc_corrs = corr["BTC-USD"].drop("BTC-USD").sort_values(ascending=False)
print("\nCorrelation with BTC-USD returns:")
print(btc_corrs)
summary["btc_corr_with_others"] = btc_corrs.round(3).to_dict()

# ---------------------------------------------------------------------
# 4. Volume -- NOT AVAILABLE (close-only panel). Document instead of fake it.
# ---------------------------------------------------------------------
print("\n[SKIP] Volume profile: btc_historical_data.csv has no volume column "
      "(close-only multi-asset panel). btc_ml_features.csv has proxy volume "
      "columns (btc_volume, mstr_volume, total_volume) -- see feature EDA below.")

# ---------------------------------------------------------------------
# 5. Seasonality (day-of-week, month -- no intraday data so no hour-of-day)
# ---------------------------------------------------------------------
dow_ret = btc_ret.groupby(btc_ret.index.dayofweek).mean()
dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
month_ret = btc_ret.groupby(btc_ret.index.month).mean()

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.barplot(x=[dow_labels[i] for i in dow_ret.index], y=dow_ret.values, ax=axes[0], color="#55A868")
axes[0].set_title("BTC mean daily return by day-of-week")
axes[0].axhline(0, color="black", linewidth=0.8)
sns.barplot(x=month_ret.index, y=month_ret.values, ax=axes[1], color="#C44E52")
axes[1].set_title("BTC mean daily return by month")
axes[1].axhline(0, color="black", linewidth=0.8)
plt.tight_layout()
plt.savefig(PLOTS / "seasonality.png")
plt.close()

summary["dow_return"] = {dow_labels[i]: float(v) for i, v in dow_ret.items()}
summary["month_return"] = {int(k): float(v) for k, v in month_ret.items()}

# ---------------------------------------------------------------------
# 6. Volatility regimes
# ---------------------------------------------------------------------
roll_vol_7 = btc_ret.rolling(7).std() * np.sqrt(365)
roll_vol_30 = btc_ret.rolling(30).std() * np.sqrt(365)
roll_vol_90 = btc_ret.rolling(90).std() * np.sqrt(365)

fig, ax = plt.subplots(figsize=(14, 5))
roll_vol_7.plot(ax=ax, alpha=0.4, label="7d annualized vol")
roll_vol_30.plot(ax=ax, label="30d annualized vol", linewidth=2)
roll_vol_90.plot(ax=ax, label="90d annualized vol", linewidth=2)
ax.set_title("BTC rolling annualized volatility (regime clustering)")
ax.legend()
plt.tight_layout()
plt.savefig(PLOTS / "volatility_regimes.png")
plt.close()

vol_regime_high = (roll_vol_30 > roll_vol_30.median() * 1.5).sum()
print(f"\nDays with 30d vol > 1.5x median (high-vol regime): {vol_regime_high} / {len(roll_vol_30.dropna())}")
summary["vol_30d_median_annualized"] = float(roll_vol_30.median())
summary["high_vol_days"] = int(vol_regime_high)

# ---------------------------------------------------------------------
# 7. Stationarity
# ---------------------------------------------------------------------
adf_price = adfuller(px["BTC-USD"].dropna())
adf_ret = adfuller(btc_ret)
kpss_ret_stat, kpss_ret_p, *_ = kpss(btc_ret, nlags="auto")

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
px["BTC-USD"].plot(ax=axes[0], label="BTC-USD price")
px["BTC-USD"].rolling(30).mean().plot(ax=axes[0], label="30d rolling mean")
axes[0].set_title(f"BTC price -- ADF p={adf_price[1]:.4f} (non-stationary if >0.05)")
axes[0].legend()
btc_ret.plot(ax=axes[1], alpha=0.5, label="daily return")
btc_ret.rolling(30).std().plot(ax=axes[1], label="30d rolling std")
axes[1].set_title(f"BTC returns -- ADF p={adf_ret[1]:.4f}, KPSS p={kpss_ret_p:.4f}")
axes[1].legend()
plt.tight_layout()
plt.savefig(PLOTS / "stationarity.png")
plt.close()

print(f"\nADF price: stat={adf_price[0]:.3f} p={adf_price[1]:.4f}")
print(f"ADF returns: stat={adf_ret[0]:.3f} p={adf_ret[1]:.4f}")
print(f"KPSS returns: stat={kpss_ret_stat:.3f} p={kpss_ret_p:.4f}")
summary["adf_price_p"] = float(adf_price[1])
summary["adf_returns_p"] = float(adf_ret[1])
summary["kpss_returns_p"] = float(kpss_ret_p)

# ---------------------------------------------------------------------
# 8. ML feature EDA (project_type=hybrid -> run this section)
# ---------------------------------------------------------------------
feature_cols = [c for c in feat.columns if c != "target"]
X = feat[feature_cols]
y = feat["target"]

# 8a. Feature distributions (grid)
n = len(feature_cols)
ncols = 6
nrows = int(np.ceil(n / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 3, nrows * 2.3))
axes = axes.flatten()
for i, col in enumerate(feature_cols):
    sns.histplot(X[col], ax=axes[i], kde=False, color="#4C72B0")
    axes[i].set_title(col, fontsize=8)
    axes[i].set_xlabel("")
    axes[i].set_ylabel("")
    axes[i].tick_params(labelsize=6)
for j in range(i + 1, len(axes)):
    axes[j].axis("off")
plt.tight_layout()
plt.savefig(PLOTS / "feature_distributions.png")
plt.close()

# 8b. Target analysis
target_balance = y.value_counts(normalize=True)
print("\nTarget class balance:", target_balance.to_dict())
summary["target_balance"] = target_balance.round(3).to_dict()

plt.figure(figsize=(6, 5))
sns.countplot(x=y, palette="deep")
plt.title(f"Target class balance (n={len(y)})")
plt.tight_layout()
plt.savefig(PLOTS / "target_analysis.png")
plt.close()

# 8c. Feature-target correlation (point-biserial via simple corr, target is 0/1)
ft_corr = X.corrwith(y).sort_values()
plt.figure(figsize=(8, 12))
sns.barplot(x=ft_corr.values, y=ft_corr.index, palette="vlag")
plt.title("Feature correlation with target")
plt.axvline(0, color="black", linewidth=0.8)
plt.tight_layout()
plt.savefig(PLOTS / "feature_target_correlations.png")
plt.close()

print("\nTop 5 |correlation| with target:")
top5 = ft_corr.abs().sort_values(ascending=False).head(5)
print(top5)
summary["top5_feature_target_corr"] = {k: float(ft_corr[k]) for k in top5.index}

# 8d. Collinearity (correlation heatmap; VIF on a reduced numeric subset to
# avoid singular-matrix errors from near-duplicate proxy columns)
feat_corr = X.corr()
plt.figure(figsize=(14, 12))
sns.heatmap(feat_corr, cmap="vlag", center=0, vmin=-1, vmax=1,
            xticklabels=True, yticklabels=True)
plt.title("Feature-feature correlation (collinearity)")
plt.xticks(fontsize=6, rotation=90)
plt.yticks(fontsize=6)
plt.tight_layout()
plt.savefig(PLOTS / "collinearity.png")
plt.close()

# flag highly collinear pairs (|corr| > 0.9, excluding diagonal)
high_corr_pairs = []
for i in range(len(feat_corr.columns)):
    for j in range(i + 1, len(feat_corr.columns)):
        v = feat_corr.iloc[i, j]
        if abs(v) > 0.9:
            high_corr_pairs.append((feat_corr.columns[i], feat_corr.columns[j], round(float(v), 3)))
print(f"\nFeature pairs with |corr| > 0.9: {len(high_corr_pairs)}")
for a, b, v in high_corr_pairs:
    print(f"  {a} <-> {b}: {v}")
summary["high_corr_pairs_gt_0.9"] = high_corr_pairs

# 8e. Missing values (already known to be zero, but confirm + plot for completeness)
miss = X.isnull().sum()
plt.figure(figsize=(10, 3))
sns.heatmap(X.isnull().T, cbar=False, cmap="Reds")
plt.title(f"Missingness heatmap (total missing cells: {int(miss.sum())})")
plt.tight_layout()
plt.savefig(PLOTS / "missing_values.png")
plt.close()
summary["feat_missing_total"] = int(miss.sum())

# 8f. Train/test (first 70% vs last 30%, chronological) distribution drift
split_idx = int(len(feat) * 0.7)
train, test = X.iloc[:split_idx], X.iloc[split_idx:]
drift_cols = ["btc_pct_above_ma200", "total_etf_flow", "funding_proxy", "oi_proxy",
              "risk_on_proxy", "btc_volume_zscore"]
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
axes = axes.flatten()
for i, col in enumerate(drift_cols):
    sns.kdeplot(train[col], ax=axes[i], label="train (first 70%)", fill=True, alpha=0.4)
    sns.kdeplot(test[col], ax=axes[i], label="test (last 30%)", fill=True, alpha=0.4)
    axes[i].set_title(col, fontsize=9)
    axes[i].legend(fontsize=7)
plt.tight_layout()
plt.savefig(PLOTS / "train_test_comparison.png")
plt.close()

drift_flags = {}
for col in feature_cols:
    ks_stat, ks_p = stats.ks_2samp(train[col], test[col])
    if ks_p < 0.01:
        drift_flags[col] = {"ks_stat": round(float(ks_stat), 3), "p": round(float(ks_p), 5)}
print(f"\nFeatures with significant train/test distribution drift (KS test, p<0.01): {len(drift_flags)}")
for k, v in drift_flags.items():
    print(f"  {k}: {v}")
summary["train_test_drift_features"] = drift_flags

# ---------------------------------------------------------------------
# Save summary JSON for EDA.md generation
# ---------------------------------------------------------------------
with open(HERE / "plots" / "eda" / "eda_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

print("\n=== EDA complete. Plots saved to plots/eda/, summary in plots/eda/eda_summary.json ===")
