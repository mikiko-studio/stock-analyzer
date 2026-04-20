"""
utils/reit_data.py
J-REIT 分析用の定数・データ取得・計算関数。
REITアナリティクスページと screener_runner の両方から利用する。
"""

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from utils.yf_session import YF_SESSION

# ─────────────────────────── 定数 ────────────────────────────────────────────
MOF_ALL_CSV    = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_RECENT_CSV = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"

SECTOR_ANALYSIS: list[dict] = [
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
            {"ticker": "8951.T", "name": "日本ビルファンド",
             "annual_dist": 4949,  "ltv": 42.1, "nav_ratio": 1.04,
             "noi_yield": 4.2, "unrealized_gain_pct": 35.2, "dist_growth":  0.5},
            {"ticker": "8952.T", "name": "ジャパンリアルエステイト",
             "annual_dist": 18000, "ltv": 43.5, "nav_ratio": 1.03,
             "noi_yield": 3.9, "unrealized_gain_pct": 32.1, "dist_growth":  1.2},
            {"ticker": "3234.T", "name": "森ヒルズリート",
             "annual_dist": 2700,  "ltv": 44.2, "nav_ratio": 0.98,
             "noi_yield": 4.0, "unrealized_gain_pct": 18.5, "dist_growth": -0.8},
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
            {"ticker": "3281.T", "name": "日本プロロジスリート",
             "annual_dist": 10416, "ltv": 38.5, "nav_ratio": 1.14,
             "noi_yield": 4.5, "unrealized_gain_pct": 52.3, "dist_growth":  3.1},
            {"ticker": "3249.T", "name": "産業ファンド投資法人",
             "annual_dist":  5400, "ltv": 40.1, "nav_ratio": 1.08,
             "noi_yield": 4.3, "unrealized_gain_pct": 41.8, "dist_growth":  2.5},
            {"ticker": "3471.T", "name": "三井不動産ロジスティクスパーク",
             "annual_dist":  6500, "ltv": 39.8, "nav_ratio": 1.10,
             "noi_yield": 4.4, "unrealized_gain_pct": 45.2, "dist_growth":  2.0},
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
            {"ticker": "3226.T", "name": "日本アコモデーション",
             "annual_dist": 6996, "ltv": 45.3, "nav_ratio": 1.09,
             "noi_yield": 4.1, "unrealized_gain_pct": 43.5, "dist_growth":  1.5},
            {"ticker": "3269.T", "name": "アドバンス・レジデンス",
             "annual_dist": 9000, "ltv": 44.8, "nav_ratio": 1.07,
             "noi_yield": 4.0, "unrealized_gain_pct": 38.2, "dist_growth":  1.0},
            {"ticker": "8979.T", "name": "スターツプロシード",
             "annual_dist": 3800, "ltv": 46.5, "nav_ratio": 0.95,
             "noi_yield": 3.8, "unrealized_gain_pct": 22.1, "dist_growth": -1.2},
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
            {"ticker": "8985.T", "name": "ジャパン・ホテル・リート",
             "annual_dist": 5061, "ltv": 41.5, "nav_ratio": 1.02,
             "noi_yield": 5.1, "unrealized_gain_pct": 28.5, "dist_growth":  8.5},
            {"ticker": "3287.T", "name": "星野リゾートREIT",
             "annual_dist": 4000, "ltv": 43.2, "nav_ratio": 0.99,
             "noi_yield": 4.8, "unrealized_gain_pct": 21.3, "dist_growth":  5.2},
            {"ticker": "8977.T", "name": "阪急阪神リート",
             "annual_dist": 3000, "ltv": 42.8, "nav_ratio": 0.97,
             "noi_yield": 4.5, "unrealized_gain_pct": 19.8, "dist_growth":  3.1},
        ],
    },
]

REIT_UNIVERSE: list[dict] = [
    {**sub, "sector": s["sector"]}
    for s in SECTOR_ANALYSIS
    for sub in s["sub_tickers"]
]

# ─────────────────────────── JGB 取得 ─────────────────────────────────────────

def _parse_jp_era_date(s: str) -> pd.Timestamp:
    era_offset = {"S": 1925, "H": 1988, "R": 2018}
    era   = s[0]
    parts = s[1:].split(".")
    return pd.Timestamp(era_offset[era] + int(parts[0]), int(parts[1]), int(parts[2]))


def _read_mof_csv(url: str) -> list[tuple[pd.Timestamp, float]]:
    r = YF_SESSION.get(url, timeout=20)
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


# ─────────────────────────── 価格取得 ─────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_universe_close(period: str = "1y") -> pd.DataFrame | None:
    """全ユニバース12銘柄の終値を一括取得。"""
    tickers = list({r["ticker"] for r in REIT_UNIVERSE})
    try:
        raw = yf.download(tickers, period=period, progress=False, auto_adjust=True, session=YF_SESSION)
        if raw.empty:
            return None
        close = raw["Close"].copy() if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].copy()
        if not isinstance(raw.columns, pd.MultiIndex):
            close.columns = tickers
        idx = pd.to_datetime(close.index)
        close.index = idx.tz_convert(None) if idx.tz is not None else idx
        return close.dropna(how="all")
    except Exception:
        return None


# ─────────────────────────── スコアリング計算 ─────────────────────────────────

def compute_universe_analytics(
    close_df: pd.DataFrame | None, bond: pd.Series
) -> list[dict]:
    """全ユニバース銘柄の現在指標（分配金利回り・スプレッド等）を計算。"""
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

        cur_price = float(s.iloc[-1])
        cur_yield = info["annual_dist"] / cur_price * 100

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
      ① スプレッドスコア (40pt): 1年スプレッドの分位数
      ② NAV スコア    (30pt): NAV 倍率が低いほど高得点
      ③ LTV スコア    (30pt): LTV が低いほど高得点（金利耐性）
    """
    rows = []
    for r in universe_records:
        if r.get("current_price") is None:
            continue
        sp           = r.get("spread_pct")
        score_spread = max(0, min(40, round(sp * 0.40))) if sp is not None else 0
        nav          = r.get("nav_ratio", 1.10)
        score_nav    = max(0, min(30, round((1.15 - nav) / 0.20 * 30)))
        ltv          = r.get("ltv", 45.0)
        score_ltv    = max(0, min(30, round((50.0 - ltv) / 15.0 * 30)))
        total        = score_spread + score_nav + score_ltv

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


def run_reit_top5() -> list[dict]:
    """Top5 スコアリングを実行して結果を返す（home.py の更新ボタン用）。"""
    bond = fetch_jgb_yield()
    if bond is None:
        return []
    uni_close = fetch_universe_close()
    uni_records = compute_universe_analytics(uni_close, bond)
    scores_df = compute_top5_scores(uni_records)
    if scores_df.empty:
        return []
    return scores_df.head(5).to_dict("records")
