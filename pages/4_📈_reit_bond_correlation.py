"""
pages/5_📈_reit_bond_correlation.py
J-REIT × 金利 相関分析 ダッシュボード（統合版）

タブ構成:
  Tab 1  全体俯瞰   : 総合判定・KPI・2軸チャート・スプレッド・相関・NAV
  Tab 2  セクター詳細 : セクター比較・個別銘柄詳細分析
  Tab 3  Top5 Pick  : スコアリングによる推奨5銘柄

データソース:
  REIT  : yfinance（各種ティッカー）
  JGB   : 財務省公表 CSV (jgbcm_all.csv + jgbcm.csv)
  ファンダメンタルズ : NAV倍率・LTV・稼働率・含み益は直近決算レポートに基づく参考値
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

from utils.ui_helpers import hero_header

# ─────────────────────────── 定数 ────────────────────────────────────────────
REIT_TICKER     = "1343.T"
REIT_LABEL      = "東証REIT ETF (1343.T)"
ANNUAL_DIST_YEN = 86.0          # 1343.T 概算年間分配金（円/口）

MOF_ALL_CSV    = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_RECENT_CSV = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
BOND_LABEL     = "日本国債10年利回り（財務省）"

ROLL_WINDOW          = 20
STRONG_NEG_THRESHOLD = -0.7
BUY_SIGNAL_WINDOW    = 180
BUY_SIGNAL_RATIO     = 0.90
BOTTOM_YIELD_SURGE   = 0.10
BOTTOM_PRICE_DROP    = -0.010
BOTTOM_VOL_MULT      = 1.50

# サイドバー表示用（参考）
SECTOR_REITS = [
    {"sector": "オフィス",  "ticker": "8952.T", "name": "ジャパンリアルエステイト", "annual_dist": 18000},
    {"sector": "住居",     "ticker": "3269.T", "name": "アドバンス・レジデンス",  "annual_dist":  9000},
    {"sector": "物流",     "ticker": "3481.T", "name": "三菱地所物流REIT",        "annual_dist": 15000},
    {"sector": "商業施設",  "ticker": "8972.T", "name": "KDX不動産投資法人",       "annual_dist":  8000},
    {"sector": "ホテル",   "ticker": "3287.T", "name": "星野リゾートREIT",        "annual_dist":  4000},
]

# ─────────────────────────── セクター定義 ─────────────────────────────────────
# ファンダメンタルズ参考値（直近決算・各種レポートベース）:
#   nav_ratio           : NAV 倍率（純資産価値比）
#   occupancy           : 稼働率 (%)
#   ltv                 : 有利子負債比率 (%)
#   noi_yield           : NOI 利回り (%)
#   unrealized_gain_pct : 含み益割合 (%)  ← 帳簿価額対比の参考値
#   dist_growth         : 直近分配金増減率 (%, YoY)
SECTOR_ANALYSIS = [
    {
        "sector": "オフィス",
        "ticker": "8951.T",
        "name": "日本ビルファンド",
        "annual_dist": 4949,
        "nav_ratio": 1.04,
        "occupancy": 97.5,
        "ltv": 42.1,
        "noi_yield": 4.2,
        "trend_reason": (
            "大手企業のオフィス回帰で都心 A 級物件の稼働率が改善。"
            "賃料上昇が底支えになる一方、金利上昇局面では"
            "借入コスト増と NAV 下押しリスクが残る。"
        ),
        "sub_tickers": [
            {
                "ticker": "8951.T", "name": "日本ビルファンド",
                "annual_dist": 4949,  "ltv": 42.1, "nav_ratio": 1.04,
                "noi_yield": 4.2, "unrealized_gain_pct": 35.2, "dist_growth":  0.5,
            },
            {
                "ticker": "8952.T", "name": "ジャパンリアルエステイト",
                "annual_dist": 18000, "ltv": 43.5, "nav_ratio": 1.03,
                "noi_yield": 3.9, "unrealized_gain_pct": 32.1, "dist_growth":  1.2,
            },
            {
                "ticker": "3234.T", "name": "森ヒルズリート",
                "annual_dist": 2700,  "ltv": 44.2, "nav_ratio": 0.98,
                "noi_yield": 4.0, "unrealized_gain_pct": 18.5, "dist_growth": -0.8,
            },
        ],
    },
    {
        "sector": "物流",
        "ticker": "3281.T",
        "name": "日本プロロジスリート",
        "annual_dist": 10416,
        "nav_ratio": 1.14,
        "occupancy": 99.2,
        "ltv": 38.5,
        "noi_yield": 4.5,
        "trend_reason": (
            "EC 需要拡大とサプライチェーン再編を背景に高稼働を維持。"
            "新規供給増で賃料上昇には一服感も、"
            "長期的な需要の底堅さからプレミアム評価が継続。"
        ),
        "sub_tickers": [
            {
                "ticker": "3281.T", "name": "日本プロロジスリート",
                "annual_dist": 10416, "ltv": 38.5, "nav_ratio": 1.14,
                "noi_yield": 4.5, "unrealized_gain_pct": 52.3, "dist_growth":  3.1,
            },
            {
                "ticker": "3249.T", "name": "産業ファンド投資法人",
                "annual_dist":  5400, "ltv": 40.1, "nav_ratio": 1.08,
                "noi_yield": 4.3, "unrealized_gain_pct": 41.8, "dist_growth":  2.5,
            },
            {
                "ticker": "3471.T", "name": "三井不動産ロジスティクスパーク",
                "annual_dist":  6500, "ltv": 39.8, "nav_ratio": 1.10,
                "noi_yield": 4.4, "unrealized_gain_pct": 45.2, "dist_growth":  2.0,
            },
        ],
    },
    {
        "sector": "住宅",
        "ticker": "3226.T",
        "name": "日本アコモデーション",
        "annual_dist": 6996,
        "nav_ratio": 1.09,
        "occupancy": 97.1,
        "ltv": 45.3,
        "noi_yield": 4.1,
        "trend_reason": (
            "都市部への人口集中と賃料上昇基調で安定収益を確保。"
            "景気変動への耐性が高くディフェンシブな特性があり、"
            "金利上昇局面でも相対的に底堅い推移が続く。"
        ),
        "sub_tickers": [
            {
                "ticker": "3226.T", "name": "日本アコモデーション",
                "annual_dist": 6996, "ltv": 45.3, "nav_ratio": 1.09,
                "noi_yield": 4.1, "unrealized_gain_pct": 43.5, "dist_growth":  1.5,
            },
            {
                "ticker": "3269.T", "name": "アドバンス・レジデンス",
                "annual_dist": 9000, "ltv": 44.8, "nav_ratio": 1.07,
                "noi_yield": 4.0, "unrealized_gain_pct": 38.2, "dist_growth":  1.0,
            },
            {
                "ticker": "8979.T", "name": "スターツプロシード",
                "annual_dist": 3800, "ltv": 46.5, "nav_ratio": 0.95,
                "noi_yield": 3.8, "unrealized_gain_pct": 22.1, "dist_growth": -1.2,
            },
        ],
    },
    {
        "sector": "商業・ホテル",
        "ticker": "8985.T",
        "name": "ジャパン・ホテル・リート",
        "annual_dist": 5061,
        "nav_ratio": 1.02,
        "occupancy": 84.5,
        "ltv": 41.5,
        "noi_yield": 5.1,
        "trend_reason": (
            "インバウンド回復と国内旅行需要で客室単価（ADR）が大幅上昇。"
            "ただし金利感応度が高くスプレッド縮小リスクあり。"
            "稼働率のさらなる改善が株価上昇の鍵。"
        ),
        "sub_tickers": [
            {
                "ticker": "8985.T", "name": "ジャパン・ホテル・リート",
                "annual_dist": 5061, "ltv": 41.5, "nav_ratio": 1.02,
                "noi_yield": 5.1, "unrealized_gain_pct": 28.5, "dist_growth":  8.5,
            },
            {
                "ticker": "3287.T", "name": "星野リゾートREIT",
                "annual_dist": 4000, "ltv": 43.2, "nav_ratio": 0.99,
                "noi_yield": 4.8, "unrealized_gain_pct": 21.3, "dist_growth":  5.2,
            },
            {
                "ticker": "8977.T", "name": "阪急阪神リート",
                "annual_dist": 3000, "ltv": 42.8, "nav_ratio": 0.97,
                "noi_yield": 4.5, "unrealized_gain_pct": 19.8, "dist_growth":  3.1,
            },
        ],
    },
]

# 全ユニバース（Top5 スコアリング・セクター比較用）
REIT_UNIVERSE: list[dict] = [
    {**sub, "sector": s["sector"]}
    for s in SECTOR_ANALYSIS
    for sub in s["sub_tickers"]
]

_SECTOR_COLORS: dict[str, str] = {
    "8951.T": "#42A5F5",
    "3281.T": "#66BB6A",
    "3226.T": "#FFA726",
    "8985.T": "#AB47BC",
}
_SECTOR_COLOR_MAP: dict[str, str] = {
    "オフィス":    "#42A5F5",
    "物流":        "#66BB6A",
    "住宅":        "#FFA726",
    "商業・ホテル": "#AB47BC",
}


# ─────────────────────────── データ取得 ──────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_reit(period: str = "1y") -> pd.Series | None:
    try:
        df = yf.download(REIT_TICKER, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return None
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        idx = pd.to_datetime(close.index)
        close.index = idx.tz_convert(None) if idx.tz is not None else idx
        return close.dropna()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_reit_ohlcv(period: str = "1y") -> pd.DataFrame | None:
    try:
        raw = yf.download(REIT_TICKER, period=period, progress=False, auto_adjust=True)
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        idx = pd.to_datetime(raw.index)
        raw.index = idx.tz_convert(None) if idx.tz is not None else idx
        df = raw[["Close", "Volume"]].copy()
        df.columns = ["close", "volume"]
        return df.dropna(subset=["close"])
    except Exception:
        return None


def _parse_jp_era_date(s: str) -> pd.Timestamp:
    era_offset = {"S": 1925, "H": 1988, "R": 2018}
    era = s[0]
    parts = s[1:].split(".")
    return pd.Timestamp(era_offset[era] + int(parts[0]), int(parts[1]), int(parts[2]))


def _read_mof_csv(url: str) -> list[tuple[pd.Timestamp, float]]:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    lines = r.content.decode("shift_jis", errors="replace").splitlines()
    rows: list[tuple[pd.Timestamp, float]] = []
    for line in lines[2:]:
        parts = line.split(",")
        if len(parts) < 11 or not parts[0] or not parts[10] or parts[10] == "-":
            continue
        try:
            rows.append((_parse_jp_era_date(parts[0].strip()), float(parts[10])))
        except (ValueError, KeyError, IndexError):
            pass
    return rows


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_jgb_yield(lookback_days: int = 400) -> pd.Series | None:
    try:
        rows = _read_mof_csv(MOF_ALL_CSV) + _read_mof_csv(MOF_RECENT_CSV)
        if not rows:
            return None
        s = pd.Series(dict(rows)).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        cutoff = s.index[-1] - pd.Timedelta(days=lookback_days)
        return s[s.index >= cutoff].dropna()
    except Exception:
        return None


@st.cache_data(ttl=3600 * 4, show_spinner=False)
def fetch_sector_prices() -> dict[str, float | None]:
    tickers = [r["ticker"] for r in SECTOR_REITS]
    prices: dict[str, float | None] = {t: None for t in tickers}
    try:
        raw = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        if raw.empty:
            return prices
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            for t in tickers:
                if t in close.columns:
                    s = close[t].dropna()
                    if not s.empty:
                        prices[t] = float(s.iloc[-1])
        elif isinstance(close, pd.Series) and len(tickers) == 1:
            s = close.dropna()
            if not s.empty:
                prices[tickers[0]] = float(s.iloc[-1])
    except Exception:
        pass
    return prices


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_sector_close(period: str = "1y") -> pd.DataFrame | None:
    """セクター代表4銘柄の終値を一括取得（セクター分析用）。"""
    tickers = [s["ticker"] for s in SECTOR_ANALYSIS]
    try:
        raw = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw[["Close"]].copy()
            close.columns = tickers
        idx = pd.to_datetime(close.index)
        close.index = idx.tz_convert(None) if idx.tz is not None else idx
        return close.dropna(how="all")
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_universe_close(period: str = "1y") -> pd.DataFrame | None:
    """全ユニバース12銘柄の終値を一括取得（Top5 スコアリング用）。"""
    tickers = list({r["ticker"] for r in REIT_UNIVERSE})
    try:
        raw = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw[["Close"]].copy()
            close.columns = tickers
        idx = pd.to_datetime(close.index)
        close.index = idx.tz_convert(None) if idx.tz is not None else idx
        return close.dropna(how="all")
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """任意ティッカーの OHLCV を取得（個別銘柄分析用）。"""
    try:
        raw = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        idx = pd.to_datetime(raw.index)
        raw.index = idx.tz_convert(None) if idx.tz is not None else idx
        df = raw[["Close", "Volume"]].copy()
        df.columns = ["close", "volume"]
        return df.dropna(subset=["close"])
    except Exception:
        return None


# ─────────────────────────── 計算 ────────────────────────────────────────────
def load_data() -> tuple[pd.DataFrame | None, str]:
    reit = fetch_reit()
    bond = fetch_jgb_yield()
    if reit is None or bond is None:
        return None, BOND_LABEL
    df = pd.DataFrame({"reit": reit, "bond": bond}).dropna()
    df["reit_ret"]     = df["reit"].pct_change()
    df["bond_ret"]     = df["bond"].pct_change()
    df["rolling_corr"] = df["reit_ret"].rolling(ROLL_WINDOW).corr(df["bond_ret"])
    return df, BOND_LABEL


def compute_yield_analytics(
    ohlcv: pd.DataFrame,
    bond: pd.Series,
    annual_dist: float | None = None,
) -> pd.DataFrame:
    """OHLCV + JGB から利回り分析列を計算。annual_dist 省略時は ANNUAL_DIST_YEN を使用。"""
    dist = annual_dist if annual_dist is not None else ANNUAL_DIST_YEN
    df = ohlcv.copy()
    df["bond"] = bond.reindex(df.index, method="ffill")
    df = df.dropna(subset=["close", "bond"])

    df["dist_yield"]    = dist / df["close"] * 100
    df["yield_max_180"] = df["dist_yield"].rolling(BUY_SIGNAL_WINDOW, min_periods=30).max()
    df["buy_signal"]    = df["dist_yield"] >= BUY_SIGNAL_RATIO * df["yield_max_180"]
    df["spread"]        = df["dist_yield"] - df["bond"]
    df["reit_ret"]      = df["close"].pct_change()
    vol_ma20            = df["volume"].rolling(20).mean()
    df["bottom_signal"] = (
        (df["dist_yield"].diff() >= BOTTOM_YIELD_SURGE)
        & (df["reit_ret"] <= BOTTOM_PRICE_DROP)
        & (df["volume"] >= BOTTOM_VOL_MULT * vol_ma20)
        & (df["volume"] > 0)
    )
    return df


def compute_dividend_score(df: pd.DataFrame) -> int:
    spread_s = df["spread"].dropna()
    if len(spread_s) < 2:
        return -1
    current  = float(spread_s.iloc[-1])
    pct_rank = float((spread_s <= current).mean())
    return int(round(pct_rank * 100))


def compute_sector_analytics(
    close_df: pd.DataFrame, bond: pd.Series
) -> dict[str, pd.DataFrame]:
    sector_map = {s["ticker"]: s for s in SECTOR_ANALYSIS}
    result: dict[str, pd.DataFrame] = {}
    for ticker in close_df.columns:
        if ticker not in sector_map:
            continue
        info = sector_map[ticker]
        s = close_df[ticker].dropna()
        if len(s) < 30:
            continue
        df = pd.DataFrame({"close": s})
        df["bond"]       = bond.reindex(df.index, method="ffill")
        df               = df.dropna()
        df["dist_yield"] = info["annual_dist"] / df["close"] * 100
        df["yield_max_180"] = df["dist_yield"].rolling(BUY_SIGNAL_WINDOW, min_periods=30).max()
        df["buy_signal"] = df["dist_yield"] >= BUY_SIGNAL_RATIO * df["yield_max_180"]
        df["spread"]     = df["dist_yield"] - df["bond"]
        price_ret        = df["close"].pct_change()
        bond_ret         = df["bond"].pct_change()
        df["rolling_corr"] = price_ret.rolling(ROLL_WINDOW).corr(bond_ret)
        result[ticker] = df
    return result


def compute_individual_analytics(
    ohlcv: pd.DataFrame, bond: pd.Series, annual_dist: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """個別銘柄の (df_yield, df_corr) を返す。既存チャート関数と互換。"""
    df_yield = compute_yield_analytics(ohlcv, bond, annual_dist=annual_dist)
    close    = ohlcv["close"].copy()
    df_corr  = pd.DataFrame({"reit": close, "bond": bond}).dropna()
    df_corr["reit_ret"]     = df_corr["reit"].pct_change()
    df_corr["bond_ret"]     = df_corr["bond"].pct_change()
    df_corr["rolling_corr"] = (
        df_corr["reit_ret"].rolling(ROLL_WINDOW).corr(df_corr["bond_ret"])
    )
    return df_yield, df_corr


def compute_universe_analytics(
    close_df: pd.DataFrame | None, bond: pd.Series
) -> list[dict]:
    """
    全ユニバース銘柄の現在指標を計算。
    静的ファンダメンタルズ + live price/yield/spread/spread_pct を付与した
    dict のリストを返す。
    """
    bond_last = float(bond.iloc[-1]) if not bond.empty else float("nan")
    results: list[dict] = []

    for info in REIT_UNIVERSE:
        ticker = info["ticker"]
        record = {**info}

        if close_df is None or ticker not in close_df.columns:
            record.update(current_price=None, current_yield=None,
                          current_spread=None, spread_pct=None)
            results.append(record)
            continue

        s = close_df[ticker].dropna()
        if len(s) < 5:
            record.update(current_price=None, current_yield=None,
                          current_spread=None, spread_pct=None)
            results.append(record)
            continue

        cur_price  = float(s.iloc[-1])
        cur_yield  = info["annual_dist"] / cur_price * 100

        if not np.isnan(bond_last):
            cur_spread   = cur_yield - bond_last
            bond_aligned = bond.reindex(s.index, method="ffill")
            all_yields   = info["annual_dist"] / s * 100
            all_spreads  = (all_yields - bond_aligned).dropna()
            spread_pct   = (
                float((all_spreads <= cur_spread).mean()) * 100
                if len(all_spreads) >= 10 else None
            )
        else:
            cur_spread = None
            spread_pct = None

        record.update(
            current_price  = round(cur_price),
            current_yield  = round(cur_yield, 2),
            current_spread = round(cur_spread, 2) if cur_spread is not None else None,
            spread_pct     = round(spread_pct) if spread_pct is not None else None,
        )
        results.append(record)

    return results


def compute_top5_scores(universe_records: list[dict]) -> pd.DataFrame:
    """
    スコアリング:
      ① スプレッドスコア (40pt) : 1年スプレッドの分位数
      ② NAV スコア    (30pt) : NAV 倍率が低いほど高得点
      ③ LTV スコア    (30pt) : LTV が低いほど高得点（金利耐性）
    """
    rows = []
    for r in universe_records:
        if r.get("current_price") is None:
            continue

        # ① スプレッドスコア
        sp = r.get("spread_pct")
        score_spread = max(0, min(40, round(sp * 0.40))) if sp is not None else 0

        # ② NAV スコア（nav 0.95 → 30pt, 1.15 → 0pt）
        nav = r.get("nav_ratio", 1.10)
        score_nav = max(0, min(30, round((1.15 - nav) / 0.20 * 30)))

        # ③ LTV スコア（ltv 35 → 30pt, 50 → 0pt）
        ltv = r.get("ltv", 45.0)
        score_ltv = max(0, min(30, round((50.0 - ltv) / 15.0 * 30)))

        total = score_spread + score_nav + score_ltv

        rows.append({
            "ティッカー":              r["ticker"],
            "銘柄名":                  r["name"],
            "セクター":                r["sector"],
            "現在価格（円）":           f"¥{r['current_price']:,}",
            "分配金利回り (%)":         r.get("current_yield"),
            "スプレッド (%pt)":        r.get("current_spread"),
            "スプレッドスコア (40pt)": score_spread,
            "NAV倍率":                 nav,
            "NAVスコア (30pt)":        score_nav,
            "LTV (%)":                 ltv,
            "LTVスコア (30pt)":        score_ltv,
            "総合スコア":              total,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("総合スコア", ascending=False).reset_index(drop=True)


def get_summary_metrics(df: pd.DataFrame) -> dict:
    corr_series = df["rolling_corr"].dropna()
    current = float(corr_series.iloc[-1]) if len(corr_series) >= 1 else float("nan")
    prev    = float(corr_series.iloc[-2]) if len(corr_series) >= 2 else float("nan")
    delta   = current - prev if not (np.isnan(current) or np.isnan(prev)) else float("nan")
    reit_ret  = float(df["reit_ret"].iloc[-1]) if len(df) >= 1 else float("nan")
    bond_last = float(df["bond"].iloc[-1])      if len(df) >= 1 else float("nan")
    bond_prev = float(df["bond"].iloc[-2])      if len(df) >= 2 else float("nan")
    bond_chg  = bond_last - bond_prev if not (np.isnan(bond_last) or np.isnan(bond_prev)) else float("nan")
    return dict(
        corr_current=current, corr_delta=delta,
        reit_ret=reit_ret, bond_last=bond_last, bond_chg=bond_chg,
    )


# ─────────────────────────── 総合判定 ────────────────────────────────────────
_VERDICT_STYLE: dict[str, dict] = {
    "強気": {"bg": "#0f2d0f", "border": "#4CAF50", "icon": "📈", "label_color": "#81C784"},
    "中立": {"bg": "#0a1e3d", "border": "#42A5F5", "icon": "↔️", "label_color": "#90CAF9"},
    "慎重": {"bg": "#2e1800", "border": "#FFA726", "icon": "⚠️", "label_color": "#FFCC80"},
    "回避": {"bg": "#220a0a", "border": "#EF5350", "icon": "🚫", "label_color": "#EF9A9A"},
}


def compute_overall_verdict(
    div_score: int, corr_val: float, corr_delta: float,
    bond_chg_1d: float, buy_sig: bool,
) -> tuple[str, str]:
    score_high   = div_score >= 70
    score_low    = div_score < 30
    corr_easing  = corr_delta > 0.02
    corr_strong  = corr_val <= -0.7
    corr_mid     = -0.7 < corr_val <= -0.3
    rate_surging = bond_chg_1d > 0.05

    if score_high and not corr_strong and (corr_easing or not corr_mid):
        verdict = "強気"
        action  = "打診買い推奨。分配金利回りは過去高値圏に達し、金利との逆相関は限定的です。段階的な買い積み増しを検討してください。"
    elif score_high and (corr_strong or corr_mid):
        verdict = "中立"
        action  = "利回り魅力は高いが金利感応度も高い水準です。金利上昇が一服するのを確認しながら分散的に打診買い。"
    elif not score_low and not rate_surging:
        verdict = "中立"
        action  = "現物ホールド・新規買いは打診程度。スプレッドが過去平均水準へ回復するまで待機が無難。"
    elif score_low and rate_surging:
        verdict = "回避"
        action  = "長期金利が急騰しスプレッドが縮小中です。REIT 価格への下押し圧力が強く、新規買いは見送り推奨。"
    elif score_low:
        verdict = "慎重"
        action  = "スプレッドが過去平均を大きく下回っています。金利安定を確認してから再検討。"
    elif rate_surging:
        verdict = "慎重"
        action  = "長期金利の急上昇に要注意。金利動向を注視しながら現物はホールド、新規投資は見送り。"
    else:
        verdict = "中立"
        action  = "現物ホールド・新規買い待機。複数指標が改善方向へ転じるのを確認してからポジション拡大。"

    if buy_sig and verdict == "慎重":
        verdict = "中立"
        action  = f"利回りシグナルが発動中（過去{BUY_SIGNAL_WINDOW}日高値圏）。金利の安定確認後は打診買いを検討できる局面です。"

    return verdict, action


def render_verdict_card(verdict: str, action: str) -> None:
    s = _VERDICT_STYLE[verdict]
    st.markdown(
        f"""
        <div style="background:{s['bg']};border-left:6px solid {s['border']};
                    border-radius:10px;padding:16px 22px 18px;margin:2px 0 18px;">
            <div style="display:flex;align-items:center;gap:14px;">
                <span style="font-size:2.2rem;line-height:1;flex-shrink:0;">{s['icon']}</span>
                <div>
                    <p style="margin:0 0 2px;font-size:0.72rem;color:#999;
                              letter-spacing:0.09em;text-transform:uppercase;">総合投資判定</p>
                    <h2 style="margin:0 0 8px;color:{s['label_color']};
                               font-size:1.75rem;font-weight:700;line-height:1.1;">{verdict}</h2>
                    <p style="margin:0;color:#ddd;font-size:0.93rem;line-height:1.65;">{action}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────── チャート：マクロ ─────────────────────────────────
def build_yield_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bond"], name="JGB 10年利回り",
        line=dict(color="#FF7043", width=1.5, dash="dot"), fill=None,
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["dist_yield"], name="REIT 分配金利回り",
        line=dict(color="#4DB6AC", width=2),
        fill="tonexty", fillcolor="rgba(77,182,172,0.15)",
    ))
    threshold = df["yield_max_180"] * BUY_SIGNAL_RATIO
    fig.add_trace(go.Scatter(
        x=df.index, y=threshold,
        name=f"買いシグナル閾値（180日最高×{BUY_SIGNAL_RATIO:.0%}）",
        line=dict(color="#FFF176", width=1, dash="dash"), opacity=0.6,
    ))
    buys = df[df["buy_signal"]]
    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys.index, y=buys["dist_yield"], name="▲ High Yield (Buy Signal)",
            mode="markers",
            marker=dict(symbol="triangle-up", size=10, color="#00E676",
                        line=dict(color="#00C853", width=1.5)),
        ))
    bottoms = df[df["bottom_signal"]]
    if not bottoms.empty:
        fig.add_trace(go.Scatter(
            x=bottoms.index, y=bottoms["dist_yield"], name="★ 底打ち検知",
            mode="markers",
            marker=dict(symbol="star", size=14, color="#FF9800",
                        line=dict(color="#E65100", width=1.5)),
        ))
    fig.update_layout(
        title=dict(text="REIT 分配金利回り vs JGB 10年利回り（スプレッド帯・シグナル付き）",
                   font=dict(size=15)),
        height=400, margin=dict(l=10, r=10, t=55, b=10),
        legend=dict(orientation="h", y=1.18, x=0, font=dict(size=11)),
        hovermode="x unified",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="分配金利回り (%)", font=dict(size=12)),
                   gridcolor="#1e2130", ticksuffix="%"),
        xaxis=dict(gridcolor="#1e2130"),
    )
    return fig


def build_spread_chart(df: pd.DataFrame) -> go.Figure:
    spread  = df["spread"].dropna()
    avg_1y  = float(spread.mean())
    cur_val = float(spread.iloc[-1])
    colors  = ["#4CAF50" if v >= avg_1y else "#EF5350" for v in spread.values]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=spread.index, y=spread.values, name="イールドスプレッド",
        marker=dict(color=colors, opacity=0.8),
        hovertemplate="%{x|%Y-%m-%d}<br>スプレッド: %{y:.3f}%pt<extra></extra>",
    ))
    fig.add_hline(y=avg_1y, line_dash="dash", line_color="#FFFFFF", line_width=1.5,
                  annotation_text=f"1年平均: {avg_1y:.2f}%pt",
                  annotation_position="right",
                  annotation_font=dict(size=11, color="#FFFFFF"))
    fig.add_hline(y=0, line_dash="dot", line_color="#9E9E9E", line_width=1)
    fig.update_layout(
        title=dict(
            text=f"イールドスプレッド（REIT 分配金利回り − JGB 10年）"
                 f"  ／  現在: {cur_val:.2f}%pt  ／  平均比: {cur_val - avg_1y:+.2f}%pt",
            font=dict(size=14),
        ),
        height=300, margin=dict(l=10, r=130, t=50, b=10),
        hovermode="x unified",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="スプレッド (%pt)", font=dict(size=12)),
                   gridcolor="#1e2130", ticksuffix="%"),
        xaxis=dict(gridcolor="#1e2130"),
        bargap=0.1, showlegend=False,
    )
    return fig


def build_dual_axis_chart(df: pd.DataFrame, reit_label: str = REIT_LABEL) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["reit"], name=reit_label,
        line=dict(color="#2196F3", width=2), yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bond"], name="日本国債10年利回り (%)",
        line=dict(color="#FF5722", width=2, dash="dot"), yaxis="y2",
    ))
    fig.update_layout(
        title=dict(text=f"{reit_label} × 日本国債10年利回り", font=dict(size=15)),
        height=360, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.08, x=0),
        hovermode="x unified",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="価格（円）", font=dict(color="#2196F3")),
                   tickfont=dict(color="#2196F3"), gridcolor="#1e2130"),
        yaxis2=dict(title=dict(text="利回り (%)", font=dict(color="#FF5722")),
                    tickfont=dict(color="#FF5722"), overlaying="y",
                    side="right", gridcolor="#1e2130"),
        xaxis=dict(gridcolor="#1e2130"),
    )
    return fig


def build_correlation_chart(df: pd.DataFrame) -> go.Figure:
    corr = df["rolling_corr"].dropna()
    fig  = go.Figure()
    strong_neg = corr <= STRONG_NEG_THRESHOLD
    in_zone = False
    zone_start = None
    for date, is_neg in strong_neg.items():
        if is_neg and not in_zone:
            zone_start = date; in_zone = True
        elif not is_neg and in_zone:
            fig.add_vrect(x0=zone_start, x1=date,
                          fillcolor="rgba(244,67,54,0.15)", layer="below", line_width=0,
                          annotation_text="強い負の相関", annotation_position="top left",
                          annotation_font=dict(size=9, color="#ef9a9a"))
            in_zone = False
    if in_zone:
        fig.add_vrect(x0=zone_start, x1=corr.index[-1],
                      fillcolor="rgba(244,67,54,0.15)", layer="below", line_width=0,
                      annotation_text="強い負の相関", annotation_position="top left",
                      annotation_font=dict(size=9, color="#ef9a9a"))
    for y_val, color, label in [
        (-0.7, "#ef5350", "−0.7（強い負の相関）"),
        (0.0,  "#9e9e9e", "0"),
        (0.7,  "#66bb6a", "+0.7（強い正の相関）"),
    ]:
        fig.add_hline(y=y_val, line_dash="dash", line_color=color, line_width=1,
                      annotation_text=label, annotation_position="right",
                      annotation_font=dict(size=9, color=color))
    fig.add_trace(go.Scatter(
        x=corr.index, y=corr.values,
        name=f"{ROLL_WINDOW}日ローリング相関",
        mode="lines", line=dict(width=2, color="#7E57C2"),
        fill="tozeroy", fillcolor="rgba(126,87,194,0.12)",
    ))
    fig.update_layout(
        title=dict(text=f"{ROLL_WINDOW}日間ローリング相関係数（J-REIT vs 10年金利）",
                   font=dict(size=14)),
        height=320, margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(range=[-1.1, 1.1], gridcolor="#1e2130", zeroline=False),
        xaxis=dict(gridcolor="#1e2130"),
        showlegend=False,
    )
    return fig


def build_nav_ratio_bar() -> go.Figure:
    """セクター別 NAV 倍率バーチャート（1.0 基準線付き）。"""
    sectors = [s["sector"] for s in SECTOR_ANALYSIS]
    navs    = [s["nav_ratio"] for s in SECTOR_ANALYSIS]
    colors  = [_SECTOR_COLOR_MAP.get(s, "#9E9E9E") for s in sectors]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sectors, y=navs,
        marker=dict(color=colors, opacity=0.85),
        text=[f"{v:.2f}x" for v in navs], textposition="outside",
        hovertemplate="%{x}<br>NAV倍率: %{y:.2f}x<extra></extra>",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#FFFFFF", line_width=1.5,
                  annotation_text="NAV = 1.0（純資産価値と等しい）",
                  annotation_position="right",
                  annotation_font=dict(size=10, color="#FFFFFF"))
    fig.update_layout(
        title=dict(text="セクター別 NAV 倍率（参考値）", font=dict(size=14)),
        height=300, margin=dict(l=10, r=160, t=50, b=10),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="NAV 倍率", font=dict(size=12)),
                   gridcolor="#1e2130", range=[0.88, 1.25]),
        xaxis=dict(gridcolor="#1e2130"),
        showlegend=False,
    )
    return fig


# ─────────────────────────── チャート：セクター ───────────────────────────────
def build_sector_comparison_chart(
    universe_records: list[dict], overall_yield: float
) -> go.Figure:
    """セクター別平均利回り vs REIT 全体利回りの比較チャート。"""
    from collections import defaultdict
    sector_yields: dict[str, list[float]] = defaultdict(list)
    for r in universe_records:
        if r.get("current_yield") is not None:
            sector_yields[r["sector"]].append(r["current_yield"])

    sectors    = [s["sector"] for s in SECTOR_ANALYSIS if s["sector"] in sector_yields]
    avg_yields = [float(np.mean(sector_yields[s])) for s in sectors]
    colors     = [_SECTOR_COLOR_MAP.get(s, "#9E9E9E") for s in sectors]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sectors, y=avg_yields,
        marker=dict(color=colors, opacity=0.85),
        text=[f"{v:.2f}%" for v in avg_yields], textposition="outside",
        hovertemplate="%{x}<br>セクター平均: %{y:.2f}%<extra></extra>",
    ))
    if not np.isnan(overall_yield):
        fig.add_hline(
            y=overall_yield, line_dash="dash", line_color="#FFFFFF", line_width=1.5,
            annotation_text=f"REIT全体 (1343.T): {overall_yield:.2f}%",
            annotation_position="right",
            annotation_font=dict(size=11, color="#FFFFFF"),
        )
    fig.update_layout(
        title=dict(text="セクター別平均分配金利回り vs REIT 全体（1343.T）", font=dict(size=14)),
        height=310, margin=dict(l=10, r=190, t=50, b=10),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="分配金利回り (%)", font=dict(size=12)),
                   gridcolor="#1e2130", ticksuffix="%"),
        xaxis=dict(gridcolor="#1e2130"),
        showlegend=False, bargap=0.35,
    )
    return fig


def build_sector_corr_chart(
    sector_data: dict[str, pd.DataFrame], selected: list[str]
) -> go.Figure:
    sector_map = {s["ticker"]: s for s in SECTOR_ANALYSIS}
    fig = go.Figure()
    for ticker in selected:
        if ticker not in sector_data:
            continue
        corr  = sector_data[ticker]["rolling_corr"].dropna()
        info  = sector_map[ticker]
        color = _SECTOR_COLORS.get(ticker, "#9E9E9E")
        fig.add_trace(go.Scatter(
            x=corr.index, y=corr.values,
            name=f"{info['sector']}（{info['name']}）",
            line=dict(color=color, width=2), mode="lines",
        ))
    for y_val, color, label in [
        (-0.7, "#ef5350", "−0.7"), (0.0, "#9e9e9e", "0"),
    ]:
        fig.add_hline(y=y_val, line_dash="dash", line_color=color, line_width=1,
                      annotation_text=label, annotation_position="right",
                      annotation_font=dict(size=10, color=color))
    fig.update_layout(
        title=dict(text=f"{ROLL_WINDOW}日ローリング相関係数 — セクター別比較",
                   font=dict(size=14)),
        height=350, margin=dict(l=10, r=10, t=55, b=10),
        hovermode="x unified",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(range=[-1.1, 1.1], gridcolor="#1e2130", zeroline=False),
        xaxis=dict(gridcolor="#1e2130"),
        legend=dict(orientation="h", y=1.22, x=0, font=dict(size=11)),
    )
    return fig


def build_sector_yield_bar(
    sector_data: dict[str, pd.DataFrame], selected: list[str], bond_last: float
) -> go.Figure:
    sector_map = {s["ticker"]: s for s in SECTOR_ANALYSIS}
    valid = [t for t in selected if t in sector_data]
    names, yields = [], []
    best_idx, best_spread = -1, -999.0
    for i, ticker in enumerate(valid):
        df   = sector_data[ticker]
        info = sector_map[ticker]
        cur_y = float(df["dist_yield"].iloc[-1])
        cur_s = float(df["spread"].iloc[-1])
        names.append(f"{info['sector']}\n({ticker})")
        yields.append(cur_y)
        if cur_s > best_spread:
            best_spread = cur_s; best_idx = i
    bar_colors = [
        _SECTOR_COLORS.get(valid[i], "#9E9E9E")
        for i in range(len(names))
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=yields,
        marker=dict(color=bar_colors, opacity=0.88),
        text=[f"{v:.2f}%" for v in yields], textposition="outside",
        hovertemplate="%{x}<br>利回り: %{y:.2f}%<extra></extra>",
    ))
    if best_idx >= 0:
        fig.add_trace(go.Scatter(
            x=[names[best_idx]], y=[yields[best_idx]],
            mode="markers+text",
            marker=dict(symbol="star", size=18, color="#FFD700"),
            text=["★"], textposition="top center",
            textfont=dict(size=14, color="#FFD700"),
            hovertemplate=f"{names[best_idx]}<br>最高スプレッド<extra></extra>",
            showlegend=False,
        ))
    if not np.isnan(bond_last):
        fig.add_hline(y=bond_last, line_dash="dash", line_color="#FF7043", line_width=1.8,
                      annotation_text=f"JGB 10年: {bond_last:.3f}%",
                      annotation_position="right",
                      annotation_font=dict(size=11, color="#FF7043"))
    fig.update_layout(
        title=dict(text="セクター別 現在分配金利回り（★＝最高スプレッド）",
                   font=dict(size=14)),
        height=330, margin=dict(l=10, r=130, t=55, b=10),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(title=dict(text="分配金利回り (%)", font=dict(size=12)),
                   gridcolor="#1e2130", ticksuffix="%"),
        xaxis=dict(gridcolor="#1e2130"),
        showlegend=False, bargap=0.35,
    )
    return fig


def build_sector_ranking_table(sector_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    sector_map = {s["ticker"]: s for s in SECTOR_ANALYSIS}
    rows = []
    for ticker, df in sector_data.items():
        if ticker not in sector_map:
            continue
        info       = sector_map[ticker]
        spread_s   = df["spread"].dropna()
        cur_yield  = float(df["dist_yield"].iloc[-1])
        cur_spread = float(df["spread"].iloc[-1])
        avg_spread = float(spread_s.mean()) if len(spread_s) >= 2 else float("nan")
        score = (
            int(round(float((spread_s <= cur_spread).mean()) * 100))
            if len(spread_s) >= 2 else -1
        )
        cur_price = float(df["close"].iloc[-1])
        buy_sig   = bool(df["buy_signal"].iloc[-1])
        sub_labels = " / ".join(f"{s['name']}({s['ticker']})" for s in info["sub_tickers"])
        rows.append({
            "セクター":           info["sector"],
            "指数銘柄":           info["name"],
            "現在株価（円）":      f"¥{cur_price:,.0f}",
            "分配金利回り (%)":    round(cur_yield, 2),
            "スプレッド (%pt)":   round(cur_spread, 2),
            "1年平均スプレッド":   round(avg_spread, 2) if not np.isnan(avg_spread) else "—",
            "配当スコア":         score if score >= 0 else "—",
            "シグナル":           "▲ 発動" if buy_sig else "—",
            "NAV倍率（参考）":    info["nav_ratio"],
            "LTV % （参考）":     info["ltv"],
            "NOI利回り（参考）":   info["noi_yield"],
            "稼働率 % （参考）":   info["occupancy"],
            "価格動向の背景":      info["trend_reason"],
            "代表個別銘柄":        sub_labels,
        })
    return (
        pd.DataFrame(rows)
        .sort_values("スプレッド (%pt)", ascending=False)
        .reset_index(drop=True)
    )


# ─────────────────────────── セクター評価 ────────────────────────────────────
def _evaluate_sector_grade(
    info: dict, sector_df: pd.DataFrame | None
) -> tuple[str, str]:
    """
    セクターの総合評価を返す: (verdict, color_hex)
    NAV倍率・LTV・稼働率・スプレッド分位で採点。
    """
    score = 0
    nav = info.get("nav_ratio", 1.1)
    ltv = info.get("ltv", 45.0)
    occ = info.get("occupancy", 95.0)

    if nav <= 1.00: score += 2
    elif nav <= 1.05: score += 1

    if ltv <= 40.0: score += 2
    elif ltv <= 43.0: score += 1

    if occ >= 97.0: score += 2
    elif occ >= 95.0: score += 1

    if sector_df is not None:
        spread_s = sector_df["spread"].dropna()
        if len(spread_s) >= 10:
            cur = float(spread_s.iloc[-1])
            avg = float(spread_s.mean())
            if cur >= avg + 0.2: score += 2
            elif cur >= avg:     score += 1

    if score >= 6: return "🟢 強気", "#4CAF50"
    if score >= 4: return "🟡 中立", "#FFC107"
    return "🟠 慎重",  "#FF7043"


# ─────────────────────────── Top5 カード ─────────────────────────────────────
def render_top5_cards(scores_df: pd.DataFrame) -> None:
    top5 = scores_df.head(5).reset_index(drop=True)
    rank_icons = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    cols = st.columns(len(top5))

    for i, row in top5.iterrows():
        sector = row["セクター"]
        color  = _SECTOR_COLOR_MAP.get(sector, "#9E9E9E")
        score  = row["総合スコア"]
        spread = row.get("スプレッド (%pt)")
        nav    = row.get("NAV倍率")
        ltv    = row.get("LTV (%)")
        spread_str = f"{spread:.2f}%pt" if isinstance(spread, (int, float)) and pd.notna(spread) else "—"
        nav_str    = f"{nav:.2f}x"      if isinstance(nav,    (int, float)) and pd.notna(nav)    else "—"
        ltv_str    = f"{ltv:.1f}%"      if isinstance(ltv,    (int, float)) and pd.notna(ltv)    else "—"

        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    background:linear-gradient(135deg,#0e1117 0%,#1a1f2e 100%);
                    border:2px solid {color};border-radius:12px;
                    padding:18px 14px 16px;text-align:center;min-height:230px;
                ">
                    <div style="font-size:1.8rem;line-height:1;">{rank_icons[i]}</div>
                    <div style="font-size:0.68rem;color:{color};font-weight:700;
                                letter-spacing:0.06em;margin-top:8px;
                                text-transform:uppercase;">{sector}</div>
                    <div style="font-size:0.84rem;font-weight:600;color:#eee;
                                margin:5px 0 2px;line-height:1.25;">{row['銘柄名']}</div>
                    <div style="font-size:0.68rem;color:#888;margin-bottom:10px;">
                        {row['ティッカー']}
                    </div>
                    <div style="font-size:1.45rem;font-weight:800;color:{color};line-height:1;">
                        {score}<span style="font-size:0.72rem;color:#aaa;font-weight:400;"> / 100</span>
                    </div>
                    <div style="border-top:1px solid {color}33;margin:10px 0 8px;"></div>
                    <div style="font-size:0.70rem;color:#ccc;line-height:1.9;text-align:left;">
                        📊 スプレッド: <b>{spread_str}</b><br>
                        🏦 NAV 倍率: <b>{nav_str}</b><br>
                        💰 LTV: <b>{ltv_str}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ─────────────────────────── サイドバー ──────────────────────────────────────
def render_sidebar(df_yield: pd.DataFrame | None) -> list[str]:
    with st.sidebar:
        st.markdown("## 📊 セクター別利回り")
        st.caption("概算分配金利回り（参考値）")
        sector_prices = fetch_sector_prices()
        for info in SECTOR_REITS:
            price = sector_prices.get(info["ticker"])
            if price and price > 0:
                yld  = info["annual_dist"] / price * 100
                icon = "🟢" if yld >= 4.0 else ("🟡" if yld >= 3.0 else "🔴")
                st.markdown(
                    f"{icon} **{info['sector']}**&nbsp;&nbsp;`{yld:.2f}%`  \n"
                    f"<small style='color:#aaa'>{info['name']}"
                    f"&nbsp;({info['ticker']})&nbsp;¥{price:,.0f}</small>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"⬜ **{info['sector']}**&nbsp;&nbsp;`---`  \n"
                    f"<small style='color:#aaa'>{info['name']}</small>",
                    unsafe_allow_html=True,
                )
        st.caption("※ 年間分配金は予想値を使用した参考値です")

        if df_yield is not None:
            st.divider()
            st.markdown("## 📈 指数概要 (1343.T)")
            reit_price_cur = float(df_yield["close"].iloc[-1])
            dist_yield_cur = float(df_yield["dist_yield"].iloc[-1])
            spread_cur     = float(df_yield["spread"].iloc[-1])
            spread_avg     = float(df_yield["spread"].mean())
            st.metric("ETF 時価", f"¥{reit_price_cur:,.0f}")
            st.metric("分配金利回り（概算）", f"{dist_yield_cur:.2f}%")
            st.metric("イールドスプレッド", f"{spread_cur:.2f}%pt",
                      delta=f"{spread_cur - spread_avg:+.2f}pt vs 1年平均")

        st.divider()
        st.markdown("## 🏢 分析対象セクター")
        _label_map = {
            f"{s['sector']}（{s['name']}）": s["ticker"] for s in SECTOR_ANALYSIS
        }
        selected_labels = st.multiselect(
            "セクターを選択",
            options=list(_label_map.keys()),
            default=list(_label_map.keys()),
            help="「セクター詳細」タブで比較表示するセクターを選択。",
        )
    return [_label_map[lbl] for lbl in selected_labels]


# ─────────────────────────── タブ①：全体俯瞰 ─────────────────────────────────
def _render_macro_tab(
    df_yield: pd.DataFrame,
    df_corr: pd.DataFrame | None,
) -> None:
    # 2軸チャート + NAV バー
    st.markdown("#### 📈 全体推移（価格・金利・NAV）")
    with st.expander("📖 この画面で使われている指標の読み方（初心者向け）", expanded=False):
        st.markdown("""
**🏦 分配金利回り（%）**
REITが1年間に出す「分配金」が、今の市場価格の何%にあたるかを示します。
例：価格が10万円のREITが年間4,000円の分配金を出すなら **利回り4%**。数字が大きいほど「利益を得やすい」状態です。

---
**📊 イールドスプレッド（%pt）**
REIT利回りから「日本国債10年利回り（ほぼリスクゼロの投資）」を引いた差です。
スプレッドが大きい = REIT投資の「ボーナス分」が多い = 相対的に割安。
目安：1.5%pt以上で割安、1.0%pt以下で割高と判断されることが多いです。

---
**🏢 NAV倍率（純資産価値倍率）**
REITが持っている不動産を全部売ったときの価値（NAV）と、今の市場価格の比率です。
1.0倍 = 適正価格／1.0倍未満 = 不動産の価値より安く買える「割安」状態／1.2倍超 = 割高の目安。

---
**💳 LTV（有利子負債比率）**
不動産購入のために借りているお金の割合です（ローン比率のイメージ）。
低いほど金利上昇の影響を受けにくく安全。一般に40%以下が低リスクの目安です。

---
**📉 相関係数（REIT vs 金利）**
-1.0〜+1.0の数値で、REITの価格と金利がどれくらい連動するかを示します。
- **マイナス**（特に-0.7以下）: 金利が上がるとREIT価格が下がりやすい（逆相関）
- **ゼロ付近**: ほぼ無関係に動いている
- **プラス**: 金利とREITが同じ方向に動く

---
**🔔 買いシグナル**
過去180日間の最高利回りの90%以上に今の利回りが達したとき発動。
「過去と比べて今が高利回り水準 = 相対的に割安」というサインです。
        """)
    col_main, col_nav = st.columns([3, 2])
    with col_main:
        if df_corr is not None:
            st.plotly_chart(build_dual_axis_chart(df_corr), use_container_width=True, key="macro_dual_axis")
        else:
            st.warning("相関分析データを取得できませんでした。")
    with col_nav:
        st.plotly_chart(build_nav_ratio_bar(), use_container_width=True, key="macro_nav_bar")
        st.caption(
            "NAV倍率は各セクター代表銘柄の直近決算ベース参考値。"
            "1.0 割れはNAV対比で割安の目安。"
        )

    # ローリング相関 + スプレッドバー
    st.markdown("#### 🔗 相関係数 × スプレッド（マクロ感応度）")
    col_corr, col_spread = st.columns(2)
    with col_corr:
        if df_corr is not None:
            st.plotly_chart(build_correlation_chart(df_corr), use_container_width=True, key="macro_rolling_corr")
    with col_spread:
        st.plotly_chart(build_spread_chart(df_yield), use_container_width=True, key="macro_spread")

    # 利回りチャート（フル幅）
    st.markdown("#### 💰 分配金利回り分析（東証REIT ETF 1343.T）")
    st.plotly_chart(build_yield_chart(df_yield), use_container_width=True, key="macro_yield")

    # 底打ち検知アラート
    recent_bottom = (
        bool(df_yield["bottom_signal"].iloc[-5:].any())
        if len(df_yield) >= 5
        else bool(df_yield["bottom_signal"].any())
    )
    if recent_bottom:
        last_date = df_yield[df_yield["bottom_signal"]].index[-1].strftime("%Y-%m-%d")
        st.warning(
            f"⚠️ **底打ち検知シグナル** が直近5営業日内に発生しています（{last_date}）  \n"
            f"利回り急上昇（+{BOTTOM_YIELD_SURGE}%pt 以上）"
            f"・価格下落（{BOTTOM_PRICE_DROP:.0%} 以下）"
            f"・出来高急増（20日平均の {BOTTOM_VOL_MULT} 倍以上）の3条件が成立。"
        )

    # 詳細展開セクション
    with st.expander("▲ 高利回りシグナル発動期間の詳細"):
        buy_df = df_yield[df_yield["buy_signal"]].copy()
        if buy_df.empty:
            st.info(
                f"過去1年間に高利回りシグナル（利回り≥{BUY_SIGNAL_RATIO:.0%}×180日最高値）"
                "は確認されませんでした。"
            )
        else:
            groups: list[tuple] = []
            grp_start = buy_df.index[0]
            prev_date = buy_df.index[0]
            for d in buy_df.index[1:]:
                if (d - prev_date).days > 5:
                    groups.append((grp_start, prev_date))
                    grp_start = d
                prev_date = d
            groups.append((grp_start, prev_date))
            rows = []
            for s, e in groups:
                seg = df_yield.loc[s:e]
                rows.append({
                    "開始日": s.strftime("%Y-%m-%d"),
                    "終了日": e.strftime("%Y-%m-%d"),
                    "期間（営業日）": len(seg),
                    "最高分配金利回り (%)": f"{float(seg['dist_yield'].max()):.2f}",
                    "最大スプレッド (%pt)": f"{float(seg['spread'].max()):.2f}",
                    "底打ちシグナル": "★" if bool(seg["bottom_signal"].any()) else "",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    if df_corr is not None:
        with st.expander("強い負の相関期間（相関係数 ≤ −0.7）の詳細"):
            corr_s = df_corr["rolling_corr"].dropna()
            strong = corr_s[corr_s <= STRONG_NEG_THRESHOLD]
            if strong.empty:
                st.info("過去1年間に強い負の相関期間は確認されませんでした。")
            else:
                neg_groups: list[tuple] = []
                grp_start = strong.index[0]
                prev_date = strong.index[0]
                for d in strong.index[1:]:
                    if (d - prev_date).days > 5:
                        neg_groups.append((grp_start, prev_date, strong[grp_start:prev_date].min()))
                        grp_start = d
                    prev_date = d
                neg_groups.append((grp_start, prev_date, strong[grp_start:prev_date].min()))
                neg_rows = [
                    {"開始日": s.strftime("%Y-%m-%d"), "終了日": e.strftime("%Y-%m-%d"),
                     "期間（営業日）": len(strong[s:e]), "最低相関係数": f"{mn:.3f}"}
                    for s, e, mn in neg_groups
                ]
                st.dataframe(pd.DataFrame(neg_rows), hide_index=True)

    st.caption(
        f"💡 分配金利回りは年間 ¥{ANNUAL_DIST_YEN:.0f}/口（2025年実績ベース）÷ 終値の参考値。"
        "実際の利回りは分配金変更・税制等により異なります。"
    )


# ─────────────────────────── タブ②：セクター詳細 ─────────────────────────────
def _render_individual_fundamentals(info: dict) -> None:
    """個別銘柄のファンダメンタルズ参考指標を5列で表示。"""
    f1, f2, f3, f4, f5 = st.columns(5)
    _nav = info.get("nav_ratio")
    _ltv = info.get("ltv")
    _noi = info.get("noi_yield")
    _urg = info.get("unrealized_gain_pct")
    f1.metric("NAV 倍率", f"{_nav:.2f}x" if _nav is not None else "—",
              help="純資産価値比。1倍以下は割安の目安。")
    f2.metric("LTV", f"{_ltv:.1f}%" if _ltv is not None else "—",
              help="有利子負債比率。低いほど金利上昇への耐性が高い。")
    f3.metric("NOI 利回り", f"{_noi:.1f}%" if _noi is not None else "—",
              help="純賃料収入 / 物件取得価格。")
    f4.metric("含み益割合", f"{_urg:.1f}%" if _urg is not None else "—",
              help="物件評価額の帳簿価額対比含み益割合（参考値）。")
    dist_g = info.get("dist_growth")
    delta_label = (
        "▲ 増配" if dist_g and dist_g > 0
        else "▼ 減配" if dist_g and dist_g < 0
        else "変化なし"
    )
    f5.metric(
        "分配金増減率",
        f"{dist_g:+.1f}%" if dist_g is not None else "—",
        delta=delta_label, delta_color="normal",
        help="直近分配金の前期比増減率（参考値）。",
    )
    st.caption("⚠️ 上記5指標はすべて直近決算レポートに基づく参考値です。投資判断はご自身でご確認ください。")


def _render_sector_tab(
    selected_sectors: list[str],
    bond: pd.Series,
    bond_last: float,
    universe_records: list[dict],
    overall_yield: float,
) -> None:
    if not selected_sectors:
        st.info("サイドバーの「分析対象セクター」で1つ以上のセクターを選択してください。")
        return

    # ── セクター評価カード（4セクター一覧）────────────────────
    st.markdown("#### 🏢 セクター別 総合評価")
    with st.expander("📖 指標の見方（大学生向け）", expanded=False):
        st.markdown("""
**分配金利回り**: 年間にもらえる分配金 ÷ 市場価格 × 100。高いほど収益性が良い。
**NAV倍率**: 市場価格 ÷ 不動産の純資産。1倍未満は「実態より安く買える」割安サイン。
**LTV**: 借金の割合。低いほど金利上昇に強い。40%以下が優良水準。
**稼働率**: テナントが埋まっている割合。高いほど安定収益が見込める。
**NOI利回り**: 物件から生む純収益 ÷ 物件価格。高いほど運用効率が良い。
**評価**: NAV・LTV・稼働率・スプレッドの4指標で総合判断（🟢強気 / 🟡中立 / 🟠慎重）。
        """)

    sec_cols = st.columns(len(SECTOR_ANALYSIS))
    for si, sec_info in enumerate(SECTOR_ANALYSIS):
        grade, grade_color = _evaluate_sector_grade(sec_info, None)
        nav = sec_info.get("nav_ratio", "—")
        ltv = sec_info.get("ltv", "—")
        occ = sec_info.get("occupancy", "—")
        noi = sec_info.get("noi_yield", "—")
        sec_color = _SECTOR_COLOR_MAP.get(sec_info["sector"], "#9E9E9E")
        nav_str = f"{nav:.2f}x" if isinstance(nav, (int, float)) else str(nav)
        ltv_str = f"{ltv:.1f}%" if isinstance(ltv, (int, float)) else str(ltv)
        occ_str = f"{occ:.1f}%" if isinstance(occ, (int, float)) else str(occ)
        noi_str = f"{noi:.1f}%" if isinstance(noi, (int, float)) else str(noi)
        with sec_cols[si]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#0e1117 0%,#1a1f2e 100%);
                            border:2px solid {sec_color};border-radius:10px;
                            padding:14px 12px;margin-bottom:8px;">
                    <div style="font-size:0.7rem;color:{sec_color};font-weight:700;
                                letter-spacing:0.06em;text-transform:uppercase;">{sec_info['sector']}</div>
                    <div style="font-size:0.78rem;color:#ccc;margin:4px 0 8px;font-weight:600;">{sec_info['name']}</div>
                    <div style="font-size:1.0rem;font-weight:800;color:{grade_color};margin-bottom:8px;">{grade}</div>
                    <div style="border-top:1px solid {sec_color}44;padding-top:8px;
                                font-size:0.68rem;color:#bbb;line-height:2.0;">
                        🏦 NAV倍率: <b style='color:#eee'>{nav_str}</b><br>
                        💳 LTV: <b style='color:#eee'>{ltv_str}</b><br>
                        🏢 稼働率: <b style='color:#eee'>{occ_str}</b><br>
                        📈 NOI利回り: <b style='color:#eee'>{noi_str}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("背景・トレンド"):
                st.caption(sec_info.get("trend_reason", ""))

    st.divider()

    # ── セクター比較チャート ─────────────────────────────────
    st.markdown("#### 📊 セクター比較 — 平均利回り・NAV 倍率")
    col_yield, col_nav = st.columns([3, 2])
    with col_yield:
        if universe_records and any(r.get("current_yield") for r in universe_records):
            st.plotly_chart(
                build_sector_comparison_chart(universe_records, overall_yield),
                use_container_width=True,
                key="sector_comparison",
            )
        else:
            st.warning("セクター利回りデータを取得できませんでした。")
    with col_nav:
        st.plotly_chart(build_nav_ratio_bar(), use_container_width=True, key="sector_nav_bar")

    # ── セクター代表銘柄の分析チャート ──────────────────────
    st.markdown("#### 🏢 選択セクター — 利回り・相関比較")
    with st.spinner("セクター詳細データ取得中..."):
        sector_close = fetch_sector_close()

    if sector_close is None:
        st.error("セクターデータの取得に失敗しました。ネットワーク環境を確認してください。")
        return

    sector_data = compute_sector_analytics(sector_close, bond)
    sel_data    = {t: sector_data[t] for t in selected_sectors if t in sector_data}

    if not sel_data:
        st.warning("選択したセクターのデータを取得できませんでした。")
        return

    col_bar, col_corr = st.columns([3, 2])
    with col_bar:
        st.plotly_chart(build_sector_yield_bar(sel_data, selected_sectors, bond_last),
                        use_container_width=True, key="sector_yield_bar")
    with col_corr:
        st.plotly_chart(build_sector_corr_chart(sel_data, selected_sectors),
                        use_container_width=True, key="sector_corr_chart")

    # セクターランキングテーブル
    st.markdown("##### 📋 セクターランキング（代表指数銘柄）")
    ranking_df = build_sector_ranking_table(sel_data)
    st.dataframe(ranking_df, hide_index=True, use_container_width=True)
    st.caption(
        "💡 NAV倍率・LTV・NOI利回り・稼働率は直近決算レポートに基づく参考値。"
        "配当スコアは過去1年スプレッドのパーセンタイル順位（高いほど割安）。"
    )

    # ── 全サブ銘柄 評価カード ────────────────────────────────
    st.divider()
    st.markdown("#### 📋 構成銘柄 一覧評価")
    st.caption("各セクターを構成する全銘柄のファンダメンタルズ参考値を一覧表示します。")

    with st.expander("📖 各指標の意味（大学生向け）", expanded=False):
        st.markdown("""
**分配金（円/口）**: 1口あたり年間にもらえる金額。銘柄によって金額が大きく異なります。
**NAV倍率**: 不動産の純資産価値との比率。低いほど割安。1.0未満 = 純資産より安く買える。
**LTV**: 借入比率。低いほど財務が健全で、金利上昇に耐えられる。
**含み益割合**: 所有する不動産の帳簿価格に対する含み益の割合。高いほど資産価値が上昇している。
**分配金増減率**: 前期と比べて分配金が増えたか減ったか（+が増配、-が減配）。
        """)

    uni_map = {r["ticker"]: r for r in universe_records}
    for sec_info in SECTOR_ANALYSIS:
        if sec_info["ticker"] not in selected_sectors:
            continue
        sec_color = _SECTOR_COLOR_MAP.get(sec_info["sector"], "#9E9E9E")
        st.markdown(
            f"<span style='color:{sec_color};font-weight:700;font-size:0.9rem;'>"
            f"● {sec_info['sector']}</span>",
            unsafe_allow_html=True,
        )
        sub_cols = st.columns(len(sec_info["sub_tickers"]))
        for ci, sub in enumerate(sec_info["sub_tickers"]):
            live = uni_map.get(sub["ticker"], {})
            cur_price = live.get("current_price")
            cur_yield = live.get("current_yield")
            nav = sub.get("nav_ratio", "—")
            ltv = sub.get("ltv", "—")
            urg = sub.get("unrealized_gain_pct", "—")
            dg  = sub.get("dist_growth")
            dg_str = f"{dg:+.1f}%" if dg is not None else "—"
            dg_color = "#4CAF50" if dg and dg > 0 else ("#EF5350" if dg and dg < 0 else "#aaa")
            price_str = f"¥{cur_price:,}" if cur_price else "—"
            yield_str = f"{cur_yield:.2f}%" if cur_yield else "—"
            nav_str = f"{nav:.2f}x" if isinstance(nav, (int, float)) else str(nav)
            ltv_str = f"{ltv:.1f}%" if isinstance(ltv, (int, float)) else str(ltv)
            urg_str = f"{urg:.1f}%" if isinstance(urg, (int, float)) else str(urg)

            with sub_cols[ci]:
                st.markdown(
                    f"""
                    <div style="background:#0e1117;border:1px solid {sec_color}66;
                                border-radius:8px;padding:12px 10px;margin-bottom:6px;">
                        <div style="font-size:0.72rem;color:{sec_color};font-weight:700;">{sub['ticker']}</div>
                        <div style="font-size:0.8rem;color:#ddd;font-weight:600;margin:2px 0 6px;
                                    line-height:1.25;">{sub['name']}</div>
                        <div style="font-size:0.68rem;color:#aaa;line-height:1.9;">
                            💰 現在価格: <b style='color:#eee'>{price_str}</b><br>
                            📊 分配金利回り: <b style='color:#80CBC4'>{yield_str}</b><br>
                            🏦 NAV倍率: <b style='color:#eee'>{nav_str}</b><br>
                            💳 LTV: <b style='color:#eee'>{ltv_str}</b><br>
                            📈 含み益: <b style='color:#eee'>{urg_str}</b><br>
                            🔄 分配金増減: <b style='color:{dg_color}'>{dg_str}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.write("")

    # ── 個別銘柄詳細分析 ────────────────────────────────────
    st.divider()
    st.markdown("### 🔍 個別銘柄 詳細分析")

    sector_map_all = {s["ticker"]: s for s in SECTOR_ANALYSIS}
    all_sub: list[dict] = []
    for t in selected_sectors:
        if t in sector_map_all:
            all_sub.extend(sector_map_all[t]["sub_tickers"])

    sub_options = {f"{s['name']}  ({s['ticker']})": s for s in all_sub}
    chosen_label = st.selectbox(
        "分析する個別銘柄を選択",
        options=list(sub_options.keys()),
        help="セクターランキング表の「代表個別銘柄」から選択できます。",
    )
    chosen = sub_options[chosen_label]

    # ファンダメンタルズ参考指標
    _render_individual_fundamentals(chosen)

    # 価格・利回りデータ取得
    with st.spinner(f"{chosen['name']} データ取得中..."):
        ind_ohlcv = fetch_ticker_ohlcv(chosen["ticker"])

    if ind_ohlcv is None or len(ind_ohlcv) < 30:
        st.warning(
            f"`{chosen['ticker']}` のデータを取得できませんでした。"
            "上場廃止・取引停止の可能性があります。"
        )
        return

    ind_yield, ind_corr = compute_individual_analytics(
        ind_ohlcv, bond, annual_dist=chosen["annual_dist"]
    )

    st.caption(
        f"**{chosen['name']}** ({chosen['ticker']}) ／ "
        f"データ期間: {ind_yield.index[0].strftime('%Y-%m-%d')} 〜 "
        f"{ind_yield.index[-1].strftime('%Y-%m-%d')} ／ "
        f"年間分配金（参考）: ¥{chosen['annual_dist']:,}/口"
    )

    # チャート 2 列レイアウト
    c_left, c_right = st.columns([3, 2])
    with c_left:
        st.plotly_chart(build_yield_chart(ind_yield), use_container_width=True, key="ind_yield")
    with c_right:
        st.plotly_chart(
            build_correlation_chart(ind_corr),
            use_container_width=True,
            key="ind_corr",
        )
    st.plotly_chart(build_spread_chart(ind_yield), use_container_width=True, key="ind_spread")
    st.plotly_chart(
        build_dual_axis_chart(ind_corr, reit_label=f"{chosen['name']} ({chosen['ticker']})"),
        use_container_width=True,
        key="ind_dual_axis",
    )

    # 個別 KPI
    ind_div_score  = compute_dividend_score(ind_yield)
    ind_spread_cur = float(ind_yield["spread"].iloc[-1])
    ind_spread_avg = float(ind_yield["spread"].mean())
    ind_yield_cur  = float(ind_yield["dist_yield"].iloc[-1])
    ind_buy_sig    = bool(ind_yield["buy_signal"].iloc[-1])
    ind_corr_s     = ind_corr["rolling_corr"].dropna()
    ind_corr_val   = float(ind_corr_s.iloc[-1]) if len(ind_corr_s) >= 1 else float("nan")

    st.markdown("##### 📊 個別銘柄 KPI")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("分配金利回り（概算）", f"{ind_yield_cur:.2f}%",
              help="年間分配金（参考値）÷ 終値 × 100")
    k2.metric("スプレッド", f"{ind_spread_cur:.2f}%pt",
              delta=f"1年平均比 {ind_spread_cur - ind_spread_avg:+.2f}pt")
    k3.metric("配当スコア",
              f"{ind_div_score}/100" if ind_div_score >= 0 else "—",
              help="過去1年スプレッドのパーセンタイル順位")
    k4.metric("20日相関係数",
              f"{ind_corr_val:.3f}" if not np.isnan(ind_corr_val) else "—")

    if ind_buy_sig:
        st.success(
            f"▲ **高利回りシグナル発動中** — "
            f"利回りが過去{BUY_SIGNAL_WINDOW}日最高値の{BUY_SIGNAL_RATIO:.0%}以上に達しています。"
        )


# ─────────────────────────── タブ③：Top5 Pick ────────────────────────────────
def _render_top5_tab(universe_records: list[dict]) -> None:
    st.markdown("### ⭐ 購入対象 Top5 セレクション")
    st.markdown("以下のスコアリングアルゴリズムで全12銘柄を採点し、上位5銘柄を表示します。")
    with st.expander("📖 スコアリングの仕組みと指標の読み方（初心者向け）", expanded=False):
        st.markdown("""
### 採点方法（合計100点満点）

#### ① イールドスプレッドスコア（最大40点）
**スプレッド** = REIT分配金利回り − 日本国債10年利回り

国債はほぼリスクゼロの投資です。REITの利回りが国債より大きく上回るほど「お得」です。
過去1年間のスプレッドと比べて、現在が上位何%にいるかを0〜40点で採点します。

> 例：過去1年で今のスプレッドが上位10%なら → 40 × 0.90 ≈ **36点**

---

#### ② NAV倍率スコア（最大30点）
**NAV倍率** = 市場価格 ÷ 不動産の純資産価値

NAVが1.0倍を下回ると「実際の資産価値より安く買える」割安状態です。
NAV 0.95以下 → 30点満点、NAV 1.15以上 → 0点というスケールで採点します。

> 例：NAV 1.04 → (1.15 - 1.04) / 0.20 × 30 ≈ **17点**

---

#### ③ LTVスコア（最大30点）
**LTV（Loan to Value）** = 借入金 ÷ 物件価格

金利が上がると借入コストが増え、分配金が減るリスクがあります。
LTVが低いほど金利上昇に強く、安全度が高い。LTV 35%以下 → 30点、50%以上 → 0点。

> 例：LTV 42.1% → (50.0 - 42.1) / 15.0 × 30 ≈ **16点**

---
        """)
    st.markdown(
        "| 軸 | 指標 | 最大 | 評価基準 |\n"
        "|---|---|---|---|\n"
        "| ① | イールドスプレッド | 40pt | 1年分位数が高いほど割安 |\n"
        "| ② | NAV 倍率 | 30pt | 低いほど純資産対比で割安 |\n"
        "| ③ | LTV | 30pt | 低いほど金利上昇への耐性が高い |\n"
    )

    no_data = not universe_records or all(
        r.get("current_price") is None for r in universe_records
    )
    if no_data:
        st.warning(
            "スコアリングに必要な価格データを取得できませんでした。"
            "ネットワーク環境を確認してください。"
        )
        return

    scores_df = compute_top5_scores(universe_records)
    if scores_df.empty:
        st.warning("スコアリングできる銘柄データが不足しています。")
        return

    # Top5 を home.py で参照できるよう保存
    st.session_state["reit_top5"] = scores_df.head(5).to_dict("records")

    # Top5 カード
    render_top5_cards(scores_df)

    st.divider()

    # 全銘柄スコアリングテーブル
    st.markdown("#### 📋 全銘柄 スコアリング詳細")
    st.dataframe(scores_df, hide_index=True, use_container_width=True)

    # 全銘柄スコア視覚化
    st.markdown("#### 📊 全銘柄スコア比較")
    st.caption("棒グラフで全12銘柄のスコアを比較できます。スコアが高いほど「今が買いやすい水準」です。")
    _colors_bar = [
        _SECTOR_COLOR_MAP.get(row["セクター"], "#9E9E9E")
        for _, row in scores_df.iterrows()
    ]
    _fig_all = go.Figure(go.Bar(
        x=scores_df["銘柄名"],
        y=scores_df["総合スコア"],
        marker=dict(color=_colors_bar, opacity=0.85),
        text=scores_df["総合スコア"],
        textposition="outside",
        hovertemplate="%{x}<br>総合スコア: %{y}点<extra></extra>",
    ))
    _fig_all.add_hline(y=60, line_dash="dash", line_color="#FFC107", line_width=1.5,
                       annotation_text="60点（目安）", annotation_position="right",
                       annotation_font=dict(size=10, color="#FFC107"))
    _fig_all.update_layout(
        height=320, margin=dict(l=10, r=100, t=20, b=80),
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font=dict(color="#fafafa"),
        yaxis=dict(range=[0, 105], gridcolor="#1e2130"),
        xaxis=dict(tickangle=-30, gridcolor="#1e2130"),
        showlegend=False,
    )
    st.plotly_chart(_fig_all, use_container_width=True, key="all_stocks_score_bar")

    st.caption(
        "⚠️ NAV倍率・LTVは直近決算レポートに基づく参考値です。"
        "スプレッドスコアは過去1年間の価格データから計算した動的指標です。"
        "本ツールの情報は投資助言ではありません。投資判断は必ずご自身でお行いください。"
    )


# ─────────────────────────── メインレンダリング ───────────────────────────────
def render() -> None:
    hero_header(
        "REITアナリティクス",
        "全体俯瞰・セクター詳細・Top5 スコアリングをワンストップで確認",
        "📈",
    )

    # ── 共通データ取得 ────────────────────────────────────────
    with st.spinner("データ取得中..."):
        ohlcv            = fetch_reit_ohlcv()
        bond             = fetch_jgb_yield()
        df_corr, bond_label = load_data()
        uni_close        = fetch_universe_close()

    if ohlcv is None or bond is None:
        st.error(
            "データの取得に失敗しました。\n\n"
            f"- REIT ETF : `{REIT_TICKER}` (yfinance)\n"
            f"- 国債利回り: 財務省 CSV (`jgbcm_all.csv`)\n\n"
            "ネットワーク環境を確認してください。"
        )
        return

    df_yield = compute_yield_analytics(ohlcv, bond)
    selected_sectors = render_sidebar(df_yield)

    # ── ユニバース分析（Tab2・Tab3 共用） ──────────────────────
    uni_records = compute_universe_analytics(uni_close, bond)

    # ── KPI 先行計算 ───────────────────────────────────────────
    dist_yield_cur  = float(df_yield["dist_yield"].iloc[-1])
    dist_yield_prev = float(df_yield["dist_yield"].iloc[-2]) if len(df_yield) >= 2 else float("nan")
    yield_delta     = dist_yield_cur - dist_yield_prev if not np.isnan(dist_yield_prev) else float("nan")

    spread_cur   = float(df_yield["spread"].iloc[-1])
    spread_prev  = float(df_yield["spread"].iloc[-2]) if len(df_yield) >= 2 else float("nan")
    spread_delta = spread_cur - spread_prev if not np.isnan(spread_prev) else float("nan")
    spread_avg   = float(df_yield["spread"].mean())

    div_score   = compute_dividend_score(df_yield)
    buy_sig_now = bool(df_yield["buy_signal"].iloc[-1]) if not df_yield.empty else False

    corr_val = corr_delta = bond_last = bond_chg = reit_ret = float("nan")
    if df_corr is not None:
        m          = get_summary_metrics(df_corr)
        corr_val   = m["corr_current"]
        corr_delta = m["corr_delta"]
        bond_last  = m["bond_last"]
        bond_chg   = m["bond_chg"]
        reit_ret   = m["reit_ret"]

    # ── データ期間キャプション ────────────────────────────────
    start_date = df_yield.index[0].strftime("%Y-%m-%d")
    end_date   = df_yield.index[-1].strftime("%Y-%m-%d")
    st.caption(
        f"データ期間: {start_date} 〜 {end_date}"
        f"　|　REIT: {REIT_TICKER} / 国債: {bond_label}"
        f"　|　分配金（参考）: 年間 ¥{ANNUAL_DIST_YEN:.0f}/口"
    )

    # ══════════════════════════════════════════════════════════
    # 総合判定カード（タブ外・常時表示）
    # ══════════════════════════════════════════════════════════
    verdict, action = compute_overall_verdict(
        div_score   = div_score,
        corr_val    = corr_val   if not np.isnan(corr_val)   else 0.0,
        corr_delta  = corr_delta if not np.isnan(corr_delta) else 0.0,
        bond_chg_1d = bond_chg   if not np.isnan(bond_chg)   else 0.0,
        buy_sig     = buy_sig_now,
    )
    render_verdict_card(verdict, action)

    # ── KPI グリッド（3カテゴリー）────────────────────────────
    if div_score >= 70:
        score_str, score_eval = f"{div_score}/100", "（割安）"
    elif div_score >= 40:
        score_str, score_eval = f"{div_score}/100", ""
    elif div_score >= 0:
        score_str, score_eval = f"{div_score}/100", "（割高）"
    else:
        score_str, score_eval = "—", ""

    buy_sig_str = "🟢 発動中" if buy_sig_now else "⬜ 待機中"
    if not np.isnan(corr_val):
        corr_icon = (
            "⚠️" if corr_val <= -0.7 else
            "↘"  if corr_val <= -0.3 else
            "↔"  if corr_val <=  0.3 else "↗"
        )
        corr_state_short = (
            "強い負の相関" if corr_val <= -0.7 else
            "負の相関"     if corr_val <= -0.3 else
            "無相関"       if corr_val <=  0.3 else "正の相関"
        )
    else:
        corr_icon, corr_state_short = "", "—"

    cat_a, cat_b, cat_c = st.columns(3)
    with cat_a:
        st.markdown(
            "<p style='font-size:0.75rem;font-weight:700;color:#80CBC4;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "border-bottom:1px solid #1e4040;padding-bottom:4px;margin-bottom:10px;'>"
            "📊 A.&nbsp;利回りポテンシャル（収益性）</p>",
            unsafe_allow_html=True,
        )
        st.metric(
            "分配金利回り（概算）", f"{dist_yield_cur:.2f}%",
            delta=f"{yield_delta:+.2f}%pt" if not np.isnan(yield_delta) else None,
            help=f"年間分配金（¥{ANNUAL_DIST_YEN:.0f}/口）を現在の市場価格で割った値です。例：価格が2,000円で年間分配金が80円なら利回り4%。数値が高いほど投資の「旨み」が大きい。",
        )
        st.metric(
            f"配当スコア　{score_eval}", score_str,
            delta=f"1年平均スプレッド比 {spread_cur - spread_avg:+.2f}pt",
            help="過去1年間のイールドスプレッドのパーセンタイル順位（0〜100点）。70点以上は「過去と比べて今が割安」の目安。スプレッドとはREIT利回りと国債利回りの差のことです。",
        )
    with cat_b:
        st.markdown(
            "<p style='font-size:0.75rem;font-weight:700;color:#90CAF9;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "border-bottom:1px solid #1a2a4a;padding-bottom:4px;margin-bottom:10px;'>"
            "🛡️ B.&nbsp;金利耐性（安全性）</p>",
            unsafe_allow_html=True,
        )
        st.metric(
            "イールドスプレッド", f"{spread_cur:.2f}%pt",
            delta=f"1年平均比 {spread_cur - spread_avg:+.2f}pt" if not np.isnan(spread_avg) else None,
            help="REIT分配金利回りから日本国債10年利回りを引いた差です。スプレッドが広いほど「リスクを取る見返り（プレミアム）」が大きく割安。1.5%pt以上で割安、1.0%pt以下で割高の目安。",
        )
        bond_str = f"{bond_last:.3f}%" if not np.isnan(bond_last) else "—"
        chg_str  = f"{bond_chg:+.3f}pt" if not np.isnan(bond_chg) else None
        st.metric("10年金利（直近）", bond_str, delta=chg_str,
                  help="日本国債10年利回り（財務省公表）。ほぼリスクゼロの投資基準となる金利です。上昇するとREITのスプレッドが縮小し、価格下落圧力になります。")
    with cat_c:
        st.markdown(
            "<p style='font-size:0.75rem;font-weight:700;color:#CE93D8;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "border-bottom:1px solid #2a1a4a;padding-bottom:4px;margin-bottom:10px;'>"
            "📡 C.&nbsp;市場感応度（需給）</p>",
            unsafe_allow_html=True,
        )
        corr_str_disp  = f"{corr_val:.3f} {corr_icon}" if not np.isnan(corr_val) else "—"
        corr_delta_str = f"{corr_delta:+.3f}" if not np.isnan(corr_delta) else None
        st.metric(
            f"20日相関係数　{corr_state_short}", corr_str_disp, delta=corr_delta_str,
            help="-1.0〜+1.0の数値でREIT価格と金利の連動度を示します。マイナス（特に-0.7以下）は「金利上昇→REIT下落」の逆相関が強い状態。ゼロ付近はほぼ無関係、プラスは同じ方向に動く。",
        )
        reit_ret_str = f"{reit_ret:+.2%}" if not np.isnan(reit_ret) else "—"
        st.metric(
            "高利回りシグナル", buy_sig_str,
            delta=reit_ret_str + " 前日騰落" if not np.isnan(reit_ret) else None,
            delta_color="normal",
            help=f"過去{BUY_SIGNAL_WINDOW}日間の最高利回りの{BUY_SIGNAL_RATIO:.0%}以上に現在の利回りが達したとき発動。「過去と比べて今が高利回り水準 = 相対的に割安」というサインです。",
        )

    st.divider()

    # ══════════════════════════════════════════════════════════
    # メインタブ
    # ══════════════════════════════════════════════════════════
    tab_macro, tab_sector, tab_top5 = st.tabs([
        "📊 全体俯瞰", "🏢 セクター詳細", "⭐ Top5 Pick"
    ])

    with tab_macro:
        _render_macro_tab(df_yield, df_corr)

    with tab_sector:
        _render_sector_tab(
            selected_sectors = selected_sectors,
            bond             = bond,
            bond_last        = bond_last,
            universe_records = uni_records,
            overall_yield    = dist_yield_cur,
        )

    with tab_top5:
        _render_top5_tab(uni_records)


render()
