"""
pages/2_📐_buffett_screener.py
三角測量 割安銘柄スクリーナー — P/E + DCF + GDM
"""

import numpy as np
import pandas as pd
import streamlit as st

from utils.constants import JP_STOCKS, SECTOR_PE_JP, SECTOR_PE_US, US_STOCKS
from utils.data_fetcher import _cached_fetch, fetch_with_cache_flag
from utils.screener_runner import (
    DISCOUNT_RATE, TERMINAL_GROWTH, DCF_YEARS, HURDLE_RATE, GROWTH_CAPS,
    calc_pe_score, calc_dcf, calc_dcf_score, calc_gdm, calc_gdm_score,
    calc_cagr, analyze_stock,
)
from utils.ui_helpers import format_pct, format_currency, hero_header, score_color, render_export_buttons

hero_header("バフェットスクリーナー × シグナル・ハンター", "P/E・DCF・GDM × テクニカル指標による割安銘柄発見", "📐")

# ── スクリーニング基準の説明 ───────────────────────────────────────────────────
with st.expander("📖 三角測量スクリーニングについて", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
**📊 P/E 分析（株価収益率）**
- 実績P/Eをセクター平均と比較
- P/E < セクター平均×60% → **+2点（大幅割安）**
- P/E < セクター平均×80% → +1点
- P/E ≈ セクター平均 → 0点
- P/E > セクター平均×130% → **-2点（大幅割高）**

→ 同業他社と比較した「市場評価」のチェック
""")
    with c2:
        st.markdown("""
**💰 DCF 分析（割引キャッシュフロー）**
- EPS × 成長率で10年分の将来キャッシュを試算
- 割引率9%で現在価値に換算
- 安全マージン > 30% → **+2点**
- 安全マージン > 10% → +1点
- 安全マージン < -30% → **-2点**

→ 「内在価値」に対して今の株価が割安かどうかを判定
""")
    with c3:
        st.markdown("""
**📐 GDM 分析（グレアム防衛モデル）**
- EPS × (8.5 + 2×成長率) × 4.4 ÷ 債券利回り
- ベンジャミン・グレアムの古典的公式に基づく保守的評価
- グレアム価値比 > 30% → **+2点**
- グレアム価値比 > 10% → +1点
- グレアム価値比 < -30% → **-2点**

→ 保守的投資家視点の「下値リスク」チェック
""")
    st.markdown("""
---
**総合スコア = P/E評価 + DCF評価 + GDM評価（-6〜+6点）**

| スコア | 判定 | 意味 |
|--------|------|------|
| 5〜6点 | 🔥 強い買い | 3手法すべてで割安。強い買い候補 |
| 4点 | ✅ 買い | 複数手法で割安。買いを検討できる水準 |
| 2〜3点 | 👀 様子見 | 一部では割安だが慎重に判断 |
| 1点以下 | ⚠️ 見送り | 割高感あり。新規買いは見送り |
""")

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ スクリーナー設定")
    _market_opts = ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"]
    _g_market = st.session_state.get("global_market", "🇯🇵 日本株")
    _market_idx = _market_opts.index(_g_market) if _g_market in _market_opts else 0
    market = st.radio("マーケット", _market_opts, index=_market_idx, horizontal=True)

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


# ── Buy Signal Icon & Technical Data ─────────────────────────────────────────
def get_signal_icon(composite: int) -> str:
    """Return a visual buy signal icon based on composite score (out of 6)."""
    if composite >= 5:
        return "🔥 強い買い"
    elif composite >= 4:
        return "✅ 買い"
    elif composite >= 2:
        return "👀 様子見"
    else:
        return "⚠️ 見送り"


def get_bottom_indicators(symbol: str) -> dict:
    """Fetch bottom_screener indicators from cached data."""
    raw = _cached_fetch(symbol)
    if raw is None:
        return {"rsi14": None, "ma25_dev": None, "from_high": None, "tech_signal": "—"}
    rsi = raw.get("rsi14")
    ma_dev = raw.get("ma25DeviationPct")
    price = raw.get("price")
    high_52w = raw.get("fifty_two_week_high")
    from_high = (
        (price - high_52w) / high_52w * 100
        if price and high_52w and high_52w > 0 else None
    )
    tech_signal = (
        "🟢 買い"
        if (rsi is not None and rsi < 35 and ma_dev is not None and ma_dev < -3)
        else "⬜"
    )
    return {"rsi14": rsi, "ma25_dev": ma_dev, "from_high": from_high, "tech_signal": tech_signal}


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
    signal_icon = get_signal_icon(r["composite"])
    st.markdown(
        f"<h4>{r['symbol']} — {r['name']} "
        f"<span style='color:{color}'>総合スコア: {r['composite']}/6 &nbsp; {signal_icon}</span></h4>",
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

_auto_rerun_buf = st.session_state.pop("_auto_rerun_buffett", False)
if _auto_rerun_buf and st.session_state.get("_last_stocks_buffett"):
    stocks = st.session_state["_last_stocks_buffett"]

_trigger_run_buf = run_btn or _auto_rerun_buf

if _trigger_run_buf or session_key in st.session_state:
    if _trigger_run_buf:
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
        st.session_state["_last_stocks_buffett"] = stocks

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
                icon = get_signal_icon(r["composite"])
                st.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:4px;
            border-left:4px solid {color};">
<b>{r['symbol']}</b> {r['name'][:10]}<br>
<span style="color:{color};font-size:1.4rem;font-weight:bold;">{r['composite']}/6</span>
&nbsp;<span style="font-size:0.85rem;">{icon}</span><br>
P/E: {r['pe_score']:+d} | DCF: {r['dcf_score']:+d} | GDM: {r['gdm_score']:+d}<br>
株価: {format_currency(r['price'], r['currency'])}
</div>
""", unsafe_allow_html=True)
    else:
        tbl_rows = []
        for r in results:
            tech = get_bottom_indicators(r["symbol"])
            rsi_v = tech["rsi14"]
            ma_v = tech["ma25_dev"]
            high_v = tech["from_high"]
            tbl_rows.append({
                "シグナル": get_signal_icon(r["composite"]),
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
                "RSI(14)": f"{rsi_v:.1f}" if rsi_v is not None else "—",
                "25日MA乖離率": f"{ma_v:.1f}%" if ma_v is not None else "—",
                "52週高値比": f"{high_v:.1f}%" if high_v is not None else "—",
                "テクシグナル": tech["tech_signal"],
            })
        df = pd.DataFrame(tbl_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Export buttons (always shown, uses raw numeric values)
    df_export = pd.DataFrame([{
        "銘柄": r["symbol"],
        "会社名": r["name"],
        "セクター": r["sector"],
        "株価": r.get("price"),
        "通貨": r.get("currency", "USD"),
        "P/E": r.get("pe"),
        "P/E評価": r["pe_score"],
        "DCF評価": r["dcf_score"],
        "GDM評価": r["gdm_score"],
        "総合スコア": r["composite"],
        "成長率(推定)": r.get("growth"),
        "期待CAGR": r.get("cagr"),
        "配当利回り": r.get("div_yield"),
        "内在価値(DCF)": r.get("dcf_value"),
        "グレアム価値(GDM)": r.get("gdm_value"),
    } for r in results])
    render_export_buttons(
        df_export,
        filename_prefix="buffett_screener",
        pct_cols=["成長率(推定)", "期待CAGR", "配当利回り"],
        float2_cols=["株価", "P/E", "内在価値(DCF)", "グレアム価値(GDM)"],
    )

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
