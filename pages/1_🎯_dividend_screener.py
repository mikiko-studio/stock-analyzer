"""
pages/1_🎯_dividend_screener.py
日本株・米国株 高配当スクリーナー — 3層フィルターエンジン
市場・セクター選択で自動銘柄リスト取得、手動追加も可能
"""

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
from utils.ui_helpers import format_pct, format_currency, hero_header, status_badge_html, render_export_buttons

st.set_page_config(page_title="高配当スクリーナー", page_icon="🎯", layout="wide")

hero_header("高配当スクリーナー", "3層フィルターで選ぶ「鉄壁高配当株」", "🎯")


# ── Auto-fetch S&P 500 by sector ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sp500_by_sector() -> dict | None:
    """Fetch S&P 500 tickers grouped by sector from Wikipedia. Cached 24h.

    Uses requests with a browser User-Agent to avoid Wikipedia bot-blocking,
    then parses the HTML table with lxml (pd.read_html flavor).
    """
    import io as _io
    import requests as _requests

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = _requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(_io.StringIO(resp.text), flavor="lxml")
        df = tables[0]
        result: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            sector = str(row.get("GICS Sector", "Other"))
            symbol = str(row.get("Symbol", "")).strip().replace(".", "-")
            if symbol and symbol != "nan":
                result.setdefault(sector, []).append(symbol)
        return result if result else None
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

    # グローバル設定から初期値を引き継ぐ
    _market_opts = ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"]
    _g_market = st.session_state.get("global_market", "🇯🇵 日本株")
    _market_idx = _market_opts.index(_g_market) if _g_market in _market_opts else 0
    market_sel = st.radio("マーケット", _market_opts, index=_market_idx, horizontal=True)

    st.subheader("銘柄選択")

    auto_tickers: list[str] = []

    # ── 日本株セクター選択 ────────────────────────────────────────────
    if market_sel in ["🇯🇵 日本株", "🌐 両方"]:
        if market_sel == "🌐 両方":
            st.markdown("**🇯🇵 日本株 セクター**")
        all_jp_sectors = list(JP_DIVIDEND_STOCKS_BY_SECTOR.keys())
        # グローバル設定から日本株セクターの初期値を引き継ぐ
        _g_jp = st.session_state.get("global_jp_sectors", all_jp_sectors[:4])
        _valid_jp = [s for s in _g_jp if s in all_jp_sectors] or all_jp_sectors[:4]
        jp_selected = st.multiselect(
            "日本株セクターを選択",
            options=all_jp_sectors,
            default=_valid_jp,
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
    equity_ratio_min = st.slider("自己資本比率 最低基準 (%)", 0, 80, 40, 5, format="%d%%",
                                  help="金融セクターはスキップ")

    st.subheader("Layer 2: 配当の誠実さ")
    dy_min = st.slider("配当利回り 下限 (%)", 0.0, 10.0, 3.5, 0.5, format="%.1f%%")
    dy_max = st.slider("配当利回り 上限（罠配当除外）(%)", 0.0, 20.0, 8.0, 0.5, format="%.1f%%")
    pr_min = st.slider("配当性向 下限 (%)", 0, 100, 30, 5, format="%d%%")
    pr_max = st.slider("配当性向 上限 (%)", 0, 100, 70, 5, format="%d%%")

    st.subheader("Layer 3: 稼ぐ力")
    om_min = st.slider("営業利益率 最低基準 (%)", 0, 30, 10, 1, format="%d%%")
    roe_min = st.slider("ROE 最低基準 (%)", 0, 30, 8, 1, format="%d%%")

    st.divider()
    st.subheader("🔧 データ欠損の扱い")
    skip_no_equity = st.checkbox(
        "自己資本比率データなし → スキップ（不合格にしない）",
        value=True,
        help="yfinanceでバランスシートが取得できない銘柄を脱落させない。日本株で推奨。",
    )
    skip_no_ocf = st.checkbox(
        "営業CFデータなし → スキップ（不合格にしない）",
        value=True,
        help="yfinanceでキャッシュフロー計算書が取得できない銘柄を脱落させない。日本株で推奨。",
    )

    st.subheader("🏦 金融セクターの扱い")
    st.caption("銀行・保険・証券などは自己資本比率チェックが免除されます（業種特性のため）")
    exclude_financial = st.checkbox(
        "金融セクターをスクリーニングから除外する",
        value=False,
        help="銀行・保険・証券などをスクリーニング対象から外します。自己資本比率を厳格に適用したい場合はONにしてください。",
    )

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
    skip_if_no_equity_data=skip_no_equity,
    skip_if_no_ocf_data=skip_no_ocf,
    exclude_financial_sector=exclude_financial,
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
- 過去5年 減配なし（当年除く）
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

    # ── Layer-by-layer breakdown ──────────────────────────────────────────────
    LAYER_STAGES = {
        "Layer 1a: 自己資本比率": "自己資本比率",
        "Layer 1b: 営業CF":       "営業CF",
        "Layer 2a: 配当利回り":   "配当利回り",
        "Layer 2b: 配当性向":     "配当性向",
        "Layer 2c: 減配チェック": "減配チェック",
        "Layer 3a: 営業利益率":   "営業利益率",
        "Layer 3b: ROE":          "ROE",
    }
    total_valid = len(results) - len(errors)
    remaining = total_valid
    layer_rows = []
    for label, stage_key in LAYER_STAGES.items():
        eliminated = sum(1 for r in results if r.get("stage") == stage_key and r["status"] == "failed")
        layer_rows.append({
            "フィルター": label,
            "この段階で脱落": eliminated,
            "残銘柄数": remaining,
        })
        remaining -= eliminated
    layer_rows.append({"フィルター": "✅ 合格", "この段階で脱落": 0, "残銘柄数": len(passed)})

    with st.expander("📊 Layer別 通過数ログ（0件のとき必ず確認）", expanded=(len(passed) == 0)):
        st.dataframe(pd.DataFrame(layer_rows), use_container_width=True, hide_index=True)

        # Highlight biggest elimination stage
        if failed:
            biggest = max(
                LAYER_STAGES.keys(),
                key=lambda lbl: sum(
                    1 for r in results
                    if r.get("stage") == LAYER_STAGES[lbl] and r["status"] == "failed"
                )
            )
            biggest_count = sum(
                1 for r in results
                if r.get("stage") == LAYER_STAGES[biggest] and r["status"] == "failed"
            )
            if biggest_count > 0:
                st.warning(f"最大脱落: **{biggest}** で {biggest_count} 件脱落。フィルター条件を緩めるか「データ欠損の扱い」設定を確認してください。")

        # Data diagnosis: show raw field values for first 5 tickers
        st.markdown("**🔬 生データ診断（先頭5銘柄）**")
        diag_rows = []
        for r in results[:5]:
            sym = r["ticker"]
            raw = _cached_fetch(sym)
            if raw:
                dy = raw.get("dividendYield")
                pr = raw.get("payoutRatio")
                eq = raw.get("equityRatio")
                om = raw.get("operatingMargin")
                roe_val = raw.get("roe")
                ocf = raw.get("operatingCashflow_3y", [])
                diag_rows.append({
                    "銘柄": sym,
                    "dividendYield": f"{dy:.4f} ({dy*100:.2f}%)" if dy is not None else "None",
                    "payoutRatio": f"{pr:.4f}" if pr is not None else "None",
                    "equityRatio": f"{eq:.4f}" if eq is not None else "None ⚠️",
                    "operatingMargin": f"{om:.4f}" if om is not None else "None",
                    "ROE": f"{roe_val:.4f}" if roe_val is not None else "None",
                    "OCF件数": len(ocf) if ocf else "0 ⚠️",
                })
            else:
                diag_rows.append({"銘柄": sym, "dividendYield": "取得失敗", "payoutRatio": "—",
                                   "equityRatio": "—", "operatingMargin": "—", "ROE": "—", "OCF件数": "—"})
        if diag_rows:
            st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)
            st.caption("⚠️ マークは yfinance から取得できなかったフィールド。「データ欠損の扱い」でスキップに設定してください。")

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 合格銘柄", "📉 フィルター分析", "📊 チャート", "📋 全銘柄ログ"])

    with tab1:
        if not passed:
            st.warning("合格銘柄がありませんでした。フィルター条件を緩めてみてください。")
        else:
            # テクニカル指標を取得（キャッシュ済みデータから、1銘柄1回のみ）
            def _get_tech(ticker_sym):
                raw = _cached_fetch(ticker_sym)
                if raw is None:
                    return None, None, None, "—"
                rsi = raw.get("rsi14")
                ma_dev = raw.get("ma25DeviationPct")
                price = raw.get("price")
                high_52w = raw.get("fifty_two_week_high")
                from_high = (
                    (price - high_52w) / high_52w * 100
                    if price and high_52w and high_52w > 0 else None
                )
                signal = (
                    "🟢 買い"
                    if (rsi is not None and rsi < 35 and ma_dev is not None and ma_dev < -3)
                    else "⬜"
                )
                return rsi, ma_dev, from_high, signal

            pass_rows = []
            for r in passed:
                rsi_v, ma_v, high_v, sig_v = _get_tech(r["ticker"])
                pass_rows.append({
                    "銘柄": r["ticker"],
                    "会社名": r.get("name", "")[:12],
                    "セクター": r.get("sector", ""),
                    "株価": format_currency(r.get("price"), r.get("currency", "JPY")),
                    "配当利回り": format_pct(r.get("dividendYield")),
                    "配当性向": format_pct(r.get("payoutRatio")),
                    "自己資本比率": (
                        "🏦 免除（金融業）" if r.get("is_financial")
                        else ("⚠️ データなし" if r.get("equityRatio") is None
                              else format_pct(r.get("equityRatio")))
                    ),
                    "営業利益率": format_pct(r.get("operatingMargin")),
                    "ROE": format_pct(r.get("roe")),
                    "RSI(14)": f"{rsi_v:.1f}" if rsi_v is not None else "—",
                    "25日MA乖離率": f"{ma_v:.1f}%" if ma_v is not None else "—",
                    "52週高値比": f"{high_v:.1f}%" if high_v is not None else "—",
                    "テクシグナル": sig_v,
                })
            df_pass = pd.DataFrame(pass_rows)

            st.dataframe(df_pass, use_container_width=True, hide_index=True)

            # Export buttons (CSV + Excel) using raw numeric values
            df_pass_export = pd.DataFrame([{
                "銘柄": r["ticker"],
                "会社名": r.get("name", ""),
                "セクター": r.get("sector", ""),
                "市場": r.get("market", ""),
                "株価": r.get("price"),
                "通貨": r.get("currency", "JPY"),
                "配当利回り": r.get("dividendYield"),
                "配当性向": r.get("payoutRatio"),
                "自己資本比率": r.get("equityRatio"),
                "営業利益率": r.get("operatingMargin"),
                "ROE": r.get("roe"),
            } for r in passed])
            render_export_buttons(
                df_pass_export,
                filename_prefix="dividend_screener",
                pct_cols=["配当利回り", "配当性向", "自己資本比率", "営業利益率", "ROE"],
                float2_cols=["株価"],
            )

            # OCF trend expander
            with st.expander("💹 営業キャッシュフロー推移（直近3年）"):
                has_any_ocf = any(r.get("operatingCashflow_3y") for r in passed)
                if not has_any_ocf:
                    st.info("営業CFデータが取得できた銘柄がありませんでした。")
                else:
                    ocf_cols = st.columns(min(len(passed), 3))
                    for idx, r in enumerate(passed):
                        ocf_vals = r.get("operatingCashflow_3y", [])
                        ocf_yrs = r.get("operatingCashflow_years", [])
                        if not ocf_vals:
                            continue

                        # Reverse so chart reads oldest → newest (left → right)
                        ocf_vals_disp = list(reversed(ocf_vals))
                        ocf_yrs_disp = list(reversed(ocf_yrs)) if ocf_yrs else [
                            f"{len(ocf_vals) - i}年前" if i > 0 else "直近"
                            for i in range(len(ocf_vals) - 1, -1, -1)
                        ]

                        # Unit: convert to 億円 (JP) or 億ドル (US)
                        currency = r.get("currency", "JPY")
                        unit_divisor = 1e8 if currency == "JPY" else 1e8
                        unit_label = "億円" if currency == "JPY" else "億USD"
                        ocf_unit = [v / unit_divisor for v in ocf_vals_disp]

                        # Trend color: green if latest ≥ oldest, else red
                        trend_up = ocf_vals_disp[-1] >= ocf_vals_disp[0]
                        bar_colors = [
                            "#22c55e" if trend_up else "#ef4444"
                        ] * len(ocf_unit)

                        fig_ocf = go.Figure(go.Bar(
                            x=ocf_yrs_disp,
                            y=ocf_unit,
                            marker_color=bar_colors,
                            text=[f"{v:.0f}" for v in ocf_unit],
                            textposition="outside",
                        ))
                        fig_ocf.update_layout(
                            title=f"{r['ticker']} {r.get('name', '')[:10]}",
                            yaxis_title=unit_label,
                            height=260,
                            margin=dict(t=40, b=10, l=10, r=10),
                            showlegend=False,
                        )

                        with ocf_cols[idx % 3]:
                            st.plotly_chart(fig_ocf, use_container_width=True)
                            # Trend annotation
                            if len(ocf_vals_disp) >= 2:
                                change_pct = (ocf_vals_disp[-1] / ocf_vals_disp[0] - 1) * 100
                                arrow = "↑" if change_pct >= 0 else "↓"
                                color = "green" if change_pct >= 0 else "red"
                                st.markdown(
                                    f"<small style='color:{color}'>{arrow} {abs(change_pct):.1f}%（{ocf_yrs_disp[0]}→{ocf_yrs_disp[-1]}）</small>",
                                    unsafe_allow_html=True,
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
