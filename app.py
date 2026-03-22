"""
app.py — Main entry point for the unified stock analysis app.
Uses Streamlit's native multi-page support via the pages/ directory.
"""

import streamlit as st

st.set_page_config(
    page_title="Stock Analyzer Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Stock Analyzer Suite")
st.markdown("### 株式分析統合ツール — Japan & US Market")
st.divider()

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown("#### 🎯 高配当スクリーナー")
        st.markdown("""
3層フィルターで選ぶ「鉄壁高配当株」
- **Layer 1** 財務の鉄壁: 自己資本比率・営業CF
- **Layer 2** 配当の誠実さ: 利回り・性向・減配チェック
- **Layer 3** 稼ぐ力: 営業利益率・ROE
""")
    with st.container(border=True):
        st.markdown("#### 🏹 シグナル・ハンター")
        st.markdown("""
テクニカル過熱感 × ニュース解析による押し目買い判定
- RSI(14) + 25日MA乖離率
- ニュース自動分類で下落理由を把握
- 52週高値/安値との距離チェック
""")
with col2:
    with st.container(border=True):
        st.markdown("#### 📐 三角測量スクリーナー")
        st.markdown("""
バフェット流 P/E・DCF・GDM トライアンギュレーション
- **P/E分析**: セクター平均との比較
- **DCF**: 内在価値の現在価値計算
- **GDM**: グレアム防衛的価値モデル
""")
    with st.container(border=True):
        st.markdown("#### ⚖️ ポートフォリオ診断")
        st.markdown("""
年齢・リスク許容度に基づく資産配分最適化
- 目標アセットアロケーション計算
- 住宅ローン金利上昇シミュレーション
- ライフイベント資金計画タイムライン
""")

st.divider()
col_a, col_b = st.columns(2)
with col_a:
    st.info("👈 **サイドバーからツールを選択してください**")
with col_b:
    st.caption("データ出典: Yahoo Finance (yfinance) | キャッシュTTL: 1時間")
    st.caption("⚠️ 本ツールは情報提供目的のみです。投資判断は自己責任でお願いします。")
