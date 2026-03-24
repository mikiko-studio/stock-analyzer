"""
home.py — Top Page content for the Stock Analyzer Suite.
Navigation and page_config are managed in app.py via st.navigation().
"""

import io
import os
import datetime

import pandas as pd
import streamlit as st

from utils.constants import JP_DIVIDEND_STOCKS_BY_SECTOR, US_STOCKS
from utils.ui_helpers import score_color

# ── ヘッダー & ツール説明 ──────────────────────────────────────────────────────
st.title("📊 Stock Analyzer Suite")
st.markdown("### 株式分析統合ツール — Japan & US Market")

st.markdown("""
日本・米国の株式市場から投資候補を多角的にスクリーニングするための分析ツールです。
**財務健全性・配当・バリュエーション・テクニカル指標**を組み合わせることで、
単一の視点では見落としがちな優良銘柄を効率よく発見できます。
初心者から中級者の投資判断をサポートすることを目的としており、
すべての分析結果は CSV / Excel / PDF 形式でダウンロードできます。
""")

st.divider()

# ── Global Settings Panel ─────────────────────────────────────────────────────
with st.expander("⚙️ グローバル設定（全スクリーナーに反映）", expanded=True):
    g_col1, g_col2, g_col3 = st.columns([1, 2, 1])

    with g_col1:
        st.markdown("**マーケット選択**")
        _market_opts = ["🇯🇵 日本株", "🇺🇸 米国株", "🌐 両方"]
        _saved_market = st.session_state.get("global_market", "🇯🇵 日本株")
        _market_idx = _market_opts.index(_saved_market) if _saved_market in _market_opts else 0
        global_market = st.radio(
            "マーケット",
            _market_opts,
            index=_market_idx,
            label_visibility="collapsed",
            key="global_market_radio",
        )
        st.session_state["global_market"] = global_market

    with g_col2:
        all_jp_sectors = list(JP_DIVIDEND_STOCKS_BY_SECTOR.keys())
        us_sector_list = sorted({s["sector"] for s in US_STOCKS})

        if global_market in ["🇯🇵 日本株", "🌐 両方"]:
            st.markdown("**🇯🇵 日本株セクター**")
            _saved_jp = st.session_state.get("global_jp_sectors", all_jp_sectors[:4])
            _valid_jp = [s for s in _saved_jp if s in all_jp_sectors] or all_jp_sectors[:4]
            global_jp_sectors = st.multiselect(
                "日本株セクター",
                options=all_jp_sectors,
                default=_valid_jp,
                label_visibility="collapsed",
                key="global_jp_sectors_ms",
            )
            st.session_state["global_jp_sectors"] = global_jp_sectors

        if global_market in ["🇺🇸 米国株", "🌐 両方"]:
            st.markdown("**🇺🇸 米国株セクター**")
            _saved_us = st.session_state.get("global_us_sectors", us_sector_list[:3])
            _valid_us = [s for s in _saved_us if s in us_sector_list] or us_sector_list[:3]
            global_us_sectors = st.multiselect(
                "米国株セクター",
                options=us_sector_list,
                default=_valid_us,
                label_visibility="collapsed",
                key="global_us_sectors_ms",
            )
            st.session_state["global_us_sectors"] = global_us_sectors

    with g_col3:
        st.markdown("**カスタム銘柄追加**")
        custom_text = st.text_area(
            "銘柄コード（1行1コード）",
            value=st.session_state.get("global_custom_tickers_text", ""),
            height=120,
            placeholder="例:\n8058.T\nAAPL\n9433.T",
            label_visibility="collapsed",
            key="global_custom_text",
        )
        st.session_state["global_custom_tickers_text"] = custom_text
        custom_tickers = [t.strip() for t in custom_text.strip().split("\n") if t.strip()]
        st.session_state["global_custom_tickers"] = custom_tickers
        if custom_tickers:
            st.caption(f"＋ {len(custom_tickers)} 銘柄追加")
        st.caption("設定はサイドバーの初期値として各スクリーナーに引き継がれます")

st.divider()

# ── Navigation Cards ──────────────────────────────────────────────────────────
st.caption("👇 各スクリーナーの名称をクリックすると詳細分析画面に移動します")

nav_col1, nav_col2, nav_col3 = st.columns(3)

with nav_col1:
    with st.container(border=True):
        st.page_link(
            "pages/1_🎯_dividend_signal_screener.py",
            label="🎯 高配当スクリーナー × シグナル・ハンター",
        )
        st.markdown("""
財務健全性・配当の安定性・テクニカル指標を3層で評価し、
「買いやすいタイミング」の高配当株を抽出します。
- **Layer 1** 財務の鉄壁: 自己資本比率・営業CF
- **Layer 2** 配当の誠実さ: 利回り・性向・減配チェック
- **Layer 3** 稼ぐ力: 営業利益率・ROE
- **＋ テクニカル** RSI・MA乖離・52週高値比も同時表示
""")

with nav_col2:
    with st.container(border=True):
        st.page_link(
            "pages/2_📐_buffett_signal_screener.py",
            label="📐 バフェットスクリーナー × シグナル・ハンター",
        )
        st.markdown("""
バフェット流の3つのバリュエーション手法で割安度を採点し、
テクニカル指標で「今が買い場か」を重ね合わせて判断します。
- **P/E分析**: セクター平均との比較
- **DCF**: 割引キャッシュフローによる内在価値計算
- **GDM**: グレアム防衛的価値モデル
- **＋ テクニカル** RSI・MA乖離・52週高値比も同時表示
""")

with nav_col3:
    with st.container(border=True):
        st.page_link(
            "pages/4_⚖️_portfolio_dashboard.py",
            label="⚖️ ポートフォリオ診断",
        )
        st.markdown("""
年齢・リスク許容度に合わせた資産配分を最適化します。
住宅ローンや将来の支出計画も含めた総合的な資産管理が可能です。
- 目標アセットアロケーション計算
- 住宅ローン金利上昇シミュレーション
- ライフイベント資金計画タイムライン
- 月次収支シミュレーション
""")

st.divider()

# ── Top 5 Results from each screener (直接展開表示) ──────────────────────────
st.subheader("📊 各スクリーナー Top5 銘柄")

# ── 高配当スクリーナー × シグナル・ハンター ────────────────────────────────
st.markdown("#### 🎯 高配当スクリーナー × シグナル・ハンター")
div_results = st.session_state.get("screener_results", [])
passed_div = [r for r in div_results if r.get("status") == "passed"]
if not passed_div:
    st.info("⏳ 未実行 — 高配当スクリーナーを実行するとTop5がここに表示されます")
else:
    top5 = passed_div[:5]
    cols = st.columns(min(len(top5), 5))
    for i, r in enumerate(top5):
        with cols[i]:
            dy = r.get("dividendYield")
            dy_str = f"{dy*100:.1f}%" if dy else "—"
            roe = r.get("roe")
            roe_str = f"{roe*100:.1f}%" if roe else "—"
            om = r.get("operatingMargin")
            om_str = f"{om*100:.1f}%" if om else "—"
            with st.container(border=True):
                st.markdown(f"**{r['ticker']}**")
                st.caption(r.get("name", "")[:12])
                st.metric("配当利回り", dy_str)
                st.caption(f"ROE: {roe_str} | 営業利益率: {om_str}")

st.markdown("---")

# ── バフェットスクリーナー × シグナル・ハンター ────────────────────────────
st.markdown("#### 📐 バフェットスクリーナー × シグナル・ハンター")
buf_results = None
for key in ["buffett_results_🇯🇵 日本株", "buffett_results_🇺🇸 米国株", "buffett_results_🌐 両方"]:
    if key in st.session_state and st.session_state[key]:
        buf_results = sorted(st.session_state[key], key=lambda x: x["composite"], reverse=True)
        break

if not buf_results:
    st.info("⏳ 未実行 — バフェットスクリーナーを実行するとTop5がここに表示されます")
else:
    top5 = buf_results[:5]
    cols = st.columns(min(len(top5), 5))
    for i, r in enumerate(top5):
        with cols[i]:
            composite = r.get("composite", 0)
            if composite >= 5:
                icon = "🔥"
            elif composite >= 4:
                icon = "✅"
            elif composite >= 2:
                icon = "👀"
            else:
                icon = "⚠️"
            with st.container(border=True):
                st.markdown(f"**{r['symbol']}**")
                st.caption(r.get("name", "")[:12])
                st.metric("総合スコア", f"{icon} {composite}/6")
                st.caption(
                    f"P/E:{r.get('pe_score', 0):+d} "
                    f"DCF:{r.get('dcf_score', 0):+d} "
                    f"GDM:{r.get('gdm_score', 0):+d}"
                )

st.divider()

# ── 一括ダウンロード ───────────────────────────────────────────────────────────
st.subheader("📥 一括ダウンロード")


def _build_div_df():
    div_res = st.session_state.get("screener_results", [])
    passed = [r for r in div_res if r.get("status") == "passed"]
    if not passed:
        return None
    return pd.DataFrame([{
        "スクリーナー": "高配当×シグナル",
        "銘柄": r["ticker"],
        "会社名": r.get("name", ""),
        "配当利回り(%)": round(r.get("dividendYield", 0) * 100, 2) if r.get("dividendYield") else None,
        "配当性向(%)": round(r.get("payoutRatio", 0) * 100, 1) if r.get("payoutRatio") else None,
        "自己資本比率(%)": round(r.get("equityRatio", 0) * 100, 1) if r.get("equityRatio") else None,
        "営業利益率(%)": round(r.get("operatingMargin", 0) * 100, 1) if r.get("operatingMargin") else None,
        "ROE(%)": round(r.get("roe", 0) * 100, 1) if r.get("roe") else None,
    } for r in passed])


def _build_buf_df():
    for key in ["buffett_results_🇯🇵 日本株", "buffett_results_🇺🇸 米国株", "buffett_results_🌐 両方"]:
        if key in st.session_state and st.session_state[key]:
            buf = st.session_state[key]
            return pd.DataFrame([{
                "スクリーナー": "バフェット×シグナル",
                "銘柄": r["symbol"],
                "会社名": r.get("name", ""),
                "総合スコア": r.get("composite"),
                "P/E評価": r.get("pe_score"),
                "DCF評価": r.get("dcf_score"),
                "GDM評価": r.get("gdm_score"),
                "成長率(%)": round(r.get("growth", 0) * 100, 1) if r.get("growth") else None,
                "期待CAGR(%)": round(r.get("cagr", 0) * 100, 1) if r.get("cagr") else None,
            } for r in buf])
    return None


def _build_bot_df():
    bot = st.session_state.get("bottom_results", [])
    if not bot:
        return None
    return pd.DataFrame([{
        "スクリーナー": "シグナル単体",
        "銘柄": r["symbol"],
        "会社名": r.get("name", ""),
        "RSI(14)": round(r["rsi14"], 1) if r.get("rsi14") is not None else None,
        "MA乖離(%)": round(r["ma25_dev"], 1) if r.get("ma25_dev") is not None else None,
        "買いシグナル": "○" if r.get("buy_signal") else "",
        "下落理由": r.get("drop_reason", ""),
    } for r in bot])


df_div = _build_div_df()
df_buf = _build_buf_df()
df_bot = _build_bot_df()

frames = [f for f in [df_div, df_buf, df_bot] if f is not None]

if not frames:
    st.info("各スクリーナーを実行するとここにダウンロードボタンが表示されます")
else:
    dl_col1, dl_col2, dl_col3 = st.columns(3)
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    with dl_col1:
        combined = pd.concat(frames, ignore_index=True)
        csv_bytes = combined.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "📄 CSV ダウンロード",
            data=csv_bytes,
            file_name=f"stock_analyzer_{now_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with dl_col2:
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            if df_div is not None:
                df_div.drop(columns=["スクリーナー"]).to_excel(
                    writer, sheet_name="高配当×シグナル", index=False)
            if df_buf is not None:
                df_buf.drop(columns=["スクリーナー"]).to_excel(
                    writer, sheet_name="バフェット×シグナル", index=False)
            if df_bot is not None:
                df_bot.drop(columns=["スクリーナー"]).to_excel(
                    writer, sheet_name="シグナル単体", index=False)
            combined.to_excel(writer, sheet_name="全結果", index=False)
        xlsx_buf.seek(0)
        st.download_button(
            "📊 Excel ダウンロード",
            data=xlsx_buf.getvalue(),
            file_name=f"stock_analyzer_{now_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with dl_col3:
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            _jp_font = "Helvetica"
            _jp_font_bold = "Helvetica-Bold"
            for _fp in [
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/YuGothM.ttc",
                "C:/Windows/Fonts/meiryo.ttc",
            ]:
                if os.path.exists(_fp):
                    try:
                        pdfmetrics.registerFont(TTFont("JPFont", _fp))
                        _jp_font = "JPFont"
                        _jp_font_bold = "JPFont"
                        break
                    except Exception:
                        pass

            def _make_pdf(df_list_with_titles: list) -> bytes:
                buf = io.BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                        leftMargin=20, rightMargin=20,
                                        topMargin=30, bottomMargin=20)
                title_style = ParagraphStyle(
                    "title", fontSize=14, spaceAfter=6,
                    fontName=_jp_font_bold, textColor=colors.HexColor("#1e3a5f"),
                )
                section_style = ParagraphStyle(
                    "section", fontSize=11, spaceAfter=4,
                    fontName=_jp_font_bold, textColor=colors.HexColor("#374151"),
                )
                story = []
                story.append(Paragraph("Stock Analyzer Suite — Results", title_style))
                story.append(Paragraph(
                    f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    ParagraphStyle("small", fontSize=8, fontName=_jp_font),
                ))
                story.append(Spacer(1, 10))

                _header_color = colors.HexColor("#1e3a5f")
                _alt_color = colors.HexColor("#f0f4f8")

                for title, df in df_list_with_titles:
                    if df is None or df.empty:
                        continue
                    story.append(Paragraph(title, section_style))
                    header = list(df.columns)
                    rows = [header] + [
                        [str(v) if v is not None else "" for v in row]
                        for row in df.itertuples(index=False, name=None)
                    ]
                    page_w = landscape(A4)[0] - 40
                    col_w = page_w / len(header)
                    t = Table(rows, colWidths=[col_w] * len(header), repeatRows=1)
                    tbl_style = [
                        ("BACKGROUND", (0, 0), (-1, 0), _header_color),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, -1), _jp_font),
                        ("FONTNAME", (0, 0), (-1, 0), _jp_font_bold),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                    for row_i in range(1, len(rows)):
                        if row_i % 2 == 0:
                            tbl_style.append(("BACKGROUND", (0, row_i), (-1, row_i), _alt_color))
                    t.setStyle(TableStyle(tbl_style))
                    story.append(t)
                    story.append(Spacer(1, 12))

                doc.build(story)
                buf.seek(0)
                return buf.getvalue()

            sections = [
                ("高配当スクリーナー×シグナル 合格銘柄",
                 df_div.drop(columns=["スクリーナー"]) if df_div is not None else None),
                ("バフェットスクリーナー×シグナル 分析結果",
                 df_buf.drop(columns=["スクリーナー"]) if df_buf is not None else None),
                ("シグナル単体 スキャン結果",
                 df_bot.drop(columns=["スクリーナー"]) if df_bot is not None else None),
            ]
            pdf_bytes = _make_pdf(sections)
            st.download_button(
                "📑 PDF ダウンロード",
                data=pdf_bytes,
                file_name=f"stock_analyzer_{now_str}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except ImportError:
            st.button(
                "📑 PDF ダウンロード（reportlab未インストール）",
                disabled=True,
                use_container_width=True,
                help="pip install reportlab でインストールしてください",
            )

st.divider()
st.caption("データ出典: Yahoo Finance (yfinance) | キャッシュTTL: 1時間")
st.caption("⚠️ 本ツールは情報提供目的のみです。投資判断は自己責任でお願いします。")
