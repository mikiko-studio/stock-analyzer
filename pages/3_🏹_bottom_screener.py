"""
pages/3_🏹_bottom_screener.py
シグナル・ハンター — 底値スクリーナー
RSI + MA乖離 + ニュース解析による押し目買い判定
"""

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import WATCH_LIST_JP, WATCH_LIST_US
from utils.data_fetcher import fetch_with_cache_flag
from utils.ui_helpers import format_pct, format_currency, hero_header

st.set_page_config(page_title="シグナル・ハンター", page_icon="🏹", layout="wide")

hero_header("シグナル・ハンター", "テクニカル分析 × ニュース解析による押し目買い判定", "🏹")

# ── News pattern matching ─────────────────────────────────────────────────────
NEWS_PATTERNS = [
    (r"earnings.miss|業績.下方|利益.減少|赤字|予想.下回", "📉 業績悪化"),
    (r"rate.hike|利上げ|金利.上昇|Fed|日銀", "🏦 金利上昇懸念"),
    (r"trade.war|関税|tariff|貿易摩擦|制裁", "🌐 貿易摩擦"),
    (r"recession|景気.後退|GDP.マイナス|経済.悪化", "📊 景気後退懸念"),
    (r"sector.rotation|セクター.ローテ|資金.移動", "🔄 セクターローテーション"),
    (r"sell.off|急落|暴落|パニック", "😱 市場パニック"),
    (r"downgrade|格下げ|レーティング.引下", "⬇️ アナリスト格下げ"),
    (r"scandal|不祥事|不正|訴訟|リコール", "⚠️ 企業スキャンダル"),
    (r"dividend.cut|減配|配当.削減", "💸 減配"),
    (r"supply.chain|サプライチェーン|供給.不足", "🔗 サプライチェーン問題"),
]


def classify_drop_reason(news_list):
    """Classify drop reason from news titles using pattern matching."""
    if not news_list:
        return "📰 ニュースなし"
    all_text = " ".join(
        item.get("title", "") for item in news_list[:5]
    ).lower()
    for pattern, label in NEWS_PATTERNS:
        if re.search(pattern, all_text, re.IGNORECASE):
            return label
    return "❓ 不明 / その他"


def check_volume_spike(hist_1y):
    """Check if today's volume is significantly higher than 20-day average."""
    if hist_1y is None or hist_1y.empty or "Volume" not in hist_1y.columns:
        return None, None
    vol = hist_1y["Volume"].dropna()
    if len(vol) < 20:
        return None, None
    avg_20d = float(vol.iloc[-21:-1].mean())
    today_vol = float(vol.iloc[-1])
    if avg_20d == 0:
        return None, None
    ratio = today_vol / avg_20d
    return today_vol, ratio


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ シグナル設定")

    market_sel = st.radio("マーケット", ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"], index=2)

    st.subheader("買いシグナル条件")
    rsi_threshold = st.slider("RSI(14) 上限（以下で買いシグナル）", 20, 50, 35, 1)
    ma_dev_threshold = st.slider("25日MA乖離率 上限（以下で買いシグナル）", -15.0, -1.0, -3.0, 0.5,
                                   format="%.1f%%")

    st.subheader("カスタム銘柄追加")
    custom_tickers = st.text_area(
        "追加銘柄（1行1コード）",
        height=100,
        placeholder="例:\n6501.T\nTSLA",
    )

    run_btn = st.button("🔍 スキャン実行", type="primary", use_container_width=True)

# Build watch list
watch_list = []
if market_sel in ["🇯🇵 日本株", "🌐 両方"]:
    watch_list.extend(WATCH_LIST_JP)
if market_sel in ["🇺🇸 米国株", "🌐 両方"]:
    watch_list.extend(WATCH_LIST_US)
if custom_tickers:
    for t in custom_tickers.strip().split("\n"):
        t = t.strip()
        if t and t not in watch_list:
            watch_list.append(t)

# ── Main ─────────────────────────────────────────────────────────────────────
if run_btn or "bottom_results" in st.session_state:
    if run_btn:
        results = []
        progress = st.progress(0, text="スキャン中...")
        for i, sym in enumerate(watch_list):
            progress.progress((i + 1) / len(watch_list), text=f"スキャン中: {sym}")
            data, _ = fetch_with_cache_flag(sym)
            if data is None:
                continue

            price = data.get("price")
            rsi = data.get("rsi14")
            ma25_dev = data.get("ma25DeviationPct")
            high_52w = data.get("fifty_two_week_high")
            low_52w = data.get("fifty_two_week_low")

            # 52W proximity
            low_proximity = None
            if price and low_52w and high_52w and (high_52w - low_52w) != 0:
                low_proximity = (price - low_52w) / (high_52w - low_52w) * 100

            # Volume spike
            today_vol, vol_ratio = check_volume_spike(data.get("price_history_1y"))

            # Buy signal
            has_buy_signal = (
                rsi is not None and rsi < rsi_threshold and
                ma25_dev is not None and ma25_dev < ma_dev_threshold
            )

            # Drop reason
            drop_reason = classify_drop_reason(data.get("news", []))

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
                "drop_reason": drop_reason,
                "news": data.get("news", []),
                "price_history": data.get("price_history_1y"),
            })

        progress.empty()
        st.session_state["bottom_results"] = results

    results = st.session_state.get("bottom_results", [])
    if not results:
        st.warning("スキャン結果がありません")
        st.stop()

    # Summary
    signals = [r for r in results if r["buy_signal"]]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("スキャン銘柄数", len(results))
    m2.metric("🟢 買いシグナル", len(signals))
    oversold = sum(1 for r in results if r.get("rsi14") and r["rsi14"] < 30)
    m3.metric("RSI<30 (売られすぎ)", oversold)
    strong_dev = sum(1 for r in results if r.get("ma25_dev") and r["ma25_dev"] < -5)
    m4.metric("25日MA乖離 <-5%", strong_dev)

    # ── Results Table ────────────────────────────────────────────────────────
    st.subheader("📊 スキャン結果一覧")

    show_signals_only = st.checkbox("買いシグナル銘柄のみ表示", value=False)
    display_results = signals if show_signals_only else results

    rows = []
    for r in display_results:
        rsi_val = r.get("rsi14")
        ma_dev = r.get("ma25_dev")
        rows.append({
            "シグナル": "🟢 買い" if r["buy_signal"] else "⬜",
            "銘柄": r["symbol"],
            "会社名": r["name"],
            "株価": format_currency(r.get("price"), r.get("currency", "JPY")),
            "RSI(14)": f"{rsi_val:.1f}" if rsi_val else "—",
            "25日MA乖離(%)": f"{ma_dev:.1f}%" if ma_dev else "—",
            "52W High": format_currency(r.get("high_52w"), r.get("currency", "JPY")),
            "52W Low": format_currency(r.get("low_52w"), r.get("currency", "JPY")),
            "底値近接(%)": f"{r['low_proximity']:.1f}%" if r.get("low_proximity") else "—",
            "出来高比率": f"{r['vol_ratio']:.1f}x" if r.get("vol_ratio") else "—",
            "下落理由": r.get("drop_reason", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Buy Signal Details ───────────────────────────────────────────────────
    if signals:
        st.subheader("🟢 買いシグナル銘柄の詳細")
        for r in signals:
            with st.expander(f"{r['symbol']} {r['name']} — RSI:{r.get('rsi14', 0):.1f} | MA乖離:{r.get('ma25_dev', 0):.1f}%"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    # Price chart
                    hist = r.get("price_history")
                    if hist is not None and not hist.empty:
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=hist.index, y=hist["Close"],
                            name="株価", line=dict(color="#3b82f6"),
                        ))
                        if r.get("ma25"):
                            ma25_series = hist["Close"].rolling(25).mean()
                            fig.add_trace(go.Scatter(
                                x=hist.index, y=ma25_series,
                                name="25日MA", line=dict(color="#f59e0b", dash="dash"),
                            ))
                        if r.get("ma75"):
                            ma75_series = hist["Close"].rolling(75).mean()
                            fig.add_trace(go.Scatter(
                                x=hist.index, y=ma75_series,
                                name="75日MA", line=dict(color="#22c55e", dash="dot"),
                            ))
                        fig.update_layout(height=300, margin=dict(t=10, b=10), showlegend=True)
                        st.plotly_chart(fig, use_container_width=True)
                with c2:
                    rsi_val = r.get("rsi14", 0) or 0
                    ma_dev_val = r.get("ma25_dev", 0) or 0
                    high_52w = r.get("high_52w")
                    low_52w = r.get("low_52w")
                    price_val = r.get("price")
                    vol_ratio = r.get("vol_ratio")

                    st.metric("RSI(14)", f"{rsi_val:.1f}")
                    # RSI interpretation
                    if rsi_val < 30:
                        rsi_interp = f"現在値 {rsi_val:.1f} → **売られすぎ水準**（買いシグナル）。短期リバウンドに期待できる"
                        st.success(rsi_interp)
                    elif rsi_val < 40:
                        rsi_interp = f"現在値 {rsi_val:.1f} → 弱め。売り圧力が続いているが底打ちに近い可能性"
                        st.info(rsi_interp)
                    elif rsi_val < 60:
                        rsi_interp = f"現在値 {rsi_val:.1f} → 中立。特段のシグナルなし"
                        st.info(rsi_interp)
                    elif rsi_val < 70:
                        rsi_interp = f"現在値 {rsi_val:.1f} → やや強め。勢いはあるが過熱感に注意"
                        st.warning(rsi_interp)
                    else:
                        rsi_interp = f"現在値 {rsi_val:.1f} → **買われすぎ水準**（売りシグナル）。短期的な調整に注意"
                        st.error(rsi_interp)

                    st.metric("25日MA乖離", f"{ma_dev_val:.1f}%")
                    # MA deviation interpretation
                    if ma_dev_val <= -10:
                        ma_interp = f"現在値 {ma_dev_val:.1f}% → **大幅下乖離**。リバウンド期待が高い水準。底値圏の可能性"
                        st.success(ma_interp)
                    elif ma_dev_val <= -5:
                        ma_interp = f"現在値 {ma_dev_val:.1f}% → 下乖離。押し目買いを検討できる水準"
                        st.info(ma_interp)
                    elif ma_dev_val <= 5:
                        ma_interp = f"現在値 {ma_dev_val:.1f}% → MA付近で推移。トレンドを見極める局面"
                        st.info(ma_interp)
                    elif ma_dev_val <= 10:
                        ma_interp = f"現在値 {ma_dev_val:.1f}% → 上乖離。勢いはあるが押し目を待つのが無難"
                        st.warning(ma_interp)
                    else:
                        ma_interp = f"現在値 {ma_dev_val:.1f}% → **大幅上乖離**。過熱感あり。新規買いは慎重に"
                        st.error(ma_interp)

                    # 52W high/low interpretations
                    if price_val and high_52w and low_52w and high_52w > low_52w:
                        from_high_pct = (price_val - high_52w) / high_52w * 100
                        from_low_pct = (price_val - low_52w) / low_52w * 100

                        st.metric("52週高値比", f"{from_high_pct:.1f}%")
                        if from_high_pct <= -30:
                            st.success(f"高値から**{abs(from_high_pct):.0f}%下落**した水準。大きな押し目買いの候補")
                        elif from_high_pct <= -20:
                            st.info(f"高値から**{abs(from_high_pct):.0f}%下落**。押し目買いを検討できる水準")
                        elif from_high_pct <= -10:
                            st.info(f"高値から**{abs(from_high_pct):.0f}%下落**。中程度の調整")
                        else:
                            st.warning(f"高値から**{abs(from_high_pct):.0f}%下落**。まだ高値圏に近い")

                        st.metric("52週安値比", f"+{from_low_pct:.1f}%")
                        if from_low_pct <= 10:
                            st.success(f"安値から**{from_low_pct:.0f}%上昇**した水準。底値に非常に近い")
                        elif from_low_pct <= 20:
                            st.info(f"安値から**{from_low_pct:.0f}%上昇**。安値圏に近い")
                        else:
                            st.info(f"安値から**{from_low_pct:.0f}%上昇**した水準")

                    # Volume interpretation
                    if vol_ratio is not None:
                        st.metric("出来高比率（20日平均比）", f"{vol_ratio:.1f}x")
                        if vol_ratio >= 2.0:
                            st.success(f"現在値 **{vol_ratio:.1f}倍** → 通常の2倍以上の出来高。大きな注目・転換点の可能性")
                        elif vol_ratio >= 1.5:
                            st.info(f"現在値 **{vol_ratio:.1f}倍** → 注目度上昇中。トレンド転換のサインかもしれない")
                        elif vol_ratio >= 0.8:
                            st.info(f"現在値 **{vol_ratio:.1f}倍** → 平均的な出来高。特段のシグナルなし")
                        else:
                            st.warning(f"現在値 **{vol_ratio:.1f}倍** → 閑散相場。積極的な買い手が少ない")

                    st.metric("下落理由", r.get("drop_reason", "不明"))

                    # News
                    if r.get("news"):
                        st.markdown("**最新ニュース:**")
                        for news in r["news"][:3]:
                            title = news.get("title", "")
                            link = news.get("link", "#")
                            st.markdown(f"- [{title[:40]}...]({link})")
    else:
        st.info(f"買いシグナル（RSI<{rsi_threshold} かつ 25日MA乖離<{ma_dev_threshold}%）の銘柄はありませんでした")
else:
    st.info("👈 サイドバーから設定して「スキャン実行」を押してください")
