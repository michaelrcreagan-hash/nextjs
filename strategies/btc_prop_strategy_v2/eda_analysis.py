"""EDA for btc_prop_strategy_v2 -- core + indicator + prop-firm risk analysis.

Data source: FMP cryptocurrency-historical-price-eod-full, BTCUSD, daily bars,
2018-01-01 to 2026-07-23 (the only dataset confirmed reachable this session --
funding/OI, CVD, on-chain, and Coinglass microstructure data are all unsourced,
see DISCOVERY.md/RESEARCH.md). This EDA therefore covers price/volume/technical
analysis only; funding-rate, CVD, on-chain, and Coinglass-layer EDA is deferred
until those sources are found.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
from statsmodels.tsa.stattools import adfuller, kpss

sns.set_theme(style="darkgrid", palette="deep")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["figure.dpi"] = 150
plt.rcParams["font.size"] = 11

DATA_PATH = "Data/btc_ohlcv_1d.csv"
PLOT_DIR = "plots/eda"

GREEN, RED, BLUE, ORANGE = "#2ecc71", "#e74c3c", "#3498db", "#f39c12"


def savefig(name):
    plt.savefig(f"{PLOT_DIR}/{name}", bbox_inches="tight", facecolor="white")
    plt.close()


# ── Load ──────────────────────────────────────────────────────────────
df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
df["returns"] = df["close"].pct_change()
df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

print("=" * 60)
print("DATA OVERVIEW")
print("=" * 60)
print(f"Rows: {len(df)}")
print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
print(f"Columns: {list(df.columns)}")
print(f"Missing values:\n{df.isna().sum()}")
date_diffs = df["date"].diff().dt.days.dropna()
gaps = (date_diffs > 1).sum()
print(f"Duplicate dates: {df['date'].duplicated().sum()}")
print(f"Gaps (>1 day between rows): {gaps}")
print(f"Max gap: {date_diffs.max()} days")

# ── Returns distribution ────────────────────────────────────────────
ret = df["returns"].dropna()
log_ret = df["log_returns"].dropna()
skew, kurt = stats.skew(ret), stats.kurtosis(ret)
jb_stat, jb_p = stats.jarque_bera(ret)
print("\n" + "=" * 60)
print("RETURNS DISTRIBUTION")
print("=" * 60)
print(f"Mean: {ret.mean():.5f}, Std: {ret.std():.5f}")
print(f"Skewness: {skew:.3f}, Kurtosis (excess): {kurt:.3f}")
print(f"Jarque-Bera: stat={jb_stat:.1f}, p={jb_p:.2e} ({'non-normal' if jb_p < 0.05 else 'normal'})")

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
sns.histplot(ret, kde=True, ax=axes[0], color=BLUE)
axes[0].set_title("Daily Returns Distribution")
sns.histplot(log_ret, kde=True, ax=axes[1], color=BLUE)
axes[1].set_title("Log Returns Distribution")
stats.probplot(ret, dist="norm", plot=axes[2])
axes[2].set_title("QQ Plot (Returns vs Normal)")
plt.tight_layout()
savefig("returns_distribution.png")

# ── Correlation matrix ───────────────────────────────────────────────
corr_cols = ["open", "high", "low", "close", "volume", "vwap", "returns"]
corr = df[corr_cols].corr()
plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0)
plt.title("OHLCV Correlation Matrix")
savefig("correlation_matrix.png")

# ── Volume profile ───────────────────────────────────────────────────
df["abs_returns"] = df["returns"].abs()
vol_mean, vol_std = df["volume"].mean(), df["volume"].std()
vol_anomalies = (df["volume"] > vol_mean + 3 * vol_std).sum()
print("\n" + "=" * 60)
print("VOLUME PROFILE")
print("=" * 60)
print(f"Mean volume: {vol_mean:,.0f}, Std: {vol_std:,.0f}")
print(f"Volume anomalies (>3 std): {vol_anomalies}")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.histplot(df["volume"], ax=axes[0], color=BLUE)
axes[0].set_title("Volume Distribution")
sns.scatterplot(x="volume", y="abs_returns", data=df, ax=axes[1], alpha=0.4, color=BLUE)
axes[1].set_title("Volume vs |Returns|")
plt.tight_layout()
savefig("volume_profile.png")

# ── Seasonality (daily bars: day-of-week and month only, no intraday hour) ──
df["dow"] = df["date"].dt.day_name()
df["month"] = df["date"].dt.month_name()
dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
month_order = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
dow_ret = df.groupby("dow")["returns"].mean().reindex(dow_order)
month_ret = df.groupby("month")["returns"].mean().reindex(month_order)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sns.barplot(x=dow_ret.index, y=dow_ret.values, ax=axes[0],
            palette=[GREEN if v > 0 else RED for v in dow_ret.values])
axes[0].set_title("Avg Return by Day of Week")
axes[0].tick_params(axis="x", rotation=45)
sns.barplot(x=month_ret.index, y=month_ret.values, ax=axes[1],
            palette=[GREEN if v > 0 else RED for v in month_ret.values])
axes[1].set_title("Avg Return by Month")
axes[1].tick_params(axis="x", rotation=45)
plt.tight_layout()
savefig("seasonality.png")

print("\n" + "=" * 60)
print("SEASONALITY (daily bars -- no intraday session data)")
print("=" * 60)
print(f"Best day of week: {dow_ret.idxmax()} ({dow_ret.max():.4f})")
print(f"Worst day of week: {dow_ret.idxmin()} ({dow_ret.min():.4f})")
print(f"Best month: {month_ret.idxmax()} ({month_ret.max():.4f})")
print(f"Worst month: {month_ret.idxmin()} ({month_ret.min():.4f})")

# ── Volatility regimes ───────────────────────────────────────────────
df["vol_7d"] = df["returns"].rolling(7).std() * np.sqrt(365)
df["vol_30d"] = df["returns"].rolling(30).std() * np.sqrt(365)
df["vol_90d"] = df["returns"].rolling(90).std() * np.sqrt(365)
high_vol_thresh = df["vol_30d"].quantile(0.75)
low_vol_thresh = df["vol_30d"].quantile(0.25)

fig, axes = plt.subplots(2, 1, figsize=(14, 8))
axes[0].plot(df["date"], df["vol_7d"], label="7d", alpha=0.5)
axes[0].plot(df["date"], df["vol_30d"], label="30d", linewidth=2)
axes[0].plot(df["date"], df["vol_90d"], label="90d", linewidth=2)
axes[0].axhline(high_vol_thresh, color=RED, linestyle="--", alpha=0.5, label="75th pct (30d)")
axes[0].axhline(low_vol_thresh, color=GREEN, linestyle="--", alpha=0.5, label="25th pct (30d)")
axes[0].set_title("Annualized Rolling Volatility")
axes[0].legend()
sns.histplot(df["vol_30d"].dropna(), ax=axes[1], color=BLUE)
axes[1].set_title("30-Day Annualized Volatility Distribution")
plt.tight_layout()
savefig("volatility_regimes.png")

print("\n" + "=" * 60)
print("VOLATILITY REGIMES")
print("=" * 60)
print(f"30d annualized vol -- median: {df['vol_30d'].median():.2%}, "
      f"25th pct: {low_vol_thresh:.2%}, 75th pct: {high_vol_thresh:.2%}")

# ── Stationarity ─────────────────────────────────────────────────────
adf_price = adfuller(df["close"].dropna())
adf_ret = adfuller(ret)
kpss_price = kpss(df["close"].dropna(), regression="c", nlags="auto")
kpss_ret = kpss(ret, regression="c", nlags="auto")

print("\n" + "=" * 60)
print("STATIONARITY TESTS")
print("=" * 60)
print(f"ADF (price): stat={adf_price[0]:.3f}, p={adf_price[1]:.4f} "
      f"({'stationary' if adf_price[1] < 0.05 else 'non-stationary'})")
print(f"ADF (returns): stat={adf_ret[0]:.3f}, p={adf_ret[1]:.4f} "
      f"({'stationary' if adf_ret[1] < 0.05 else 'non-stationary'})")
print(f"KPSS (price): stat={kpss_price[0]:.3f}, p={kpss_price[1]:.4f} "
      f"({'non-stationary' if kpss_price[1] < 0.05 else 'stationary'})")
print(f"KPSS (returns): stat={kpss_ret[0]:.3f}, p={kpss_ret[1]:.4f} "
      f"({'non-stationary' if kpss_ret[1] < 0.05 else 'stationary'})")

fig, axes = plt.subplots(2, 1, figsize=(14, 8))
axes[0].plot(df["date"], df["close"], color=BLUE)
axes[0].plot(df["date"], df["close"].rolling(90).mean(), color=ORANGE, label="90d MA")
axes[0].set_title("BTC Close Price (non-stationary)")
axes[0].legend()
axes[1].plot(df["date"], df["returns"], color=BLUE, alpha=0.6)
axes[1].axhline(0, color="black", linewidth=0.5)
axes[1].set_title("Daily Returns (stationary)")
plt.tight_layout()
savefig("stationarity.png")

# ── Indicator analysis (Trend Rider / Range Hunter / DCB inputs) ──────
df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
df["ma200"] = df["close"].rolling(200).mean()
df["ma365"] = df["close"].rolling(365).mean()

# ATR / ADX
high_low = df["high"] - df["low"]
high_close = (df["high"] - df["close"].shift()).abs()
low_close = (df["low"] - df["close"].shift()).abs()
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df["atr14"] = tr.rolling(14).mean()

up_move = df["high"].diff()
down_move = -df["low"].diff()
plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
atr_smooth = tr.ewm(alpha=1 / 14, adjust=False).mean()
plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr_smooth
minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr_smooth
dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
df["adx14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

# RSI(2) and RSI(14)
def rsi(series, period):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

df["rsi2"] = rsi(df["close"], 2)
df["rsi14"] = rsi(df["close"], 14)

# Bollinger Bands (20, 2)
df["bb_mid"] = df["close"].rolling(20).mean()
df["bb_std"] = df["close"].rolling(20).std()
df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]

trend_rider_signal = (df["ema9"] > df["ema21"]) & (df["adx14"] > 25)
range_hunter_signal = (df["rsi2"] < 10) | (df["rsi2"] > 90)
below_365dma = (df["close"] < df["ma365"]).sum() / df["ma365"].notna().sum()

print("\n" + "=" * 60)
print("INDICATOR ANALYSIS")
print("=" * 60)
print(f"ADX(14) > 25 (trending) frequency: {(df['adx14'] > 25).mean():.1%}")
print(f"EMA9>EMA21 AND ADX>25 (Trend Rider long trigger) frequency: {trend_rider_signal.mean():.1%}")
print(f"RSI(2) extreme (<10 or >90, Range Hunter trigger) frequency: {range_hunter_signal.mean():.1%}")
print(f"% of days price < 365DMA (DCB-overlay 'confirmed bear' condition): {below_365dma:.1%}")
print(f"Current (last row) price vs 365DMA: "
      f"{'BELOW (bear regime active)' if df['close'].iloc[-1] < df['ma365'].iloc[-1] else 'ABOVE (bear regime not active)'}")

fig, axes = plt.subplots(2, 2, figsize=(16, 10))
sns.histplot(df["adx14"].dropna(), ax=axes[0, 0], color=BLUE)
axes[0, 0].axvline(25, color=RED, linestyle="--", label="ADX=25 threshold")
axes[0, 0].set_title("ADX(14) Distribution")
axes[0, 0].legend()
sns.histplot(df["rsi2"].dropna(), ax=axes[0, 1], color=BLUE)
axes[0, 1].axvline(10, color=GREEN, linestyle="--")
axes[0, 1].axvline(90, color=RED, linestyle="--")
axes[0, 1].set_title("RSI(2) Distribution (Range Hunter thresholds)")
axes[1, 0].plot(df["date"], df["close"], color="gray", alpha=0.5, label="Close")
axes[1, 0].plot(df["date"], df["ma200"], color=ORANGE, label="200DMA")
axes[1, 0].plot(df["date"], df["ma365"], color=RED, label="365DMA (DCB bear regime line)")
axes[1, 0].set_title("Price vs 200DMA/365DMA")
axes[1, 0].legend()
bb_width = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
sns.histplot(bb_width.dropna(), ax=axes[1, 1], color=BLUE)
axes[1, 1].set_title("Bollinger Band Width Distribution (squeeze proxy)")
plt.tight_layout()
savefig("indicator_analysis.png")

# ── Prop firm risk assessment ─────────────────────────────────────────
daily_loss_limit = -0.05  # firm limit
internal_daily_buffer = -0.03  # internal safety buffer
max_dd_limit = -0.10  # firm limit
internal_dd_buffer = -0.06  # internal safety buffer

p_breach_daily_firm = (ret < daily_loss_limit).mean()
p_breach_daily_internal = (ret < internal_daily_buffer).mean()
worst_daily = ret.min()

cummax = df["close"].cummax()
drawdown = (df["close"] - cummax) / cummax
p_dd_breach_firm = (drawdown < max_dd_limit).mean()
p_dd_breach_internal = (drawdown < internal_dd_buffer).mean()
worst_dd = drawdown.min()

print("\n" + "=" * 60)
print("PROP FIRM RISK ASSESSMENT (unlevered BTC buy-hold daily returns, informs sizing)")
print("=" * 60)
print(f"P(daily return < -5% firm limit): {p_breach_daily_firm:.2%}")
print(f"P(daily return < -3% internal buffer): {p_breach_daily_internal:.2%}")
print(f"Worst single-day return: {worst_daily:.2%}")
print(f"P(drawdown < -10% firm limit, unlevered buy-hold): {p_dd_breach_firm:.2%}")
print(f"P(drawdown < -6% internal buffer, unlevered buy-hold): {p_dd_breach_internal:.2%}")
print(f"Worst historical drawdown (unlevered buy-hold): {worst_dd:.2%}")
# at 3x leverage, a raw -X% daily move becomes -3X% on the account
implied_3x_worst_daily = worst_daily * 3
print(f"Worst single-day return AT 3x LEVERAGE (config.yaml max): {implied_3x_worst_daily:.2%} "
      f"-- {'BREACHES' if implied_3x_worst_daily < daily_loss_limit else 'within'} firm 5% daily limit, "
      f"{'BREACHES' if implied_3x_worst_daily < internal_daily_buffer else 'within'} internal 3% buffer")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.histplot(ret, kde=True, ax=axes[0], color=BLUE)
axes[0].axvline(daily_loss_limit, color=RED, linestyle="--", label="Firm limit (-5%)")
axes[0].axvline(internal_daily_buffer, color=ORANGE, linestyle="--", label="Internal buffer (-3%)")
axes[0].axvspan(ret.min(), daily_loss_limit, alpha=0.15, color=RED)
axes[0].set_title("Daily Return Distribution vs Loss Limits (unlevered)")
axes[0].legend()
axes[1].fill_between(df["date"], drawdown, 0, color=RED, alpha=0.4)
axes[1].axhline(max_dd_limit, color=RED, linestyle="--", label="Firm limit (-10%)")
axes[1].axhline(internal_dd_buffer, color=ORANGE, linestyle="--", label="Internal buffer (-6%)")
axes[1].set_title("Drawdown from Peak vs Limits (unlevered buy-hold)")
axes[1].legend()
plt.tight_layout()
savefig("prop_firm_daily_loss_risk.png")

# sizing sensitivity: what leverage keeps P(breach) < 5%?
print("\nLeverage sensitivity (P(levered daily return < internal -3% buffer)):")
for lev in [1, 1.5, 2, 2.5, 3]:
    p = (ret * lev < internal_daily_buffer).mean()
    print(f"  {lev}x: {p:.2%}")

df.to_csv("Data/btc_ohlcv_1d_with_indicators.csv", index=False)
print("\nSaved enriched dataset -> Data/btc_ohlcv_1d_with_indicators.csv")
print("\nAll plots saved to plots/eda/")
