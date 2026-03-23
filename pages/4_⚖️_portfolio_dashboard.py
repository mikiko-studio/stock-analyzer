"""
pages/4_⚖️_portfolio_dashboard.py
ポートフォリオ診断 — 資産配分最適化 + 住宅ローンリスク + ライフイベント計画 + 収支シミュレーション
"""

import math
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.constants import ASSET_EXPECTED_RETURNS
from utils.ui_helpers import hero_header, format_currency

hero_header("ポートフォリオ診断", "年齢・リスク許容度に基づく資産配分最適化", "⚖️")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 基本設定")
    age = st.slider("年齢", 20, 75, 35, 1)
    risk_tolerance = st.slider("リスク許容度", 1, 5, 3, 1,
                                help="1=超安定志向 / 5=積極的成長志向")

    st.divider()
    st.header("📊 現在の保有状況（万円）")
    st.caption("各アセットクラスの現在の保有総額を入力すると、保有比率を自動計算します")

    holdings = {
        "日本株":           st.number_input("🇯🇵 日本株", min_value=0, max_value=100000, value=200, step=10),
        "外国株":           st.number_input("🌍 外国株", min_value=0, max_value=100000, value=300, step=10),
        "国内債券":         st.number_input("📈 国内債券", min_value=0, max_value=100000, value=100, step=10),
        "外国債券":         st.number_input("🌐 外国債券", min_value=0, max_value=100000, value=100, step=10),
        "J-REIT":           st.number_input("🏢 J-REIT", min_value=0, max_value=100000, value=50, step=10),
        "オルタナティブ":   st.number_input("💎 オルタナティブ（金・コモディティ等）", min_value=0, max_value=100000, value=50, step=10),
        "現金・預金":       st.number_input("💴 現金・預金", min_value=0, max_value=100000, value=200, step=10),
    }

    total_assets = sum(holdings.values())
    if total_assets > 0:
        st.success(f"合計: **{total_assets:,} 万円**")
    else:
        st.warning("保有額を入力してください")

# ── Section 1: Target Asset Allocation ──────────────────────────────────────
st.subheader("📊 目標アセットアロケーション")

# Calculate recommended allocation
multiplier = 1.0 + (risk_tolerance - 3) * 0.1
risky_ratio = float(np.clip(((120 - age) / 100) * multiplier, 0.0, 0.95))
safe_ratio = 1.0 - risky_ratio

equity_jp_ratio = risky_ratio * 0.30
equity_us_ratio = risky_ratio * 0.55
equity_reit_ratio = risky_ratio * 0.15
foreign_bond_ratio = safe_ratio * 0.30
alt_ratio = safe_ratio * 0.20
domestic_bond_ratio = safe_ratio * 0.25
cash_ratio = safe_ratio * 0.25

recommended = {
    "🇯🇵 日本株":         equity_jp_ratio,
    "🌍 外国株":          equity_us_ratio,
    "🏢 J-REIT":          equity_reit_ratio,
    "🌐 外国債券":        foreign_bond_ratio,
    "💎 オルタナティブ":  alt_ratio,
    "📈 国内債券":        domestic_bond_ratio,
    "💴 現金・預金":      cash_ratio,
}
recommended = {k: v for k, v in recommended.items() if v > 0.001}

# Actual allocation from holdings
actual_labels = {
    "日本株":         "🇯🇵 日本株",
    "外国株":         "🌍 外国株",
    "国内債券":       "📈 国内債券",
    "外国債券":       "🌐 外国債券",
    "J-REIT":         "🏢 J-REIT",
    "オルタナティブ": "💎 オルタナティブ",
    "現金・預金":     "💴 現金・預金",
}
actual_allocation = {}
if total_assets > 0:
    for key, amount in holdings.items():
        if amount > 0:
            label = actual_labels.get(key, key)
            actual_allocation[label] = amount / total_assets

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    fig_rec = px.pie(
        values=list(recommended.values()),
        names=list(recommended.keys()),
        title=f"推奨配分 (年齢{age}歳 / リスク{risk_tolerance})",
        hole=0.45,
    )
    fig_rec.update_traces(textinfo="percent+label")
    fig_rec.update_layout(height=380)
    st.plotly_chart(fig_rec, use_container_width=True)

with col2:
    if actual_allocation:
        fig_act = px.pie(
            values=list(actual_allocation.values()),
            names=list(actual_allocation.keys()),
            title=f"現在の保有配分 (合計 {total_assets:,}万円)",
            hole=0.45,
        )
        fig_act.update_traces(textinfo="percent+label")
        fig_act.update_layout(height=380)
        st.plotly_chart(fig_act, use_container_width=True)
    else:
        st.info("保有額を入力すると現在の配分が表示されます")

with col3:
    st.markdown(f"""
**分析サマリー**
- 📅 年齢: **{age}歳**
- ⚡ リスク許容度: **{risk_tolerance}/5**
- 📈 リスク資産推奨比率: **{risky_ratio:.0%}**
- 🔒 安全資産推奨比率: **{safe_ratio:.0%}**
""")
    st.markdown("**推奨 vs 現在の比較（万円）**")
    for key, amount in holdings.items():
        label = actual_labels.get(key, key)
        # Find matching recommended ratio
        rec_ratio = 0.0
        for rec_key, rec_val in recommended.items():
            if key in rec_key or rec_key in label:
                rec_ratio = rec_val
                break
        rec_amount = total_assets * rec_ratio if total_assets > 0 else 0
        diff = amount - rec_amount
        diff_str = f"+{diff:,.0f}" if diff >= 0 else f"{diff:,.0f}"
        st.markdown(f"- {label}: **{amount:,}万円** (推奨{rec_amount:,.0f}万円 / 差{diff_str}万円)")

st.divider()

# ── Section 2: Portfolio Expected Return ────────────────────────────────────
# Calculate expected return from actual holdings
if total_assets > 0:
    weighted_return = sum(
        (holdings[key] / total_assets) * ASSET_EXPECTED_RETURNS.get(key, 0.03)
        for key in holdings
    )
else:
    weighted_return = 0.05  # default

# ── Section 3: Mortgage Risk Analysis ──────────────────────────────────────
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
        st.markdown("**ポートフォリオ期待成長率**")
        auto_return_pct = weighted_return * 100
        st.caption(f"自動計算: {auto_return_pct:.2f}%")
        override_return = st.toggle("手動で上書き", value=False)
        if override_return:
            expected_return_pct = st.number_input(
                "期待成長率（%）", 0.0, 15.0, float(round(auto_return_pct, 1)), 0.1
            )
        else:
            expected_return_pct = auto_return_pct


def calc_monthly_payment(principal_man, annual_rate_pct, years):
    """Calculate monthly mortgage payment in 万円."""
    P = principal_man * 10000
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return P / n / 10000
    payment = P * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return payment / 10000


if loan_balance > 0:
    current_payment = calc_monthly_payment(loan_balance, current_rate, remaining_years)
    total_interest = current_payment * remaining_years * 12 - loan_balance

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("現在の月返済額", f"{current_payment:.1f}万円/月")
    mc2.metric("総支払利息（現在金利）", f"{total_interest:.0f}万円")

    compare_label = "繰上返済優先" if current_rate > expected_return_pct else "投資優先"
    compare_delta = f"差: {expected_return_pct - current_rate:.1f}%pt"
    mc3.metric(
        f"金利 vs ポートフォリオ期待成長率({expected_return_pct:.1f}%)",
        compare_label,
        delta=compare_delta,
        delta_color="normal" if current_rate < expected_return_pct else "inverse",
    )
    if current_rate < expected_return_pct:
        st.success(
            f"現在金利({current_rate}%)がポートフォリオ期待成長率({expected_return_pct:.1f}%)を下回っています。"
            f"繰上返済より投資を優先した方が、長期的には有利な可能性があります。"
        )
    else:
        st.warning(
            f"現在金利({current_rate}%)がポートフォリオ期待成長率({expected_return_pct:.1f}%)を上回っています。"
            f"ローン返済の優先度を高めることを検討してください。"
        )

    # Rate hike simulation table (no bar chart)
    rate_scenarios = [current_rate, 1.0, 1.5, 2.0, 3.0]
    scenario_data = []
    for rate in sorted(set(rate_scenarios)):
        if rate < current_rate:
            continue
        monthly = calc_monthly_payment(loan_balance, rate, remaining_years)
        total_int = monthly * remaining_years * 12 - loan_balance
        increase = monthly - current_payment
        beats_portfolio = "🔴 繰上返済優先" if rate > expected_return_pct else "🟢 投資優先"
        scenario_data.append({
            "金利シナリオ": f"{rate:.1f}%",
            "月返済額（万円）": round(monthly, 1),
            "現在比増加（万円/月）": round(increase, 1),
            "総支払利息（万円）": round(total_int, 0),
            "vs 期待成長率": beats_portfolio,
        })

    if scenario_data:
        st.markdown("**📈 金利上昇シナリオ別シミュレーション**")
        df_sim = pd.DataFrame(scenario_data)
        st.dataframe(df_sim, use_container_width=True, hide_index=True)

st.divider()

# ── Section 4: Life Event Reservations ──────────────────────────────────────
st.subheader("📅 ライフイベント 資金計画")
st.markdown("**予定ライフイベント一覧（3年以内は100%現金確保推奨）**")

if "life_events" not in st.session_state:
    current_year = date.today().year
    st.session_state["life_events"] = [
        {"イベント": "教育資金", "予定年": current_year + 5, "必要額(万円)": 300},
        {"イベント": "海外旅行", "予定年": current_year + 1, "必要額(万円)": 50},
        {"イベント": "車購入", "予定年": current_year + 3, "必要額(万円)": 200},
        {"イベント": "住宅リフォーム", "予定年": current_year + 8, "必要額(万円)": 500},
    ]

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

    urgent_total = edited_df[edited_df["years_until"] <= 3]["必要額(万円)"].sum()
    mid_total = edited_df[(edited_df["years_until"] > 3) & (edited_df["years_until"] <= 7)]["必要額(万円)"].sum()
    long_total = edited_df[edited_df["years_until"] > 7]["必要額(万円)"].sum()

    s1, s2, s3 = st.columns(3)
    s1.metric("🔴 3年以内（現金確保）", f"{urgent_total:,.0f}万円")
    s2.metric("🟡 3〜7年（保守的運用）", f"{mid_total:,.0f}万円")
    s3.metric("🟢 7年超（長期投資可）", f"{long_total:,.0f}万円")

st.divider()

# ── Section 5: Monthly Cash Flow Simulation ─────────────────────────────────
st.subheader("💰 毎月の収支シミュレーション")
st.caption("住宅ローン金利の変化が月次収支にどう影響するかをシミュレーションします")

with st.expander("収支設定", expanded=True):
    inc_col, exp_col = st.columns(2)

    with inc_col:
        st.markdown("**収入**")
        monthly_income = st.number_input("月収入（手取り）（万円）", min_value=0.0, max_value=200.0,
                                          value=35.0, step=0.5)

    with exp_col:
        st.markdown("**支出**")
        ec1, ec2 = st.columns(2)
        with ec1:
            food_cost       = st.number_input("食費（万円）",      min_value=0.0, max_value=50.0, value=6.0,  step=0.5)
            water_cost      = st.number_input("水道代（万円）",     min_value=0.0, max_value=10.0, value=0.5,  step=0.1)
            gas_cost        = st.number_input("ガス代（万円）",     min_value=0.0, max_value=10.0, value=0.5,  step=0.1)
            electric_cost   = st.number_input("電気代（万円）",     min_value=0.0, max_value=10.0, value=1.0,  step=0.1)
        with ec2:
            education_cost  = st.number_input("教育費（万円）",     min_value=0.0, max_value=50.0, value=2.0,  step=0.5)
            other_cost      = st.number_input("その他支出（万円）", min_value=0.0, max_value=50.0, value=5.0,  step=0.5)
            st.markdown("※ ローン返済額は下表で金利別に自動計算")

fixed_expenses = food_cost + water_cost + gas_cost + electric_cost + education_cost + other_cost

if loan_balance > 0:
    # Build cash flow simulation table across interest rate scenarios
    cf_scenarios = []
    sim_rates = [current_rate + i * 0.5 for i in range(7) if current_rate + i * 0.5 <= 5.0]
    sim_rates = sorted(set([current_rate] + sim_rates))

    for rate in sim_rates:
        loan_payment = calc_monthly_payment(loan_balance, rate, remaining_years)
        total_expense = fixed_expenses + loan_payment
        balance = monthly_income - total_expense
        cf_scenarios.append({
            "金利シナリオ": f"{rate:.1f}%",
            "ローン返済額": round(loan_payment, 2),
            "固定支出合計": round(fixed_expenses, 2),
            "支出合計": round(total_expense, 2),
            "月次収支（万円）": round(balance, 2),
            "年間収支（万円）": round(balance * 12, 1),
        })

    cf_df = pd.DataFrame(cf_scenarios)

    # Style dataframe: highlight negative balance rows
    def highlight_balance(row):
        color = "background-color: #fef2f2; color: #dc2626;" if row["月次収支（万円）"] < 0 else ""
        return [color] * len(row)

    st.markdown("**金利別 月次収支シミュレーション**")
    styled_df = cf_df.style.apply(highlight_balance, axis=1).format({
        "ローン返済額": "{:.2f}",
        "固定支出合計": "{:.2f}",
        "支出合計": "{:.2f}",
        "月次収支（万円）": "{:.2f}",
        "年間収支（万円）": "{:.1f}",
    })
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Chart: monthly balance by interest rate
    fig_cf = go.Figure()
    colors = ["#22c55e" if row["月次収支（万円）"] >= 0 else "#ef4444" for _, row in cf_df.iterrows()]
    fig_cf.add_trace(go.Bar(
        x=cf_df["金利シナリオ"],
        y=cf_df["月次収支（万円）"],
        marker_color=colors,
        text=[f"{v:.1f}万円" for v in cf_df["月次収支（万円）"]],
        textposition="outside",
    ))
    fig_cf.add_hline(y=0, line_dash="solid", line_color="#94a3b8", line_width=2)
    fig_cf.update_layout(
        title="金利別 月次収支（プラス=黒字 / マイナス=赤字）",
        yaxis_title="月次収支（万円）",
        xaxis_title="金利シナリオ",
        height=350,
    )
    st.plotly_chart(fig_cf, use_container_width=True)

    # Warning: identify break-even rate
    negative_rows = cf_df[cf_df["月次収支（万円）"] < 0]
    if not negative_rows.empty:
        first_negative_rate = negative_rows.iloc[0]["金利シナリオ"]
        st.error(
            f"⚠️ **警告**: 金利が **{first_negative_rate}** 以上になると月次収支がマイナスになります。\n\n"
            f"支出の見直しや繰上返済・借り換えを検討してください。"
        )
    else:
        st.success(
            f"✅ シミュレーション範囲内（最大{sim_rates[-1]:.1f}%）では月次収支はプラスを維持できます。"
        )

    # Expense breakdown (current rate)
    current_loan_payment = calc_monthly_payment(loan_balance, current_rate, remaining_years)
    expense_breakdown = {
        "食費": food_cost,
        "水道代": water_cost,
        "ガス代": gas_cost,
        "電気代": electric_cost,
        "教育費": education_cost,
        "その他": other_cost,
        "ローン返済": current_loan_payment,
    }
    expense_breakdown = {k: v for k, v in expense_breakdown.items() if v > 0}

    with st.expander("📊 現在金利での支出内訳"):
        fig_exp = px.pie(
            values=list(expense_breakdown.values()),
            names=list(expense_breakdown.keys()),
            title=f"支出内訳（現在金利 {current_rate}%）",
            hole=0.4,
        )
        fig_exp.update_traces(textinfo="percent+label")
        fig_exp.update_layout(height=350)

        exp_col1, exp_col2 = st.columns([1, 1])
        with exp_col1:
            st.plotly_chart(fig_exp, use_container_width=True)
        with exp_col2:
            total_exp = sum(expense_breakdown.values())
            st.markdown(f"**月収入: {monthly_income:.1f}万円**")
            st.markdown(f"**月支出合計: {total_exp:.1f}万円**")
            balance_now = monthly_income - total_exp
            if balance_now >= 0:
                st.success(f"月次収支: **+{balance_now:.1f}万円**（年間 +{balance_now*12:.1f}万円）")
            else:
                st.error(f"月次収支: **{balance_now:.1f}万円**（年間 {balance_now*12:.1f}万円）")
            for k, v in expense_breakdown.items():
                pct = v / total_exp * 100 if total_exp > 0 else 0
                st.markdown(f"- {k}: {v:.2f}万円 ({pct:.1f}%)")

else:
    # No loan
    fixed_total = fixed_expenses
    balance_no_loan = monthly_income - fixed_total
    st.markdown(f"""
**月次収支サマリー（ローンなし）**
- 月収入: **{monthly_income:.1f}万円**
- 月固定支出: **{fixed_total:.1f}万円**
- 月次収支: **{balance_no_loan:.1f}万円**
""")
    if balance_no_loan >= 0:
        st.success(f"月次収支: **+{balance_no_loan:.1f}万円**（年間 +{balance_no_loan*12:.1f}万円）")
    else:
        st.error(f"月次収支: **{balance_no_loan:.1f}万円** ⚠️ 収支がマイナスです")
    st.info("住宅ローン残債を入力すると、金利変化に連動した収支シミュレーションが表示されます。")
