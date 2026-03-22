"""
pages/2_📐_buffett_screener.py
三角測量 割安銘柄スクリーナー — P/E + DCF + GDM
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import JP_STOCKS, SECTOR_PE_JP, SECTOR_PE_US, US_STOCKS
from utils.data_fetcher import fetch_with_cache_flag
from utils.ui_helpers import format_pct, format_currency, hero_header, score_color

st.set_page_config(page_title="三角測量スクリーナー", page_icon="📐", layout="wide")

hero_header("三角測量スクリーナー", "P/E・DCF・GDM 3手法による割安銘柄発見", "📐")

# ── Constants ────────────────────────────────────────────────────────────────
DISCOUNT_RATE = 0.09
TERMINAL_GROWTH = 0.03
DCF_YEARS = 10
HURDLE_RATE = 0.10

# Max growth cap by sector
GROWTH_CAPS = {
    "Technology": 0.20, "Communication Services": 0.15,
    "Consumer Discretionary": 0.15, "Consumer Staples": 0.10,
    "Healthcare": 0.12, "Financials": 0.10, "Industrials": 0.12,
    "Energy": 0.08, "Materials": 0.08, "Utilities": 0.07,
    "Real Estate": 0.08,
    "電気機器": 0.15, "情報通信": 0.15, "医薬品": 0.12,
    "輸送用機器": 0.08, "銀行業": 0.07, "小売業": 0.10,
    "機械": 0.10, "化学": 0.08, "サービス業": 0.12,
}

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ スクリーナー設定")
    market = st.radio("マーケット", ["🇯🇵 日本株", "🇺🇸 米国株"], horizontal=True)
    is_jp = market.startswith("🇯🇵")
    stocks = JP_STOCKS if is_jp else US_STOCKS
    sector_pe = SECTOR_PE_JP if is_jp else SECTOR_PE_US

    max_stocks = st.slider("分析銘柄数（上位N件）", 5, len(stocks), min(20, len(stocks)), 5)
    show_explanation = st.toggle("🔍 トップ銘柄の詳細説明を表示", value=True)
    card_view = st.toggle("🃏 カード表示モード", value=False)
    run_btn = st.button("🚀 分析実行", type="primary", use_container_width=True)


# ── Valuation Models ─────────────────────────────────────────────────────────
def calc_pe_score(pe, sector, sector_pe_map):
    """P/E score: compare to sector benchmark."""
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
    """Calculate DCF intrinsic value."""
    if eps is None or eps <= 0:
        return None
    pv = 0
    for y in range(1, years + 1):
        projected_eps = eps * (1 + growth_rate) ** y
        pv += projected_eps / (1 + discount_rate) ** y
    # Terminal value
    terminal_eps = eps * (1 + growth_rate) ** years
    terminal_value = (terminal_eps * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    pv += terminal_value / (1 + discount_rate) ** years
    return pv


def calc_dcf_score(price, intrinsic_value):
    """DCF score: compare current price to intrinsic value."""
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
    """Graham Defensive Model: EPS × (8.5 + 2g) × 4.4 / Y"""
    if eps is None or eps <= 0:
        return None
    if bond_yield <= 0:
        bond_yield = 0.045
    return eps * (8.5 + 2 * growth_rate * 100) * 4.4 / (bond_yield * 100)


def calc_gdm_score(price, gdm_value):
    """GDM score."""
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
    """Calculate expected CAGR."""
    if price is None or eps is None or price <= 0:
        return None
    future_price = price * (1 + growth_rate) ** years
    total_divs = price * div_yield * years if div_yield else 0
    try:
        cagr = ((future_price + total_divs) / price) ** (1 / years) - 1
        return cagr
    except Exception:
        return None


def analyze_stock(stock_info, data):
    """Run all 3 valuation models on a stock."""
    if data is None:
        return None

    symbol = stock_info["symbol"]
    sector = stock_info.get("sector", data.get("sector", "Unknown"))
    price = data.get("price")
    eps = data.get("trailingEps") or data.get("forwardEps")
    pe = data.get("trailingPE")
    div_yield = data.get("dividendYield") or 0
    revenue_growth = data.get("revenueGrowth") or 0
    earnings_growth = data.get("earningsGrowth") or 0

    # Growth rate: cap to sector maximum
    raw_growth = max(revenue_growth, earnings_growth)
    cap = GROWTH_CAPS.get(sector, 0.12)
    growth = min(max(raw_growth, 0.02), cap)

    # Model scores
    pe_score, pe_ratio = calc_pe_score(pe, sector, sector_pe)
    dcf_val = calc_dcf(eps, growth)
    dcf_score, dcf_margin = calc_dcf_score(price, dcf_val)
    gdm_val = calc_gdm(eps, growth)
    gdm_score, gdm_margin = calc_gdm_score(price, gdm_val)
    composite = pe_score + dcf_score + gdm_score

    cagr = calc_cagr(price, eps, div_yield, growth)

    return {
        "symbol": symbol,
        "name": stock_info.get("name", data.get("name", symbol)),
        "sector": sector,
        "price": price,
        "currency": data.get("currency", "USD"),
        "pe": pe,
        "eps": eps,
        "growth": growth,
        "dcf_value": dcf_val,
        "gdm_value": gdm_val,
        "pe_score": pe_score,
        "pe_ratio": pe_ratio,
        "dcf_score": dcf_score,
        "dcf_margin": dcf_margin,
        "gdm_score": gdm_score,
        "gdm_margin": gdm_margin,
        "composite": composite,
        "cagr": cagr,
        "div_yield": div_yield,
    }


# ── Main ─────────────────────────────────────────────────────────────────────
if run_btn or f"buffett_results_{market}" in st.session_state:
    target_stocks = stocks[:max_stocks]

    if run_btn:
        results = []
        progress = st.progress(0, text="分析中...")
        for i, s in enumerate(target_stocks):
            progress.progress((i + 1) / len(target_stocks), text=f"分析中: {s['symbol']}")
            data, _ = fetch_with_cache_flag(s["symbol"])
            result = analyze_stock(s, data)
            if result:
                results.append(result)
        progress.empty()
        st.session_state[f"buffett_results_{market}"] = results

    results = st.session_state.get(f"buffett_results_{market}", [])
    if not results:
        st.warning("分析結果がありません")
        st.stop()

    # Sort by composite score
    results = sorted(results, key=lambda x: x["composite"], reverse=True)

    # ── Summary ──────────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("分析銘柄数", len(results))
    bullish = sum(1 for r in results if r["composite"] >= 3)
    m2.metric("強い買いシグナル(≥3点)", bullish)
    avg_score = sum(r["composite"] for r in results) / len(results) if results else 0
    m3.metric("平均スコア", f"{avg_score:.1f}/6")
    top = results[0]
    m4.metric("トップ銘柄", f"{top['symbol']} ({top['composite']}点)")

    if card_view:
        # Card view
        cols = st.columns(3)
        for i, r in enumerate(results[:9]):
            with cols[i % 3]:
                color = score_color(r["composite"], 6)
                st.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:4px;
            border-left:4px solid {color};">
<b>{r['symbol']}</b> {r['name'][:10]}<br>
<span style="color:{color};font-size:1.4rem;font-weight:bold;">{r['composite']}/6</span><br>
P/E: {r['pe_score']:+d} | DCF: {r['dcf_score']:+d} | GDM: {r['gdm_score']:+d}<br>
株価: {format_currency(r['price'], r['currency'])}
</div>
""", unsafe_allow_html=True)
    else:
        # Table view
        df = pd.DataFrame([{
            "銘柄": r["symbol"],
            "会社名": r["name"][:12],
            "セクター": r["sector"][:8],
            "株価": format_currency(r["price"], r["currency"]),
            "P/E評価": r["pe_score"],
            "DCF評価": r["dcf_score"],
            "GDM評価": r["gdm_score"],
            "総合スコア": r["composite"],
            "成長率(推定)": format_pct(r.get("growth")),
            "期待CAGR": format_pct(r.get("cagr")),
        } for r in results])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Score heatmap
    with st.expander("📊 スコア分布チャート"):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="P/E スコア",
            x=[r["symbol"] for r in results[:20]],
            y=[r["pe_score"] for r in results[:20]],
            marker_color="#3b82f6",
        ))
        fig.add_trace(go.Bar(
            name="DCF スコア",
            x=[r["symbol"] for r in results[:20]],
            y=[r["dcf_score"] for r in results[:20]],
            marker_color="#22c55e",
        ))
        fig.add_trace(go.Bar(
            name="GDM スコア",
            x=[r["symbol"] for r in results[:20]],
            y=[r["gdm_score"] for r in results[:20]],
            marker_color="#f59e0b",
        ))
        fig.update_layout(
            barmode="group",
            title="銘柄別 評価スコア内訳",
            yaxis_title="スコア (-2 to +2)",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top stock explanation
    if show_explanation and results:
        top = results[0]
        with st.expander(f"🔍 トップ銘柄詳細: {top['symbol']} {top['name']}", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**📊 P/E 分析**")
                st.markdown(f"- 実績P/E: {top.get('pe', 'N/A')}")
                benchmark = sector_pe.get(top["sector"], 20)
                st.markdown(f"- セクター基準P/E: {benchmark}")
                pe_ratio = top.get("pe_ratio")
                st.markdown(f"- 比率: {f'{pe_ratio:.2f}' if pe_ratio else 'N/A'}")
                color = score_color(top["pe_score"])
                st.markdown(f"- スコア: **<span style='color:{color}'>{top['pe_score']:+d}</span>**", unsafe_allow_html=True)
            with c2:
                st.markdown("**💰 DCF 分析**")
                st.markdown(f"- EPS: {top.get('eps', 'N/A')}")
                st.markdown(f"- 推定成長率: {format_pct(top.get('growth'))}")
                st.markdown(f"- 内在価値: {format_currency(top.get('dcf_value'), top['currency'])}")
                color = score_color(top["dcf_score"])
                st.markdown(f"- スコア: **<span style='color:{color}'>{top['dcf_score']:+d}</span>**", unsafe_allow_html=True)
            with c3:
                st.markdown("**📐 GDM 分析**")
                st.markdown(f"- グレアム価値: {format_currency(top.get('gdm_value'), top['currency'])}")
                st.markdown(f"- 現在株価: {format_currency(top.get('price'), top['currency'])}")
                st.markdown(f"- 期待CAGR: {format_pct(top.get('cagr'))}")
                color = score_color(top["gdm_score"])
                st.markdown(f"- スコア: **<span style='color:{color}'>{top['gdm_score']:+d}</span>**", unsafe_allow_html=True)
else:
    st.info("👈 サイドバーからマーケットを選択して「分析実行」を押してください")
