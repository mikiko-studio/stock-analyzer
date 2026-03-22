"""
pages/2_📐_buffett_screener.py
三角測量 割安銘柄スクリーナー — P/E + DCF + GDM
"""

import numpy as np
import pandas as pd
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
    market = st.radio("マーケット", ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"], horizontal=True)

    if market == "🌐 両方":
        max_jp = st.slider("日本株 分析銘柄数", 5, len(JP_STOCKS), min(15, len(JP_STOCKS)), 5)
        max_us = st.slider("米国株 分析銘柄数", 5, len(US_STOCKS), min(15, len(US_STOCKS)), 5)
        stocks = [{"**market**": "JP", **s} for s in JP_STOCKS[:max_jp]] + \
                 [{"**market**": "US", **s} for s in US_STOCKS[:max_us]]
    else:
        is_jp = market.startswith("🇯🇵")
        base_stocks = JP_STOCKS if is_jp else US_STOCKS
        max_stocks = st.slider("分析銘柄数（上位N件）", 5, len(base_stocks), min(20, len(base_stocks)), 5)
        stocks = base_stocks[:max_stocks]

    card_view = st.toggle("🃏 カード表示モード", value=False)
    run_btn = st.button("🚀 分析実行", type="primary", use_container_width=True)


# ── Valuation Models ─────────────────────────────────────────────────────────
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
        cagr = ((future_price + total_divs) / price) ** (1 / years) - 1
        return cagr
    except Exception:
        return None


def analyze_stock(stock_info, data, sector_pe_jp=SECTOR_PE_JP, sector_pe_us=SECTOR_PE_US):
    """Run all 3 valuation models on a stock."""
    if data is None:
        return None

    symbol = stock_info["symbol"]
    is_jp_stock = symbol.endswith(".T")
    sector_pe_map = sector_pe_jp if is_jp_stock else sector_pe_us

    sector = stock_info.get("sector", data.get("sector", "Unknown"))
    price = data.get("price")
    eps = data.get("trailingEps") or data.get("forwardEps")
    pe = data.get("trailingPE")
    div_yield = data.get("dividendYield") or 0
    revenue_growth = data.get("revenueGrowth") or 0
    earnings_growth = data.get("earningsGrowth") or 0

    raw_growth = max(revenue_growth, earnings_growth)
    cap = GROWTH_CAPS.get(sector, 0.12)
    growth = min(max(raw_growth, 0.02), cap)

    pe_score, pe_ratio = calc_pe_score(pe, sector, sector_pe_map)
    dcf_val = calc_dcf(eps, growth)
    dcf_score, dcf_margin = calc_dcf_score(price, dcf_val)
    gdm_val = calc_gdm(eps, growth)
    gdm_score, gdm_margin = calc_gdm_score(price, gdm_val)
    composite = pe_score + dcf_score + gdm_score

    cagr = calc_cagr(price, eps, div_yield, growth)
    benchmark = sector_pe_map.get(sector, 20)

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
        "pe_benchmark": benchmark,
        "dcf_score": dcf_score,
        "dcf_margin": dcf_margin,
        "gdm_score": gdm_score,
        "gdm_margin": gdm_margin,
        "composite": composite,
        "cagr": cagr,
        "div_yield": div_yield,
    }


# ── Metric Interpretation Helpers ────────────────────────────────────────────
def interpret_pe(r: dict) -> str:
    pe = r.get("pe")
    pe_score = r.get("pe_score", 0)
    pe_ratio = r.get("pe_ratio")
    benchmark = r.get("pe_benchmark", 20)
    if pe is None:
        return "P/Eデータなし — 計算不可"
    ratio_str = f"{pe_ratio:.2f}" if pe_ratio else "N/A"
    if pe_score == 2:
        return f"P/E **{pe:.1f}** → セクター平均({benchmark})の{ratio_str}倍。**大幅割安** — 積極的な買い候補"
    elif pe_score == 1:
        return f"P/E **{pe:.1f}** → セクター平均({benchmark})より割安。**買いを検討できる水準**"
    elif pe_score == 0:
        return f"P/E **{pe:.1f}** → セクター平均({benchmark})並み。フェアバリュー — 割安感は薄い"
    elif pe_score == -1:
        return f"P/E **{pe:.1f}** → セクター平均({benchmark})より**割高**。成長性で正当化できるか要確認"
    else:
        return f"P/E **{pe:.1f}** → セクター平均({benchmark})の{ratio_str}倍。**大幅割高** — 高成長期待が織り込み済み"


def interpret_dcf(r: dict) -> str:
    dcf_val = r.get("dcf_value")
    dcf_score = r.get("dcf_score", 0)
    dcf_margin = r.get("dcf_margin")
    currency = r.get("currency", "JPY")
    eps = r.get("eps")
    if dcf_val is None or eps is None:
        return "DCF計算不可 — EPSデータなし（赤字企業や非公開企業に多い）"
    margin_pct = abs(dcf_margin * 100) if dcf_margin else 0
    val_str = format_currency(dcf_val, currency)
    if dcf_score == 2:
        return f"内在価値({val_str})より現在株価が**{margin_pct:.0f}%割安**。安全マージン十分 — バフェットが好む水準"
    elif dcf_score == 1:
        return f"内在価値({val_str})より**{margin_pct:.0f}%割安**。買いを検討できる水準"
    elif dcf_score == 0:
        return f"内在価値({val_str})と**ほぼ同水準**。フェアバリュー — 大きな上値余地は限定的"
    elif dcf_score == -1:
        return f"内在価値({val_str})より**{margin_pct:.0f}%割高**。将来成長が現在価格に織り込まれている"
    else:
        return f"内在価値({val_str})より**{margin_pct:.0f}%割高**。高成長を前提にした価格設定 — 期待外れリスクに注意"


def interpret_gdm(r: dict) -> str:
    gdm_val = r.get("gdm_value")
    gdm_score = r.get("gdm_score", 0)
    gdm_margin = r.get("gdm_margin")
    currency = r.get("currency", "JPY")
    eps = r.get("eps")
    if gdm_val is None or eps is None:
        return "グレアム価値計算不可 — EPSデータなし"
    margin_pct = abs(gdm_margin * 100) if gdm_margin else 0
    val_str = format_currency(gdm_val, currency)
    if gdm_score == 2:
        return f"グレアム価値({val_str})より**{margin_pct:.0f}%割安**。防衛的投資家に適した水準 — 下値リスクが小さい"
    elif gdm_score == 1:
        return f"グレアム価値({val_str})より**{margin_pct:.0f}%割安**。保守的評価でも割安"
    elif gdm_score == 0:
        return f"グレアム価値({val_str})と**ほぼ同水準**。保守的にはフェアバリュー"
    elif gdm_score == -1:
        return f"グレアム価値({val_str})より**{margin_pct:.0f}%割高**。保守的投資家には割高感あり"
    else:
        return f"グレアム価値({val_str})より**{margin_pct:.0f}%割高**。グレアム基準では買いにくい水準"


def render_stock_detail(r: dict, sector_pe_map_jp=SECTOR_PE_JP, sector_pe_map_us=SECTOR_PE_US):
    """Render detailed analysis for a selected stock."""
    color = score_color(r["composite"], 6)
    st.markdown(
        f"<h4>{r['symbol']} — {r['name']} "
        f"<span style='color:{color}'>総合スコア: {r['composite']}/6</span></h4>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📊 P/E 分析**")
        pe_color = score_color(r["pe_score"])
        st.markdown(f"- 実績P/E: **{r.get('pe', 'N/A')}**")
        st.markdown(f"- セクター基準P/E: {r.get('pe_benchmark', 'N/A')}")
        pe_ratio = r.get("pe_ratio")
        st.markdown(f"- セクター比: {f'{pe_ratio:.2f}' if pe_ratio else 'N/A'}")
        st.markdown(f"- スコア: **<span style='color:{pe_color}'>{r['pe_score']:+d}</span>**", unsafe_allow_html=True)
        st.info(interpret_pe(r))

    with c2:
        st.markdown("**💰 DCF 分析（割引キャッシュフロー）**")
        dcf_color = score_color(r["dcf_score"])
        st.markdown(f"- EPS: **{r.get('eps', 'N/A')}**")
        st.markdown(f"- 推定成長率: {format_pct(r.get('growth'))}")
        st.markdown(f"- 内在価値: **{format_currency(r.get('dcf_value'), r['currency'])}**")
        st.markdown(f"- スコア: **<span style='color:{dcf_color}'>{r['dcf_score']:+d}</span>**", unsafe_allow_html=True)
        st.info(interpret_dcf(r))

    with c3:
        st.markdown("**📐 GDM 分析（グレアム防衛モデル）**")
        gdm_color = score_color(r["gdm_score"])
        st.markdown(f"- グレアム価値: **{format_currency(r.get('gdm_value'), r['currency'])}**")
        st.markdown(f"- 現在株価: **{format_currency(r.get('price'), r['currency'])}**")
        st.markdown(f"- 期待CAGR: {format_pct(r.get('cagr'))}")
        st.markdown(f"- スコア: **<span style='color:{gdm_color}'>{r['gdm_score']:+d}</span>**", unsafe_allow_html=True)
        st.info(interpret_gdm(r))


# ── Main ─────────────────────────────────────────────────────────────────────
session_key = f"buffett_results_{market}"

if run_btn or session_key in st.session_state:
    if run_btn:
        results = []
        progress = st.progress(0, text="分析中...")
        target = stocks
        for i, s in enumerate(target):
            sym = s["symbol"]
            progress.progress((i + 1) / len(target), text=f"分析中: {sym}")
            data, _ = fetch_with_cache_flag(sym)
            result = analyze_stock(s, data)
            if result:
                results.append(result)
        progress.empty()
        st.session_state[session_key] = results

    results = st.session_state.get(session_key, [])
    if not results:
        st.warning("分析結果がありません")
        st.stop()

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

    # ── Stock Detail (user selects from table) ────────────────────────────────
    st.subheader("🔍 銘柄詳細分析")
    symbol_options = [f"{r['symbol']} — {r['name'][:12]}　（スコア: {r['composite']}/6）" for r in results]
    selected_idx = st.selectbox(
        "詳細を確認したい銘柄を選択",
        options=range(len(symbol_options)),
        format_func=lambda i: symbol_options[i],
        index=0,
    )
    selected = results[selected_idx]

    with st.container(border=True):
        render_stock_detail(selected)

else:
    st.info("👈 サイドバーからマーケットを選択して「分析実行」を押してください")

# ── 単独銘柄チェック ──────────────────────────────────────────────────────────
st.divider()
st.subheader("🎯 単独銘柄チェック")
st.caption("スクリーニング結果に関係なく、気になる銘柄を単体で分析します")

with st.form("single_check_form"):
    col_a, col_b = st.columns([3, 1])
    with col_a:
        single_input = st.text_input(
            "銘柄コードを入力",
            placeholder="例: 7203.T（トヨタ）、AAPL（Apple）",
        )
    with col_b:
        single_sector = st.text_input(
            "セクター（任意）",
            placeholder="例: 輸送用機器",
            help="空欄の場合は yfinance のセクター情報を使用します",
        )
    check_btn = st.form_submit_button("🔍 分析する", type="primary")

if check_btn and single_input.strip():
    sym = single_input.strip()
    with st.spinner(f"{sym} のデータを取得中..."):
        data, _ = fetch_with_cache_flag(sym)

    if data is None:
        st.error(f"「{sym}」のデータを取得できませんでした。銘柄コードを確認してください。")
    else:
        sector_override = single_sector.strip() if single_sector.strip() else data.get("sector", "Unknown")
        stock_info_single = {
            "symbol": sym,
            "name": data.get("name", sym),
            "sector": sector_override,
        }
        single_result = analyze_stock(stock_info_single, data)
        if single_result:
            with st.container(border=True):
                render_stock_detail(single_result)
        else:
            st.warning("スコアを計算できませんでした（EPSや株価データが不足している可能性があります）")
elif check_btn:
    st.warning("銘柄コードを入力してください")
