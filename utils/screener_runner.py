"""
utils/screener_runner.py
バフェット・シグナル・高配当スクリーナーのコアロジックを集約。
各スクリーナーページと Top Page の「全て更新」ボタンの両方から利用する。
"""

import re
from typing import Callable

import numpy as np
import pandas as pd

from utils.constants import (
    JP_DIVIDEND_STOCKS_BY_SECTOR,
    JP_STOCKS,
    SECTOR_PE_JP,
    SECTOR_PE_US,
    WATCH_LIST_JP,
    WATCH_LIST_US,
)
from utils.data_fetcher import fetch_with_cache_flag

# ─────────────────────────── バフェット分析 ───────────────────────────────────

DISCOUNT_RATE   = 0.09
TERMINAL_GROWTH = 0.03
DCF_YEARS       = 10
HURDLE_RATE     = 0.10

GROWTH_CAPS: dict[str, float] = {
    "Technology": 0.20, "Communication Services": 0.15,
    "Consumer Discretionary": 0.15, "Consumer Staples": 0.10,
    "Healthcare": 0.12, "Financials": 0.10, "Industrials": 0.12,
    "Energy": 0.08, "Materials": 0.08, "Utilities": 0.07,
    "Real Estate": 0.08,
    "電気機器": 0.15, "情報通信": 0.15, "医薬品": 0.12,
    "輸送用機器": 0.08, "銀行業": 0.07, "小売業": 0.10,
    "機械": 0.10, "化学": 0.08, "サービス業": 0.12,
}


def calc_pe_score(pe, sector, sector_pe_map):
    if pe is None or np.isnan(pe):
        return 0, None
    benchmark = sector_pe_map.get(sector, 20)
    ratio = pe / benchmark
    if ratio < 0.6:
        return 2, ratio
    elif ratio < 0.8:
        return 1, ratio
    elif ratio < 1.0:
        return 0, ratio
    elif ratio < 1.3:
        return -1, ratio
    else:
        return -2, ratio


def calc_dcf(eps, growth_rate, discount_rate=DISCOUNT_RATE,
             terminal_growth=TERMINAL_GROWTH, years=DCF_YEARS):
    if eps is None or eps <= 0:
        return None
    pv = 0
    for y in range(1, years + 1):
        projected_eps = eps * (1 + growth_rate) ** y
        pv += projected_eps / (1 + discount_rate) ** y
    terminal_eps = eps * (1 + growth_rate) ** years
    terminal_value = (terminal_eps * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    pv += terminal_value / (1 + discount_rate) ** years
    return pv


def calc_dcf_score(price, intrinsic_value):
    if intrinsic_value is None or price is None or intrinsic_value <= 0:
        return 0, None
    margin = (intrinsic_value - price) / intrinsic_value
    if margin > 0.30:
        return 2, margin
    elif margin > 0.10:
        return 1, margin
    elif margin > -0.10:
        return 0, margin
    elif margin > -0.30:
        return -1, margin
    else:
        return -2, margin


def calc_gdm(eps, growth_rate, bond_yield=0.045):
    if eps is None or eps <= 0:
        return None
    if bond_yield <= 0:
        bond_yield = 0.045
    return eps * (8.5 + 2 * growth_rate * 100) * 4.4 / (bond_yield * 100)


def calc_gdm_score(price, gdm_value):
    if gdm_value is None or price is None or gdm_value <= 0:
        return 0, None
    margin = (gdm_value - price) / gdm_value
    if margin > 0.30:
        return 2, margin
    elif margin > 0.10:
        return 1, margin
    elif margin > -0.10:
        return 0, margin
    elif margin > -0.30:
        return -1, margin
    else:
        return -2, margin


def calc_cagr(price, eps, div_yield, growth_rate, years=10):
    if price is None or eps is None or price <= 0:
        return None
    future_price = price * (1 + growth_rate) ** years
    total_divs = price * div_yield * years if div_yield else 0
    try:
        return ((future_price + total_divs) / price) ** (1 / years) - 1
    except Exception:
        return None


def analyze_stock(stock_info, data, sector_pe_jp=SECTOR_PE_JP, sector_pe_us=SECTOR_PE_US):
    """3手法（P/E・DCF・GDM）でスコアリングする。"""
    if data is None:
        return None

    symbol = stock_info["symbol"]
    is_jp_stock = symbol.endswith(".T")
    sector_pe_map = sector_pe_jp if is_jp_stock else sector_pe_us

    sector        = stock_info.get("sector", data.get("sector", "Unknown"))
    price         = data.get("price")
    eps           = data.get("trailingEps") or data.get("forwardEps")
    pe            = data.get("trailingPE")
    div_yield     = data.get("dividendYield") or 0
    revenue_growth   = data.get("revenueGrowth") or 0
    earnings_growth  = data.get("earningsGrowth") or 0

    raw_growth = max(revenue_growth, earnings_growth)
    cap        = GROWTH_CAPS.get(sector, 0.12)
    growth     = min(max(raw_growth, 0.02), cap)

    pe_score,  pe_ratio  = calc_pe_score(pe, sector, sector_pe_map)
    dcf_val              = calc_dcf(eps, growth)
    dcf_score, dcf_margin = calc_dcf_score(price, dcf_val)
    gdm_val              = calc_gdm(eps, growth)
    gdm_score, gdm_margin = calc_gdm_score(price, gdm_val)
    composite            = pe_score + dcf_score + gdm_score
    cagr                 = calc_cagr(price, eps, div_yield, growth)
    benchmark            = sector_pe_map.get(sector, 20)

    return {
        "symbol": symbol,
        "name": stock_info.get("name", data.get("name", symbol)),
        "sector": sector,
        "price": price,
        "currency": data.get("currency", "USD"),
        "pe": pe, "eps": eps, "growth": growth,
        "dcf_value": dcf_val, "gdm_value": gdm_val,
        "pe_score": pe_score, "pe_ratio": pe_ratio, "pe_benchmark": benchmark,
        "dcf_score": dcf_score, "dcf_margin": dcf_margin,
        "gdm_score": gdm_score, "gdm_margin": gdm_margin,
        "composite": composite, "cagr": cagr, "div_yield": div_yield,
    }


# ─────────────────────────── シグナルハンター ─────────────────────────────────

NEWS_PATTERNS = [
    (r"earnings.miss|業績.下方|利益.減少|赤字|予想.下回", "📉 業績悪化"),
    (r"rate.hike|利上げ|金利.上昇|Fed|日銀",              "🏦 金利上昇懸念"),
    (r"trade.war|関税|tariff|貿易摩擦|制裁",              "🌐 貿易摩擦"),
    (r"recession|景気.後退|GDP.マイナス|経済.悪化",        "📊 景気後退懸念"),
    (r"sector.rotation|セクター.ローテ|資金.移動",         "🔄 セクターローテーション"),
    (r"sell.off|急落|暴落|パニック",                      "😱 市場パニック"),
    (r"downgrade|格下げ|レーティング.引下",                "⬇️ アナリスト格下げ"),
    (r"scandal|不祥事|不正|訴訟|リコール",                 "⚠️ 企業スキャンダル"),
    (r"dividend.cut|減配|配当.削減",                      "💸 減配"),
    (r"supply.chain|サプライチェーン|供給.不足",           "🔗 サプライチェーン問題"),
]


def classify_drop_reason(news_list) -> str:
    if not news_list:
        return "📰 ニュースなし"
    all_text = " ".join(item.get("title", "") for item in news_list[:5]).lower()
    for pattern, label in NEWS_PATTERNS:
        if re.search(pattern, all_text, re.IGNORECASE):
            return label
    return "❓ 不明 / その他"


def check_volume_spike(hist_1y):
    if hist_1y is None or hist_1y.empty or "Volume" not in hist_1y.columns:
        return None, None
    vol = hist_1y["Volume"].dropna()
    if len(vol) < 20:
        return None, None
    avg_20d   = float(vol.iloc[-21:-1].mean())
    today_vol = float(vol.iloc[-1])
    if avg_20d == 0:
        return None, None
    return today_vol, today_vol / avg_20d


# ─────────────────────────── ランナー関数 ────────────────────────────────────
# Top Page の「全て更新」から呼び出す。results を返すので呼び出し側で session_state に格納する。

def run_dividend_screener(
    progress_cb: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """
    全 JP_DIVIDEND_STOCKS_BY_SECTOR のティッカーをデフォルト条件でスクリーニング。
    progress_cb(ratio: float, text: str) を渡すと進捗コールバックを受け取れる。
    """
    from screener import ScreenerConfig, screen_from_raw

    all_tickers = [
        t for tickers in JP_DIVIDEND_STOCKS_BY_SECTOR.values() for t in tickers
    ]
    cfg     = ScreenerConfig()
    results = []

    for i, symbol in enumerate(all_tickers):
        if progress_cb:
            progress_cb((i + 1) / len(all_tickers), f"{symbol} ({i+1}/{len(all_tickers)})")
        raw, _ = fetch_with_cache_flag(symbol)
        if raw is None:
            results.append({
                "ticker": symbol, "name": symbol, "sector": "不明",
                "status": "error", "stage": "データ取得", "reason": "データ取得失敗",
                "price": None, "currency": "JPY",
                "equityRatio": None, "dividendYield": None, "dividendRate": None,
                "payoutRatio": None, "operatingMargin": None, "roe": None,
                "dividend_history": pd.Series(dtype=float), "operatingCashflow_3y": [],
            })
        else:
            results.append(screen_from_raw(symbol, raw, cfg))

    return results


def run_buffett_screener(
    stocks: list[dict] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """
    バフェットスクリーナーを実行。stocks を省略すると JP_STOCKS 全件を対象にする。
    """
    if stocks is None:
        stocks = JP_STOCKS

    results = []
    for i, s in enumerate(stocks):
        sym = s["symbol"]
        if progress_cb:
            progress_cb((i + 1) / len(stocks), f"{sym} ({i+1}/{len(stocks)})")
        data, _ = fetch_with_cache_flag(sym)
        result   = analyze_stock(s, data)
        if result:
            results.append(result)

    return results


def run_signal_screener(
    watch_list: list[str] | None = None,
    rsi_threshold: float = 35.0,
    ma_dev_threshold: float = -3.0,
    progress_cb: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """
    シグナルハンターを実行。watch_list を省略すると WATCH_LIST_JP + WATCH_LIST_US を使う。
    """
    if watch_list is None:
        watch_list = list(dict.fromkeys(WATCH_LIST_JP + WATCH_LIST_US))

    results = []
    for i, sym in enumerate(watch_list):
        if progress_cb:
            progress_cb((i + 1) / len(watch_list), f"{sym} ({i+1}/{len(watch_list)})")
        data, _ = fetch_with_cache_flag(sym)
        if data is None:
            continue

        price    = data.get("price")
        rsi      = data.get("rsi14")
        ma25_dev = data.get("ma25DeviationPct")
        high_52w = data.get("fifty_two_week_high")
        low_52w  = data.get("fifty_two_week_low")

        low_proximity = None
        if price and low_52w and high_52w and (high_52w - low_52w) != 0:
            low_proximity = (price - low_52w) / (high_52w - low_52w) * 100

        today_vol, vol_ratio = check_volume_spike(data.get("price_history_1y"))
        has_buy_signal = (
            rsi is not None and rsi < rsi_threshold and
            ma25_dev is not None and ma25_dev < ma_dev_threshold
        )

        results.append({
            "symbol": sym,
            "name": data.get("name", sym)[:12],
            "price": price,
            "currency": data.get("currency", "JPY"),
            "rsi14": rsi,
            "ma25_dev": ma25_dev,
            "ma25": data.get("ma25"),
            "ma75": data.get("ma75"),
            "ma200": data.get("ma200"),
            "high_52w": high_52w,
            "low_52w": low_52w,
            "low_proximity": low_proximity,
            "vol_ratio": vol_ratio,
            "buy_signal": has_buy_signal,
            "drop_reason": classify_drop_reason(data.get("news", [])),
            "news": data.get("news", []),
            "price_history": data.get("price_history_1y"),
        })

    return results
