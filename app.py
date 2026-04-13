"""
app.py — Navigation entry point for the Stock Analyzer Suite.
Page content lives in home.py and pages/*.
"""

import streamlit as st

st.set_page_config(
    page_title="Stock Analyzer Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("home.py",                                          title="Top Page",                        icon="📊"),
    st.Page("pages/1_🎯_dividend_signal_screener.py",           title="高配当 × シグナル",                icon="🎯"),
    st.Page("pages/2_📐_buffett_signal_screener.py",            title="バフェット × シグナル",            icon="📐"),
    st.Page("pages/3_🏹_bottom_screener.py",                    title="シグナル・ハンター（単体）",        icon="🏹"),
    st.Page("pages/4_📈_reit_bond_correlation.py",              title="REITアナリティクス",              icon="📈"),
    st.Page("pages/5_⚖️_portfolio_dashboard.py",                title="ポートフォリオ診断",               icon="⚖️"),
])

pg.run()
