"""
pages/1_🎯_dividend_screener.py
日本株・米国株 高配当スクリーナー — 3層フィルターエンジン
市場・セクター選択で自動銘柄リスト取得、手動追加も可能
"""

import io
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from screener import ScreenerConfig, screen_from_raw
from utils.constants import (
    DEFAULT_DIVIDEND_TICKERS,
    FILTER_STAGES,
    JP_DIVIDEND_STOCKS_BY_SECTOR,
)
from utils.data_fetcher import _cached_fetch, fetch_with_cache_flag
from utils.ui_helpers import format_pct, format_currency, hero_header, status_badge_html

st.set_page_config(page_title="高配当スクリーナー", page_icon="🎯", layout="wide")

hero_header("高配当スクリーナー", "3層フィルターで選ぶ「鉄壁高配当株」", "🎯")


# ── Auto-fetch S&P 500 by sector ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sp500_by_sector() -> dict | None:
    """Fetch S&P 500 tickers grouped by sector from Wikipedia. Cached 24h."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        result: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            sector = str(row.get("GICS Sector", "Other"))
            symbol = str(row.get("Symbol", "")).strip().replace(".", "-")
            if symbol:
                result.setdefault(sector, []).append(symbol)
        return result
    except Exception:
        return None


def get_us_sectors_fallback() -> dict[str, list[str]]:
    """Fallback US sectors from built-in US_STOCKS list."""
    from utils.constants import US_STOCKS
    result: dict[str, list[str]] = {}
    for s in US_STOCKS:
        result.setdefault(s["sector"], []).append(s["symbol"])
    return result


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ スクリーナー設定")

    market_sel = st.radio("マーケット", ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"], horizontal=True)

    st.subheader("銘柄選択")

    auto_tickers: list[str] = []

    # ── 日本株セクター選択 ────────────────────────────────────────────
    if market_sel in ["🇯🇵 日本株", "🌐 両方"]:
        if market_sel == "🌐 両方":
            st.markdown("**🇯🇵 日本株 セクター**")
        all_jp_sectors = list(JP_DIVIDEND_STOCKS_BY_SECTOR.keys())
        jp_selected = st.multiselect(
            "日本株セクターを選択",
            options=all_jp_sectors,
            default=all_jp_sectors[:4],
            help="選択したセクターの銘柄が自動でスクリーニング対象になります",
            label_visibility="collapsed" if market_sel == "🌐 両方" else "visible",
        )
        for sec in jp_selected:
            auto_tickers.extend(JP_DIVIDEND_STOCKS_BY_SECTOR[sec])

    # ── 米国株セクター選択 ────────────────────────────────────────────
    if market_sel in ["🇺🇸 米国株", "🌐 両方"]:
        if market_sel == "🌐 両方":
            st.markdown("**🇺🇸 米国株 セクター**")
        with st.spinner("S&P500銘柄リストを取得中..."):
            sp500_data = fetch_sp500_by_sector()
        if sp500_data:
            st.caption("📡 Wikipedia から S&P500 取得済み")
        else:
            st.caption("⚠️ 取得失敗 — 内蔵リストを使用")
            sp500_data = get_us_sectors_fallback()
        us_sectors = list(sp500_data.keys())
        us_selected = st.multiselect(
            "米国株セクターを選択",
            options=us_sectors,
            default=us_sectors[:3] if us_sectors else [],
            help="S&P500の構成銘柄からセクターで絞り込みます",
            label_visibility="collapsed" if market_sel == "🌐 両方" else "visible",
        )
        for sec in us_selected:
            auto_tickers.extend(sp500_data.get(sec, []))

    selected_count = len(auto_tickers)
    if selected_count > 0:
        st.caption(f"自動選択: {selected_count} 銘柄")
    else:
        st.warning("セクターを1つ以上選択してください")

    st.subheader("カスタム銘柄追加（任意）")
    custom_input = st.text_area(
        "追加銘柄（1行1コード）",
        height=100,
        placeholder="例:\n8058.T\nAAPL\n9433.T",
        help="自動リストに含まれない銘柄を手動で追加できます",
    )
    custom_tickers = [t.strip() for t in custom_input.strip().split("\n") if t.strip()]
    if custom_tickers:
        st.caption(f"＋ カスタム: {len(custom_tickers)} 銘柄")

    # Deduplicate while preserving order
    all_tickers = list(dict.fromkeys(auto_tickers + custom_tickers))

    if all_tickers:
        st.info(f"**合計: {len(all_tickers)} 銘柄** をスクリーニング対象とします")
    else:
        st.warning("銘柄が0件です。セクターを選択するか、手動で入力してください。")

    st.subheader("Layer 1: 財務の鉄壁")
    equity_ratio_min = st.slider("自己資本比率 最低基準 (%)", 0, 80, 30, 5, format="%d%%",
                                  help="金融セクターはスキップ")

    st.subheader("Layer 2: 配当の誠実さ")
    dy_min = st.slider("配当利回り 下限 (%)", 0.0, 10.0, 3.0, 0.5, format="%.1f%%")
    dy_max = st.slider("配当利回り 上限（罠配当除外）(%)", 0.0, 20.0, 10.0, 0.5, format="%.1f%%")
    pr_min = st.slider("配当性向 下限 (%)", 0, 100, 0, 5, format="%d%%")
    pr_max = st.slider("配当性向 上限 (%)", 0, 100, 80, 5, format="%d%%")

    st.subheader("Layer 3: 稼ぐ力")
    om_min = st.slider("営業利益率 最低基準 (%)", 0, 30, 5, 1, format="%d%%")
    roe_min = st.slider("ROE 最低基準 (%)", 0, 30, 8, 1, format="%d%%")

    st.divider()
    run_button = st.button("🚀 スクリーニング実行", type="primary", use_container_width=True,
                            disabled=(len(all_tickers) == 0))

    if st.button("🗑️ キャッシュクリア", use_container_width=True):
        _cached_fetch.clear()
        fetch_sp500_by_sector.clear()
        for k in list(st.session_state.keys()):
            if k.startswith("_fetched_"):
                del st.session_state[k]
        st.success("キャッシュをクリアしました")

cfg = ScreenerConfig(
    equity_ratio_min=equity_ratio_min / 100,
    dividend_yield_min=dy_min / 100,
    dividend_yield_max=dy_max / 100,
    payout_ratio_min=pr_min / 100,
    payout_ratio_max=pr_max / 100,
    operating_margin_min=om_min / 100,
    roe_min=roe_min / 100,
)

# ── 3-Layer Explanation Cards ────────────────────────────────────────────────
with st.expander("📖 3層フィルターについて", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
**🛡️ Layer 1: 財務の鉄壁**
- 自己資本比率 ≥ 40%
- 直近3年 営業CF がプラス
→ 財務基盤の安定性チェック
""")
    with c2:
        st.markdown("""
**💝 Layer 2: 配当の誠実さ**
- 配当利回り 3.75〜8%
- 配当性向 30〜70%
- 過去10年 減配なし
→ 配当の持続可能性チェック
""")
    with c3:
        st.markdown("""
**💪 Layer 3: 稼ぐ力**
- 営業利益率 ≥ 10%
- ROE ≥ 8%
→ 収益性・資本効率チェック
""")

# ── Main Execution ───────────────────────────────────────────────────────────
if run_button or "screener_results" in st.session_state:
    tickers = all_tickers if run_button else [
        r["ticker"] for r in st.session_state.get("screener_results", [])
    ]

    if run_button:
        if not all_tickers:
            st.error("スクリーニング対象銘柄がありません。セクターを選択してください。")
            st.stop()

        results = []
        log_lines = []

        progress_bar = st.progress(0, text="スクリーニング開始...")
        log_placeholder = st.empty()

        for i, symbol in enumerate(all_tickers):
            progress_bar.progress((i + 1) / len(all_tickers), text=f"処理中: {symbol} ({i+1}/{len(all_tickers)})")

            raw, is_hit = fetch_with_cache_flag(symbol)
            cache_icon = "💾" if is_hit else "🌐"

            if raw is None:
                result = {
                    "ticker": symbol, "name": symbol, "sector": "不明",
                    "status": "error", "stage": "データ取得", "reason": "データ取得失敗",
                    "price": None, "currency": "JPY",
                    "equityRatio": None, "dividendYield": None, "dividendRate": None,
                    "payoutRatio": None, "operatingMargin": None, "roe": None,
                    "dividend_history": pd.Series(dtype=float), "operatingCashflow_3y": [],
                }
                log_lines.append(f"{cache_icon} {symbol}: ⚠️ データ取得失敗")
            else:
                result = screen_from_raw(symbol, raw, cfg)
                status_icon = "✅" if result["status"] == "passed" else "❌"
                log_lines.append(
                    f"{cache_icon} {symbol} ({result.get('name','')[:10]}): "
                    f"{status_icon} {result.get('stage','')} — {result.get('reason','')[:40]}"
                )

            results.append(result)
            log_placeholder.text("\n".join(log_lines[-8:]))

        progress_bar.empty()
        log_placeholder.empty()
        st.session_state["screener_results"] = results
        st.session_state["screener_config"] = cfg

    results = st.session_state.get("screener_results", [])
    if not results:
        st.info("銘柄が選択されていません")
        st.stop()

    # Re-run screening with updated config (pure function, no re-fetch)
    if "screener_config" in st.session_state and not run_button:
        rerun_results = []
        for r in results:
            sym = r["ticker"]
            raw = _cached_fetch(sym)
            if raw:
                rerun_results.append(screen_from_raw(sym, raw, cfg))
            else:
                rerun_results.append(r)
        results = rerun_results
        st.session_state["screener_results"] = results

    passed = [r for r in results if r["status"] == "passed"]
    failed = [r for r in results if r["status"] == "failed"]
    errors = [r for r in results if r["status"] == "error"]

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総銘柄数", len(results))
    m2.metric("✅ 合格", len(passed))
    m3.metric("❌ 不合格", len(failed))
    m4.metric("⚠️ エラー", len(errors))

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 合格銘柄", "📉 フィルター分析", "📊 チャート", "📋 全銘柄ログ"])

    with tab1:
        if not passed:
            st.warning("合格銘柄がありませんでした。フィルター条件を緩めてみてください。")
        else:
            df_pass = pd.DataFrame([{
                "銘柄": r["ticker"],
                "会社名": r.get("name", "")[:12],
                "セクター": r.get("sector", ""),
                "株価": format_currency(r.get("price"), r.get("currency", "JPY")),
                "配当利回り": format_pct(r.get("dividendYield")),
                "配当性向": format_pct(r.get("payoutRatio")),
                "自己資本比率": format_pct(r.get("equityRatio")),
                "営業利益率": format_pct(r.get("operatingMargin")),
                "ROE": format_pct(r.get("roe")),
            } for r in passed])

            st.dataframe(df_pass, use_container_width=True, hide_index=True)

            # CSV download
            csv_buf = io.StringIO()
            df_pass.to_csv(csv_buf, index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 CSVダウンロード",
                csv_buf.getvalue().encode("utf-8-sig"),
                "dividend_screener_passed.csv",
                "text/csv",
            )

            # Dividend history expander
            with st.expander("📈 配当履歴（合格銘柄）"):
                for r in passed:
                    hist = r.get("dividend_history", pd.Series(dtype=float))
                    if isinstance(hist, pd.Series) and not hist.empty:
                        st.markdown(f"**{r['ticker']} {r.get('name','')}**")
                        fig = px.bar(
                            x=hist.index.astype(str),
                            y=hist.values,
                            labels={"x": "年", "y": f"配当額 ({r.get('currency','JPY')})"},
                            title=f"{r['ticker']} — 年間配当履歴",
                        )
                        fig.update_layout(height=250, margin=dict(t=30, b=10))
                        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Funnel chart
        stage_counts = {}
        total = len(results)
        remaining = total

        for stage in FILTER_STAGES:
            eliminated = sum(1 for r in results if r.get("stage") == stage and r["status"] == "failed")
            stage_counts[stage] = remaining
            remaining -= eliminated

        stage_counts["合格"] = len(passed)

        funnel_df = pd.DataFrame({
            "ステージ": list(stage_counts.keys()),
            "残銘柄数": list(stage_counts.values()),
        })

        fig_funnel = go.Figure(go.Funnel(
            y=funnel_df["ステージ"],
            x=funnel_df["残銘柄数"],
            textinfo="value+percent initial",
            marker=dict(color=["#3b82f6", "#6366f1", "#8b5cf6", "#a855f7",
                                "#ec4899", "#ef4444", "#f97316", "#22c55e", "#14b8a6"]),
        ))
        fig_funnel.update_layout(title="フィルター漏斗 (ファネルチャート)", height=500)
        st.plotly_chart(fig_funnel, use_container_width=True)

        # Elimination breakdown
        elim_data = []
        for stage in FILTER_STAGES:
            stage_failed = [r for r in results if r.get("stage") == stage and r["status"] == "failed"]
            if stage_failed:
                elim_data.append({
                    "フィルター段階": stage,
                    "脱落数": len(stage_failed),
                    "銘柄": ", ".join(r["ticker"] for r in stage_failed),
                })
        if elim_data:
            st.dataframe(pd.DataFrame(elim_data), use_container_width=True, hide_index=True)

    with tab3:
        if len(passed) >= 2:
            # Scatter: yield vs ROE
            scatter_data = [{
                "ticker": r["ticker"],
                "配当利回り(%)": (r.get("dividendYield") or 0) * 100,
                "ROE(%)": (r.get("roe") or 0) * 100,
                "営業利益率(%)": (r.get("operatingMargin") or 0) * 100,
            } for r in passed]
            df_scatter = pd.DataFrame(scatter_data)
            fig_scatter = px.scatter(
                df_scatter,
                x="配当利回り(%)",
                y="ROE(%)",
                text="ticker",
                size="営業利益率(%)",
                title="配当利回り vs ROE（合格銘柄）",
                labels={"配当利回り(%)": "配当利回り (%)", "ROE(%)": "ROE (%)"},
            )
            fig_scatter.update_traces(textposition="top center")
            fig_scatter.update_layout(height=450)
            st.plotly_chart(fig_scatter, use_container_width=True)

            # Grouped bar: key metrics comparison
            bar_data = []
            for r in passed:
                for metric, val in [
                    ("配当利回り", (r.get("dividendYield") or 0) * 100),
                    ("営業利益率", (r.get("operatingMargin") or 0) * 100),
                    ("ROE", (r.get("roe") or 0) * 100),
                ]:
                    bar_data.append({"銘柄": r["ticker"], "指標": metric, "値(%)": val})
            df_bar = pd.DataFrame(bar_data)
            fig_bar = px.bar(
                df_bar, x="銘柄", y="値(%)", color="指標", barmode="group",
                title="合格銘柄 主要指標比較",
            )
            fig_bar.update_layout(height=400)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("チャート表示には合格銘柄が2件以上必要です")

    with tab4:
        status_filter = st.selectbox(
            "ステータスフィルター",
            ["全て", "✅ 合格", "❌ 不合格", "⚠️ エラー"],
        )
        filter_map = {
            "全て": None,
            "✅ 合格": "passed",
            "❌ 不合格": "failed",
            "⚠️ エラー": "error",
        }
        filter_status = filter_map[status_filter]
        filtered = results if filter_status is None else [r for r in results if r["status"] == filter_status]

        df_all = pd.DataFrame([{
            "銘柄": r["ticker"],
            "会社名": r.get("name", "")[:12],
            "ステータス": {"passed": "✅ 合格", "failed": "❌ 不合格", "error": "⚠️ エラー"}.get(r["status"], r["status"]),
            "脱落段階": r.get("stage", ""),
            "理由": r.get("reason", ""),
            "配当利回り": format_pct(r.get("dividendYield")),
            "ROE": format_pct(r.get("roe")),
        } for r in filtered])
        st.dataframe(df_all, use_container_width=True, hide_index=True)
else:
    st.info("👈 サイドバーからマーケット・セクターを選択して「スクリーニング実行」ボタンを押してください")
