"""
pages/4_⚖️_portfolio_dashboard.py
ポートフォリオ診断 — 資産配分最適化 + 住宅ローンリスク + ライフイベント計画
"""

import math
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.ui_helpers import hero_header, format_currency

st.set_page_config(page_title="ポートフォリオ診断", page_icon="⚖️", layout="wide")

hero_header("ポートフォリオ診断", "年齢・リスク許容度に基づく資産配分最適化", "⚖️")

# ── Section 1: Target Asset Allocation ──────────────────────────────────────
st.subheader("📊 目標アセットアロケーション")

with st.sidebar:
    st.header("⚙️ 基本設定")
    age = st.slider("年齢", 20, 75, 35, 1)
    risk_tolerance = st.slider("リスク許容度", 1, 5, 3, 1,
                                help="1=超安定志向 / 5=積極的成長志向")
    include_foreign_bonds = st.toggle("外国債券を含む", value=True)
    total_assets = st.number_input("総資産額（万円）", min_value=0, max_value=100000,
                                    value=1000, step=100)

# Calculate target allocation
multiplier = 1.0 + (risk_tolerance - 3) * 0.1  # 0.8 ~ 1.2
risky_ratio = float(np.clip(((120 - age) / 100) * multiplier, 0.0, 0.95))
safe_ratio = 1.0 - risky_ratio

# Split equity
equity_jp_ratio = risky_ratio * 0.30
equity_us_ratio = risky_ratio * 0.55
equity_reit_ratio = risky_ratio * 0.15

# Safe assets
if include_foreign_bonds:
    foreign_bond_ratio = safe_ratio * 0.30
    alt_ratio = safe_ratio * 0.20
    domestic_bond_ratio = safe_ratio * 0.25
    cash_ratio = safe_ratio * 0.25
else:
    foreign_bond_ratio = 0.0
    alt_ratio = safe_ratio * 0.25
    domestic_bond_ratio = safe_ratio * 0.35
    cash_ratio = safe_ratio * 0.40

allocation = {
    "🇯🇵 日本株": equity_jp_ratio,
    "🌍 外国株": equity_us_ratio,
    "🏢 J-REIT": equity_reit_ratio,
    "🌐 外国債券": foreign_bond_ratio,
    "💎 オルタナティブ": alt_ratio,
    "📈 国内債券": domestic_bond_ratio,
    "💴 現金・預金": cash_ratio,
}
# Remove zero entries
allocation = {k: v for k, v in allocation.items() if v > 0.001}

col1, col2 = st.columns([1, 1])
with col1:
    fig_donut = px.pie(
        values=list(allocation.values()),
        names=list(allocation.keys()),
        title=f"推奨アセットアロケーション (年齢{age}歳 / リスク許容度{risk_tolerance})",
        hole=0.45,
    )
    fig_donut.update_traces(textinfo="percent+label")
    fig_donut.update_layout(height=400)
    st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    st.markdown(f"""
**分析サマリー**
- 📅 年齢: **{age}歳**
- ⚡ リスク許容度: **{risk_tolerance}/5**
- 📈 リスク資産比率: **{risky_ratio:.0%}**
- 🔒 安全資産比率: **{safe_ratio:.0%}**

**金額目安（総資産{total_assets:,}万円の場合）**
""")
    for asset, ratio in allocation.items():
        amount = total_assets * ratio
        st.markdown(f"- {asset}: **{amount:,.0f}万円** ({ratio:.0%})")

st.divider()

# ── Section 2: Mortgage Risk Analysis ──────────────────────────────────────
st.subheader("🏠 住宅ローン金利リスク分析")

with st.expander("住宅ローン設定", expanded=True):
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        loan_balance = st.number_input("残債（万円）", 0, 100000, 3000, 100)
    with mc2:
        current_rate = st.number_input("現在金利（%）", 0.0, 5.0, 0.5, 0.1)
    with mc3:
        remaining_years = st.number_input("残年数（年）", 1, 35, 25, 1)
    with mc4:
        bond_yield = st.number_input("債券利回り想定（%）", 0.0, 5.0, 1.5, 0.1)


def calc_monthly_payment(principal_man, annual_rate_pct, years):
    """Calculate monthly mortgage payment."""
    P = principal_man * 10000  # to yen
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return P / n / 10000  # 万円
    payment = P * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return payment / 10000  # 万円


if loan_balance > 0:
    current_payment = calc_monthly_payment(loan_balance, current_rate, remaining_years)
    total_interest = current_payment * remaining_years * 12 - loan_balance

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("現在の月返済額", f"{current_payment:.1f}万円/月")
    mc2.metric("総支払利息（現在金利）", f"{total_interest:.0f}万円")
    mc3.metric(
        "金利 vs 債券利回り",
        "繰上返済優先" if current_rate > bond_yield else "投資優先",
        delta=f"差: {bond_yield - current_rate:.1f}%",
        delta_color="normal" if current_rate < bond_yield else "inverse",
    )

    # Rate hike simulation
    rate_scenarios = [current_rate, 1.0, 1.5, 2.0, 3.0]
    scenario_data = []
    for rate in rate_scenarios:
        if rate < current_rate:
            continue
        monthly = calc_monthly_payment(loan_balance, rate, remaining_years)
        total_int = monthly * remaining_years * 12 - loan_balance
        increase = monthly - current_payment
        scenario_data.append({
            "金利シナリオ": f"{rate:.1f}%",
            "月返済額（万円）": round(monthly, 1),
            "現在比増加（万円/月）": round(increase, 1),
            "総支払利息（万円）": round(total_int, 0),
        })

    if scenario_data:
        st.markdown("**📈 金利上昇シナリオ別シミュレーション**")
        df_sim = pd.DataFrame(scenario_data)
        st.dataframe(df_sim, use_container_width=True, hide_index=True)

        fig_sim = px.bar(
            df_sim,
            x="金利シナリオ",
            y="月返済額（万円）",
            title="金利別 月返済額シミュレーション",
            color="月返済額（万円）",
            color_continuous_scale="RdYlGn_r",
        )
        fig_sim.update_layout(height=300)
        st.plotly_chart(fig_sim, use_container_width=True)

st.divider()

# ── Section 3: Life Event Reservations ──────────────────────────────────────
st.subheader("📅 ライフイベント 資金計画")

st.markdown("**予定ライフイベント一覧（3年以内は100%現金確保推奨）**")

# Default life events
if "life_events" not in st.session_state:
    current_year = date.today().year
    st.session_state["life_events"] = [
        {"イベント": "教育資金", "予定年": current_year + 5, "必要額(万円)": 300},
        {"イベント": "海外旅行", "予定年": current_year + 1, "必要額(万円)": 50},
        {"イベント": "車購入", "予定年": current_year + 3, "必要額(万円)": 200},
        {"イベント": "住宅リフォーム", "予定年": current_year + 8, "必要額(万円)": 500},
    ]

# Edit life events
le_df = pd.DataFrame(st.session_state["life_events"])
edited_df = st.data_editor(
    le_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "予定年": st.column_config.NumberColumn("予定年", min_value=date.today().year, max_value=date.today().year + 30),
        "必要額(万円)": st.column_config.NumberColumn("必要額(万円)", min_value=0),
    },
)
st.session_state["life_events"] = edited_df.to_dict("records")

if not edited_df.empty:
    current_year = date.today().year
    edited_df["years_until"] = edited_df["予定年"] - current_year
    edited_df["推奨運用方法"] = edited_df["years_until"].apply(
        lambda y: "💴 100%現金" if y <= 3 else ("📈 保守的運用" if y <= 7 else "🚀 長期投資可")
    )
    edited_df["優先度"] = edited_df["years_until"].apply(
        lambda y: "🔴 高" if y <= 3 else ("🟡 中" if y <= 7 else "🟢 低")
    )

    st.dataframe(
        edited_df[["イベント", "予定年", "必要額(万円)", "years_until", "推奨運用方法", "優先度"]].rename(
            columns={"years_until": "あと何年"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    # Timeline chart
    fig_timeline = px.scatter(
        edited_df,
        x="予定年",
        y="必要額(万円)",
        text="イベント",
        size="必要額(万円)",
        color="推奨運用方法",
        title="ライフイベント タイムライン",
        labels={"予定年": "年", "必要額(万円)": "必要額（万円）"},
    )
    fig_timeline.update_traces(textposition="top center")
    fig_timeline.add_vline(
        x=current_year + 3,
        line_dash="dash",
        line_color="red",
        annotation_text="3年ライン（現金確保）",
    )
    fig_timeline.update_layout(height=400)
    st.plotly_chart(fig_timeline, use_container_width=True)

    # Summary
    urgent_total = edited_df[edited_df["years_until"] <= 3]["必要額(万円)"].sum()
    mid_total = edited_df[(edited_df["years_until"] > 3) & (edited_df["years_until"] <= 7)]["必要額(万円)"].sum()
    long_total = edited_df[edited_df["years_until"] > 7]["必要額(万円)"].sum()

    s1, s2, s3 = st.columns(3)
    s1.metric("🔴 3年以内（現金確保）", f"{urgent_total:,.0f}万円")
    s2.metric("🟡 3〜7年（保守的運用）", f"{mid_total:,.0f}万円")
    s3.metric("🟢 7年超（長期投資可）", f"{long_total:,.0f}万円")
